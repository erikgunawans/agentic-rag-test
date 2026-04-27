"""LLM-based missed-PII scan (D-75 / D-77 / D-78, SCAN-01..05, FR-8.1..5).

Auto-chained inside RedactionService.redact_text after primary anonymization:
  detect → anonymize → missed-scan → re-anonymize-if-replaced → return.

D-75: scan operates on the ALREADY-ANONYMIZED text. The cloud LLM only sees
surrogates + [TYPE] placeholders — never raw real values. Privacy-safe by
construction.

D-77: response schema = list[{type, text}]; server uses re.escape(text) +
re.subn to replace ALL occurrences (handles multi-mention). Type validated
against settings.pii_redact_entities; invalid types silently dropped (FR-8.4).

D-78: soft-fail on provider failure. On timeout / 5xx / network / Pydantic
validation error: WARNING-level structured log (counts only — B4 invariant)
+ @traced span tag (scan_skipped=True). Anonymization continues with primary
NER results. PERF-04 mandates this behavior.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import get_settings
from app.services.llm_provider import LLMProviderClient, _EgressBlocked
from app.services.tracing_service import traced

if TYPE_CHECKING:
    from app.services.redaction.registry import ConversationRegistry

logger = logging.getLogger(__name__)


class MissedEntity(BaseModel):
    """One missed-PII match returned by the scan LLM (D-77)."""

    model_config = ConfigDict(extra="forbid")
    type: str = Field(..., min_length=1, max_length=64)
    text: str = Field(..., min_length=1, max_length=1000)


class MissedScanResponse(BaseModel):
    """Top-level scan response. Pydantic validation = the schema gate."""

    model_config = ConfigDict(extra="forbid")
    entities: list[MissedEntity] = Field(default_factory=list, max_length=100)


def _valid_hard_redact_types() -> set[str]:
    """D-77 / FR-8.4: build the whitelist from Settings.pii_redact_entities."""
    raw = get_settings().pii_redact_entities or ""
    return {t.strip() for t in raw.split(",") if t.strip()}


@traced(name="redaction.missed_scan")
async def scan_for_missed_pii(
    anonymized_text: str,
    registry: "ConversationRegistry",
) -> tuple[str, int]:
    """D-75: run a missed-PII LLM scan over the already-anonymized text.

    Returns (possibly-modified text, replacements_count). On any failure
    returns (anonymized_text, 0) — never raises (D-78 / NFR-3 / PERF-04).
    """
    settings = get_settings()
    if not settings.pii_missed_scan_enabled:
        return anonymized_text, 0

    valid_types = _valid_hard_redact_types()
    if not valid_types:
        # No configured hard-redact types → nothing the scan could legally replace.
        return anonymized_text, 0

    messages = [
        {
            "role": "system",
            "content": (
                "Identify any PII the primary NER missed in the text below. "
                'Respond ONLY with JSON: {"entities":[{"type":"<TYPE>","text":"<verbatim substring>"}]}. '
                f"Allowed types: {sorted(valid_types)}. "
                "Return ONLY entities of those types. Do NOT include character offsets — "
                "the server matches by substring. Do NOT return surrogates that are already "
                "anonymized; only NEW PII you spot."
            ),
        },
        {"role": "user", "content": anonymized_text},
    ]

    client = LLMProviderClient()

    try:
        result = await client.call(
            feature="missed_scan",
            messages=messages,
            registry=registry,
            provisional_surrogates=None,  # D-56: no provisional set for this feature
        )
        parsed = MissedScanResponse.model_validate(result)
    except _EgressBlocked:
        # Defense-in-depth backstop fired (Phase 3 D-53..D-56). Soft-fail.
        logger.warning(
            "event=missed_scan_skipped feature=missed_scan error_class=_EgressBlocked"
        )
        return anonymized_text, 0
    except ValidationError:
        logger.warning(
            "event=missed_scan_skipped feature=missed_scan error_class=ValidationError"
        )
        return anonymized_text, 0
    except Exception as exc:  # noqa: BLE001 — D-78 catch-all (timeout / 5xx / network)
        logger.warning(
            "event=missed_scan_skipped feature=missed_scan error_class=%s",
            type(exc).__name__,
        )
        return anonymized_text, 0

    # D-77: substring-replace each valid (type, text) pair. Drop invalid types silently.
    out = anonymized_text
    replacements = 0
    for ent in parsed.entities:
        if ent.type not in valid_types:
            continue  # FR-8.4: invalid types discarded
        placeholder = f"[{ent.type}]"
        new_text, n = re.subn(re.escape(ent.text), placeholder, out)
        out = new_text
        replacements += n
    return out, replacements
