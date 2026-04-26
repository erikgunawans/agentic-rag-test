"""Pre-flight egress filter for cloud LLM calls (D-53..D-56, PROVIDER-04, NFR-2).

The egress filter is the security primitive of the v1.0 PII milestone: every
cloud-LLM call passes through this function with its outbound payload BEFORE
any byte leaves the process. It scans for any case-insensitive word-boundary
match against the union of:
  - registry.entries() — all real values from prior turns of this thread
  - the in-flight provisional surrogate map for THIS turn (D-56)

If ANY match is found, the result is `tripped=True` and the LLMProviderClient
raises _EgressBlocked, which the caller's algorithmic-fallback wrapper catches
(D-52 / D-54). The trip log line carries COUNTS + entity_types + 8-char SHA-256
hashes ONLY (D-55). Raw values are NEVER logged (B4 invariant).
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.redaction.registry import ConversationRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EgressResult:
    """Outcome of a single egress_filter() call.

    tripped: True if at least one match was found (block the call).
    match_count: number of distinct (entity_type, real_value) matches.
    entity_types: sorted unique entity types matched (e.g. ['EMAIL_ADDRESS', 'PERSON']).
    match_hashes: sorted unique 8-char SHA-256 hashes of matched real values
                  (D-55 — forensic-correlation-friendly without leaking PII).
    """
    tripped: bool
    match_count: int
    entity_types: list[str]
    match_hashes: list[str]


class _EgressBlocked(Exception):
    """Internal-only: caught by LLMProviderClient's fallback wrapper.

    Never raised to the chat loop (NFR-3 'never crash'). Carries the
    EgressResult so the caller can log + decide on algorithmic fallback.
    """
    def __init__(self, result: EgressResult) -> None:
        self.result = result
        super().__init__("egress filter blocked cloud call")


def _hash8(value: str) -> str:
    """8-char SHA-256 hash for forensic logging (D-55). NOT for security."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def egress_filter(
    payload: str,
    registry: "ConversationRegistry",
    provisional: dict[str, str] | None,
) -> EgressResult:
    """D-53: casefold + word-boundary regex match.
    D-56: scope = persisted registry ∪ in-flight provisional surrogates.
    Bail-on-first-match in the inner loop is acceptable; we accumulate all
    matches for richer telemetry (small registries; n is per-thread).

    Args:
        payload: the outbound LLM request body as a plain string (caller
            pre-serializes messages — usually json.dumps(messages)).
        registry: the per-thread ConversationRegistry whose entries() supplies
            the persisted real values.
        provisional: dict[real_value, provisional_surrogate] for entities
            detected in THIS turn that are not yet persisted (D-56). May be None.

    Returns:
        EgressResult with tripped=True iff any candidate matched.
    """
    haystack = payload.casefold()
    matches: list[tuple[str, str]] = []

    # Build candidate (entity_type, real_value) list.
    candidates: list[tuple[str, str]] = []
    for ent in registry.entries():
        # EntityMapping field name confirmed by grepping registry.py before write.
        candidates.append((ent.entity_type, ent.real_value))
    if provisional:
        for real_value in provisional:
            candidates.append(("PERSON", real_value))  # provisional set is PERSON-only

    for entity_type, value in candidates:
        if not value:
            continue
        pattern = r"\b" + re.escape(value.casefold()) + r"\b"
        if re.search(pattern, haystack):
            matches.append((entity_type, value))

    result = EgressResult(
        tripped=bool(matches),
        match_count=len(matches),
        entity_types=sorted({t for t, _ in matches}),
        match_hashes=sorted({_hash8(v) for _, v in matches}),
    )

    if result.tripped:
        # D-55: counts + entity_types + 8-char SHA-256 hashes ONLY. NEVER raw values.
        logger.warning(
            "egress_filter_blocked event=egress_filter_blocked match_count=%d entity_types=%s match_hashes=%s",
            result.match_count, result.entity_types, result.match_hashes,
        )

    return result
