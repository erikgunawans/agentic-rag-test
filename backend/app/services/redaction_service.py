"""Public RedactionService — composes detection + anonymization (D-13..D-15).

This is the single entry point for the v1.0 PII redaction layer. It glues
together the building blocks shipped across Phases 1-3:

- ``uuid_filter`` (Phase 1) — pre-mask UUIDs so Presidio never touches them.
- ``detection`` (Phase 1) — Presidio + spaCy ``xx_ent_wiki_sm`` two-pass
  threshold filter; returns ``(masked_text, entities, sentinels)``.
- ``clustering`` (Phase 3 Wave 3) — Union-Find PERSON cluster builder +
  D-48 sub-surrogate variant set generator.
- ``llm_provider`` (Phase 3 Wave 4) — provider-aware AsyncOpenAI client with
  pre-flight egress filter for cloud calls (D-53..D-56).
- ``anonymization`` (Phase 1 / Phase 3) — cluster-aware Faker dispatch:
  one surrogate per cluster; non-PERSON spans flow through the per-entity
  Phase 1 path (D-62 / RESOLVE-04).
- ``tracing_service`` (Phase 1) — provides the ``@traced`` decorator.

Design invariants:

- W10: ``redact_text`` calls ``detect_entities`` exactly once and uses the
  returned 3-tuple directly. The UUID-masking helper is NOT called from
  here — it lives inside ``detect_entities``. This file imports only
  ``restore_uuids``.
- D-13: public method is ``async def redact_text(text) -> RedactionResult``.
  Phase 2 widened the signature to accept a registry; Phase 3 dispatches on
  ``settings.entity_resolution_mode`` inside the registry-aware path.
- D-14: Phase 1 stateless path remains stateless — no per-conversation
  registry, no thread parameter, no caching of real values across calls.
- D-15: ``get_redaction_service()`` is ``@lru_cache``'d. The FastAPI lifespan
  calls it once at startup so Presidio + Faker + gender detector are loaded
  before the first chat request (PERF-01).
- D-18 / B4: ``redact_text`` is wrapped in ``@traced(name="redaction.redact_text")``
  for OBS-01. Span attributes are counts and timings only — never real
  entity values.
- D-29 / D-30: per-thread asyncio.Lock spans detect → cluster → LLM-call →
  generate-surrogates → upsert-deltas → return. The Phase 3 LLM call
  happens INSIDE the lock; ``LLMProviderClient`` enforces a
  settings-controlled timeout (default 30 s) so the lock is bounded.
- D-52 / D-54 / NFR-3: ``_EgressBlocked`` and any other exception from the
  cloud-LLM path fall back to algorithmic clusters; never re-raised to the
  chat loop.
- D-62 / RESOLVE-04: only PERSON entities are clustered. EMAIL / PHONE /
  URL / LOCATION / DATE_TIME / IP_ADDRESS / hard-redact spans flow through
  the existing Phase 1 + Phase 2 per-entity path — no clustering, no LLM
  contact.
"""

from __future__ import annotations

import asyncio
import weakref
import json
import logging
import re
import time
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import get_settings
from app.services.llm_provider import LLMProviderClient
from app.services.system_settings_service import get_system_settings
from app.services.redaction.anonymization import (
    anonymize,
    get_faker,
    get_gender_detector,
)
from app.services.redaction.clustering import Cluster, cluster_persons, variants_for
from app.services.redaction.detection import Entity, detect_entities, get_analyzer
from app.services.redaction.egress import _EgressBlocked
from app.services.redaction.fuzzy_match import best_match
from app.services.redaction.missed_scan import scan_for_missed_pii
from app.services.redaction.registry import ConversationRegistry, EntityMapping

# W10: the UUID pre-mask helper is intentionally NOT imported here. It is
# called exactly once per ``redact_text`` invocation, from inside
# ``detect_entities``, and the resulting sentinel map is threaded back
# through this module via the 3-tuple return. We only need ``restore_uuids``
# to put the original UUIDs back after substitution.
from app.services.redaction.uuid_filter import restore_uuids
from app.services.tracing_service import traced

logger = logging.getLogger(__name__)


# D-29 (PERF-03): per-process asyncio.Lock keyed by thread_id.
# NOTE (D-31, FUTURE-WORK Phase 6): UPGRADE PATH for multi-worker / multi-instance
# Railway deploys is `pg_advisory_xact_lock(hashtext(thread_id))` — see
# `.planning/STATE.md` "Pending Items" → "Async-lock cross-process upgrade".
# asyncio.Lock is correct only while Railway runs a single Uvicorn worker.
# The composite UNIQUE constraint `(thread_id, real_value_lower)` on the
# entity_registry table (migration 029) is the cross-process safety net.
#
# WeakValueDictionary so locks GC when no coroutine holds them — prevents
# unbounded growth as new thread_ids are seen over a long-running process.
_thread_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = weakref.WeakValueDictionary()
_thread_locks_master: asyncio.Lock = asyncio.Lock()


class RedactionResult(BaseModel):
    """D-13 public output schema.

    Attributes:
        anonymized_text: Input text with surrogate-bucket entities replaced
            by Faker values and hard-redact-bucket entities replaced by
            literal ``[ENTITY_TYPE]`` placeholders. UUIDs are preserved
            exactly.
        entity_map: Mapping of real value -> surrogate. Contains ONLY
            surrogate-bucket pairs; hard-redacted entities are excluded
            per FR-3.5 / D-08. Phase 2's de-anonymization layer consumes
            this same shape from a persisted registry.
        hard_redacted_count: How many hard-redact placeholders were emitted.
            Useful for observability / SLA dashboards.
        latency_ms: Wall-clock duration of the whole redact call, including
            detection, anonymization, and UUID restoration.

    Frozen: callers must not mutate the result; this guards against
    accidental cross-request leaks if the result is ever cached.
    """

    model_config = ConfigDict(frozen=True)

    anonymized_text: str
    entity_map: dict[str, str]
    hard_redacted_count: int
    latency_ms: float


# Phase 4 D-73: LLM fuzzy-match response schema. Server validates membership
# of `token` against Pass-1 placeholders dict (extra defense beyond Pydantic).
# `extra="forbid"` rejects spurious fields the LLM might invent; `pattern` on
# `token` shape-checks that returned tokens look like Pass 1 placeholders.
class _FuzzyMatch(BaseModel):
    """One LLM-fuzzy-match candidate (D-73)."""

    model_config = ConfigDict(extra="forbid")

    span: str = Field(..., min_length=1, max_length=500)
    token: str = Field(..., pattern=r"^<<PH_[0-9a-f]+>>$")


class _FuzzyMatchResponse(BaseModel):
    """LLM fuzzy-match response — Pydantic-validated payload (D-73).

    Cap of 50 matches per call is generous for normal chat turns and limits
    blast radius from a misbehaving / adversarial provider response.
    """

    model_config = ConfigDict(extra="forbid")

    matches: list[_FuzzyMatch] = Field(default_factory=list, max_length=50)


def _split_person_non_person(
    entities: list[Entity],
) -> tuple[list[Entity], list[Entity]]:
    """D-62 / RESOLVE-04: PERSON entities go through clustering; everything
    else (EMAIL / PHONE / URL / LOCATION / DATE_TIME / IP_ADDRESS / hard-redact)
    flows through the existing Phase 1 + Phase 2 per-entity path.

    Returns ``(person_entities, non_person_entities)``.
    """
    person_entities = [e for e in entities if e.type == "PERSON"]
    non_person_entities = [e for e in entities if e.type != "PERSON"]
    return person_entities, non_person_entities


def _clusters_for_mode_none(person_entities: list[Entity]) -> list[Cluster]:
    """D-62 / Claude's Discretion §"none" mode: each PERSON entity becomes
    its own pseudo-cluster (canonical = entity.text, members = (entity,)).

    No merges; no nickname expansion. The variant set is still computed via
    ``variants_for`` so cross-turn de-anonymization still has the variant
    rows in entity_registry to round-trip on. This is explicitly worse for
    coreference quality than algorithmic mode but is the deterministic
    "do nothing" path.
    """
    return [
        Cluster(
            canonical=e.text,
            variants=variants_for(e.text),
            members=(e,),
        )
        for e in person_entities
    ]


async def _resolve_clusters_via_llm(
    person_entities: list[Entity],
    registry: ConversationRegistry,
) -> tuple[list[Cluster], bool, str, bool]:
    """D-49 / D-52 / D-54: try to refine algorithmic clusters via the LLM
    provider; on ANY failure (egress trip, network, schema mismatch) fall
    back to the algorithmic clusters.

    Returns:
        ``(clusters, provider_fallback, fallback_reason, egress_tripped)``.

    Caller holds the per-thread asyncio.Lock; this function MUST NOT raise
    (NFR-3 — never crash, never leak). The cloud LLM call happens inside
    ``LLMProviderClient`` which enforces a settings-controlled timeout
    (D-50, default 30 s) so the lock is bounded.
    """
    # First, always compute the algorithmic clusters — they are the fallback
    # answer if the LLM path errors out OR returns invalid JSON.
    algorithmic_clusters = cluster_persons(person_entities)

    # No PERSON entities → no LLM call needed. Empty cluster list is the
    # correct answer, not an error.
    if not algorithmic_clusters:
        return [], False, "", False

    # Build the provisional surrogate map for the egress filter (D-56).
    # The filter's job is to scan the outbound payload for ANY real value
    # that might be in the registry OR in this turn's in-flight set; using
    # the canonical real values as keys here keeps the filter scope
    # exhaustive without leaking provisional surrogates that don't exist
    # yet (anonymize() hasn't run yet — Faker output not assigned).
    provisional_surrogates: dict[str, str] = {
        c.canonical: c.canonical for c in algorithmic_clusters
    }

    # Compose the resolution prompt. Schema documented in CONTEXT.md D-49.
    # The model's job is to RE-GROUP existing members (no name invention).
    prompt_clusters = [
        {"canonical": c.canonical, "members": [m.text for m in c.members]}
        for c in algorithmic_clusters
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "You are a coreference resolver. The user provides "
                "preliminary PERSON clusters. Return JSON "
                '{"clusters": [{"canonical": str, "members": list[str]}, ...]} '
                "with the same members regrouped if you can identify obvious "
                "mergeable clusters; otherwise return the input unchanged. "
                "Never invent names. Never include any text outside the JSON "
                "object."
            ),
        },
        {
            "role": "user",
            "content": json.dumps({"clusters": prompt_clusters}, ensure_ascii=False),
        },
    ]

    try:
        client = LLMProviderClient()
        result = await client.call(
            feature="entity_resolution",
            messages=messages,
            registry=registry,
            provisional_surrogates=provisional_surrogates,
        )

        # Schema validation. Any mismatch raises ValueError → falls back.
        refined = result.get("clusters") if isinstance(result, dict) else None
        if not isinstance(refined, list):
            raise ValueError("invalid resolution response (clusters not a list)")

        # Re-attach Entity members by looking up each member text in the
        # algorithmic-cluster member pool. Hallucinated names are silently
        # dropped (T-CLUST-02 mitigation) — never invented.
        text_to_entity: dict[str, Entity] = {
            m.text: m for c in algorithmic_clusters for m in c.members
        }
        clusters_built: list[Cluster] = []
        for entry in refined:
            if not isinstance(entry, dict):
                raise ValueError("invalid resolution response entry (not a dict)")
            canonical = entry.get("canonical")
            members_raw = entry.get("members")
            if not isinstance(canonical, str) or not isinstance(members_raw, list):
                raise ValueError("invalid resolution response entry shape")
            members = tuple(
                text_to_entity[m] for m in members_raw if m in text_to_entity
            )
            if not members:
                continue
            clusters_built.append(
                Cluster(
                    canonical=canonical,
                    variants=variants_for(canonical),
                    members=members,
                )
            )
        if not clusters_built:
            raise ValueError("resolution response empty after re-attach")

        # Successful refinement.
        return clusters_built, False, "", False

    except _EgressBlocked as exc:
        # D-54: pre-flight egress trip. Algorithmic fallback (already computed).
        # The egress filter already logged a WARNING with hashes-only.
        # We log the fallback decision at INFO; counts only.
        logger.info(
            "redaction.llm_fallback reason=egress_blocked clusters_formed=%d match_count=%d",
            len(algorithmic_clusters),
            exc.result.match_count,
        )
        return algorithmic_clusters, True, "egress_blocked", True

    except Exception as exc:  # noqa: BLE001
        # D-52: network / 5xx / invalid_response / etc → algorithmic fallback.
        # NEVER re-raise (NFR-3). Type name only; never raw values.
        reason = type(exc).__name__
        logger.info(
            "redaction.llm_fallback reason=%s clusters_formed=%d",
            reason,
            len(algorithmic_clusters),
        )
        return algorithmic_clusters, True, reason, False


class RedactionService:
    """v1.0 redaction service — single async public method (D-14).

    The constructor eagerly warms every ``@lru_cache``'d singleton the
    pipeline depends on so the first real request doesn't pay the
    Presidio + spaCy model load (~1-3 s on a cold start).
    """

    def __init__(self) -> None:
        # D-15 eager warm-up — load Presidio engine, Faker(id_ID), and the
        # gender-guesser detector. Each is @lru_cache'd, so subsequent calls
        # from anywhere in the process are O(1) lookups.
        get_analyzer()
        get_faker()
        get_gender_detector()
        logger.info(
            "RedactionService initialised (Presidio + Faker + gender detector loaded)."
        )

    async def _get_thread_lock(self, thread_id: str) -> asyncio.Lock:
        """D-29 (PERF-03): get-or-create the asyncio.Lock for this thread.

        Held briefly under ``_thread_locks_master`` to make get-or-create
        atomic across coroutines (avoids the dict-mutation race where two
        callers both observe ``_thread_locks.get(thread_id) is None`` and
        each create their own lock — losing one and serialising on the
        other). Returned lock is acquired by the caller.
        """
        async with _thread_locks_master:
            lock = _thread_locks.get(thread_id)
            if lock is None:
                lock = asyncio.Lock()
                _thread_locks[thread_id] = lock
            return lock

    @traced(name="redaction.redact_text")
    async def redact_text(
        self,
        text: str,
        registry: ConversationRegistry | None = None,
    ) -> RedactionResult:
        """D-13 / D-14 / D-39: detect + cluster + anonymize. Stateless or
        registry-aware.

        Args:
            text: Raw input text. May contain UUIDs, Indonesian or English
                names, emails, phone numbers, credit-card-like strings, etc.
            registry: When ``None`` (Phase 1 default — D-39), behaviour is
                identical to the stateless legacy path (mode=algorithmic
                pseudo-clusters; no LLM contact; no upsert). When supplied,
                the call is wrapped in a per-thread ``asyncio.Lock``
                (D-29 / D-30) and:
                  - PERSON entities are clustered per
                    ``settings.entity_resolution_mode`` (algorithmic / llm /
                    none — D-45 / D-49 / D-62)
                  - the cloud-LLM path is gated by the egress filter and
                    falls back to algorithmic on any failure (D-52 / D-54)
                  - existing real values reuse their stored surrogate
                    (REG-04)
                  - Faker generation honours both per-call AND per-thread
                    forbidden tokens (D-37)
                  - newly-introduced mappings (canonical + variants) are
                    upserted to the ``entity_registry`` table inside the
                    critical section (D-32 / D-48)

        Returns:
            ``RedactionResult`` with anonymized text, the real -> surrogate
            map for surrogate-bucket entities, the count of hard-redact
            placeholders emitted, and total latency in milliseconds.

        Raises:
            RedactionError: if the input contains the literal sentinel
                substring ``<<UUID_`` (D-11). Surfaced from the UUID
                pre-mask helper inside ``detect_entities``.

        D-84 (Phase 5): when ``PII_REDACTION_ENABLED=false`` this method
        returns an identity ``RedactionResult`` (input text unchanged,
        ``entity_map`` empty, ``hard_redacted_count=0``, ``latency_ms=0.0``)
        BEFORE any ``_get_thread_lock`` acquisition, NER call, or DB I/O.
        Defense-in-depth alongside Plan 05-04's top-level branch in
        ``chat.py``.
        """
        # Phase 5 D-84: lock-free off-mode early return.
        # Defense-in-depth — chat.py top-level branch (Plan 05-04) also gates
        # at the request boundary, but every other future caller of
        # redact_text benefits automatically from this service-layer short-
        # circuit. Runs BEFORE _get_thread_lock and BEFORE any logger /
        # span attribute set, so off-mode produces zero log spam, zero
        # contention, and zero observable PII (T-05-01-1 mitigation).
        # Plan 05-08: D-84 gate sourced from system_settings (DB-backed) instead
        # of config.py. Avoids drift between the chat-router gate and the
        # service-layer gate (both must stay in lock-step — D-83 invariant).
        if not bool(get_system_settings().get("pii_redaction_enabled", True)):
            return RedactionResult(
                anonymized_text=text,
                entity_map={},
                hard_redacted_count=0,
                latency_ms=0.0,
            )
        if registry is None:
            # D-39: stateless legacy path. Phase 1 body unchanged.
            return await self._redact_text_stateless(text)

        # D-29 / D-30 / D-61: per-thread lock spans detect → cluster → LLM-call
        # → generate-surrogates → upsert-deltas. Phase 3 LLM call lives
        # INSIDE the lock per D-61 step 3.
        lock = await self._get_thread_lock(registry.thread_id)
        t_lock_start = time.perf_counter()
        async with lock:
            lock_wait_ms = (time.perf_counter() - t_lock_start) * 1000.0
            size_before = len(registry.entries())
            result = await self._redact_text_with_registry(text, registry)
            size_after = len(registry.entries())
            # D-41 / B4: counts and timings only — NEVER real values.
            logger.debug(
                "redaction.redact_text(registry): thread_id=%s size_before=%d size_after=%d lock_wait_ms=%.2f writes=%d",
                registry.thread_id,
                size_before,
                size_after,
                lock_wait_ms,
                size_after - size_before,
            )
            return result

    @traced(name="redaction.redact_text_batch")
    async def redact_text_batch(
        self,
        texts: list[str],
        registry: ConversationRegistry,
    ) -> list[str]:
        """D-92: single-asyncio.Lock-acquisition batch redaction primitive.

        The Phase 5 chat-loop chokepoint (D-93) calls this ONCE per turn with
        the full prior history + the new user message. Per-string NER runs
        inside one held lock so the entire turn's anonymization is one
        contention window, one batched DB upsert path. Returns anonymized
        strings in the same order as input — D-93 reassembles history by
        index, so order MUST be preserved (T-05-01-2).

        Args:
            texts: ordered list of raw input strings (e.g., history +
                user_message). Empty list returns [] via the fast path.
            registry: per-thread ConversationRegistry, already loaded by the
                caller (Plan 05-04 chat.py event_generator). Required — the
                batch primitive has no stateless mode (use ``redact_text``
                with ``registry=None`` for that).

        Returns:
            anonymized: list of anonymized strings; ``len(anonymized) ==
                len(texts)``; ``anonymized[i]`` is the surrogate-form of
                ``texts[i]``.

        Raises:
            ValueError: if ``registry`` is None.

        Off-mode (Phase 5 D-84): when ``PII_REDACTION_ENABLED=false``,
        returns ``list(texts)`` — a shallow copy with no transformation.
        No lock, no NER, no DB I/O.

        Lock-hold semantics (T-05-01-3 — accepted): for N strings the lock
        is held for the full batch (no release-between-strings). Phase 6
        PERF-02 may revisit if profiling shows multi-second hold times
        block concurrent same-thread turns.
        """
        # D-84 off-mode identity (defense-in-depth alongside redact_text's
        # service-layer gate). Returns a shallow copy via list(...) so the
        # caller cannot accidentally mutate the input through the result.
        # Plan 05-08: sourced from system_settings DB column (admin-toggleable).
        if not bool(get_system_settings().get("pii_redaction_enabled", True)):
            return list(texts)

        # Strict primitive: batch is the chat-loop chokepoint, not the
        # stateless path. Plan 05-04's event_generator always loads a
        # registry before calling this — None means a programming error.
        if registry is None:
            raise ValueError(
                "redact_text_batch requires a loaded ConversationRegistry; "
                "this primitive is the chat-loop chokepoint, not the "
                "stateless path."
            )

        # Empty-input fast path — zero NER, zero lock acquisition.
        if not texts:
            return []

        started = time.perf_counter()
        lock = await self._get_thread_lock(registry.thread_id)
        results: list[str] = []
        hard_redacted_total = 0
        # T-05-01-2 mitigation: single in-order for-loop, no asyncio.gather,
        # no sorting — ``results[i]`` is always the redaction of ``texts[i]``.
        async with lock:
            for t in texts:
                r = await self._redact_text_with_registry(t, registry)
                results.append(r.anonymized_text)
                hard_redacted_total += r.hard_redacted_count
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        # D-41 / B4: counts and timings only — NEVER real values.
        logger.debug(
            "redaction.redact_text_batch: thread_id=%s batch_size=%d "
            "hard_redacted_total=%d ms=%.2f",
            registry.thread_id,
            len(texts),
            hard_redacted_total,
            elapsed_ms,
        )

        # B4 + Phase 1 D-18 + Phase 2 D-41 + T-05-01-4: span attributes
        # are batch_size (int), hard_redacted_total (int), latency_ms
        # (float) ONLY. NEVER input/output text or surrogate values.
        # Tracing MUST NEVER affect functional behavior — try/except
        # mirrors the existing pattern inside _redact_text_with_registry.
        try:
            span = None
            try:
                from opentelemetry import trace as _otel_trace  # type: ignore[import-not-found]

                span = _otel_trace.get_current_span()
                if span is None or not getattr(span, "is_recording", lambda: False)():
                    span = None
            except Exception:
                span = None
            if span is not None:
                span.set_attribute("batch_size", len(texts))
                span.set_attribute("hard_redacted_total", hard_redacted_total)
                span.set_attribute("latency_ms", elapsed_ms)
        except Exception:
            pass  # tracing must NEVER affect functional behavior

        return results

    async def _redact_text_stateless(self, text: str) -> RedactionResult:
        """Phase 1 stateless redact path — registry=None ⇒ no clustering, no
        LLM, no upsert. Each PERSON entity gets its own pseudo-cluster so
        the cluster-aware ``anonymize()`` API still works correctly (D-39:
        identical legacy behaviour from the caller's perspective — same
        return shape, same surrogate properties)."""
        t0 = time.perf_counter()

        # W10: detect_entities returns the masked text it built so we don't
        # double-mask. Entity offsets are relative to masked_text, NOT the
        # original input.
        masked_text, entities, sentinels = detect_entities(text)

        person_entities, non_person_entities = _split_person_non_person(entities)
        # Stateless path: each PERSON entity gets its own pseudo-cluster
        # (no merges, no nickname expansion). Behaviour matches the legacy
        # Phase 1 per-entity path because each cluster has a single member
        # whose canonical equals its own text.
        clusters = _clusters_for_mode_none(person_entities)

        anonymized_masked, entity_map, hard_redacted_count = anonymize(
            masked_text=masked_text,
            clusters=clusters,
            non_person_entities=non_person_entities,
            registry=None,
        )
        anonymized_text = restore_uuids(anonymized_masked, sentinels)

        latency_ms = (time.perf_counter() - t0) * 1000.0

        # D-18 / B4: counts and timings only — never real entity values.
        logger.debug(
            "redaction.redact_text: chars=%d entities=%d surrogates=%d hard=%d uuid_drops=%d ms=%.2f",
            len(text),
            len(entities),
            len(entity_map),
            hard_redacted_count,
            len(sentinels),
            latency_ms,
        )

        return RedactionResult(
            anonymized_text=anonymized_text,
            entity_map=entity_map,
            hard_redacted_count=hard_redacted_count,
            latency_ms=latency_ms,
        )

    async def _redact_text_with_registry(
        self,
        text: str,
        registry: ConversationRegistry,
        _scan_rerun_done: bool = False,  # NEW (D-76 single-re-run cap)
    ) -> RedactionResult:
        """Registry-aware redact path. Caller holds the per-thread lock.

        D-61 8-step flow (verbatim from CONTEXT.md):
            1. (Caller) Acquire per-thread asyncio.Lock.
            2. Detect entities (Presidio two-pass).
            3. Cluster PERSON entities (mode-dispatched: algorithmic / llm /
               none — Phase 3).
            4. Generate Faker surrogates per cluster (Phase 1 collision
               budget preserved by anonymize()).
            5. Compose variant set per cluster (D-48 first-only / last-only /
               honorific-prefixed / nickname).
            6. Compute deltas vs loaded registry; await registry.upsert_delta
               (Phase 2 D-32).
            7. Build entity_map for THIS call's text rewrite using ALL
               variant rows.
            8. (Caller) Release the lock; return RedactionResult.
        """
        t0 = time.perf_counter()

        masked_text, entities, sentinels = detect_entities(text, thread_id=registry.thread_id)

        # Step 3: split PERSON / non-PERSON; cluster PERSON by mode.
        person_entities, non_person_entities = _split_person_non_person(entities)

        settings = get_settings()
        mode = settings.entity_resolution_mode  # 'algorithmic' | 'llm' | 'none'

        # D-63 tracing accumulators. NEVER store raw values here.
        provider_fallback = False
        egress_tripped = False
        fallback_reason = ""

        if mode == "algorithmic":
            clusters = cluster_persons(person_entities)
            clusters_merged_via = "algorithmic"
        elif mode == "none":
            clusters = _clusters_for_mode_none(person_entities)
            clusters_merged_via = "none"
        elif mode == "llm":
            # pre-cluster algorithmically, then ask the LLM to refine.
            # On ANY failure (egress, network, schema mismatch),
            # fall back to algorithmic clusters. Never raises.
            (
                clusters,
                provider_fallback,
                fallback_reason,
                egress_tripped,
            ) = await _resolve_clusters_via_llm(person_entities, registry)
            clusters_merged_via = "llm"
        else:
            raise ValueError(f"unknown entity_resolution_mode: {mode!r}")

        # Steps 4 + 7: cluster-aware Faker dispatch + entity_map build.
        # anonymize() now allocates ONE surrogate per cluster (D-45) — every
        # variant in cluster.members rewrites to the same canonical surrogate.
        anonymized_masked, entity_map, hard_redacted_count = anonymize(
            masked_text=masked_text,
            clusters=clusters,
            non_person_entities=non_person_entities,
            registry=registry,
        )
        anonymized_text = restore_uuids(anonymized_masked, sentinels)

        # ==============================================================
        # Phase 4 D-75: auto-chain missed-PII scan unless this is the re-run
        # pass. Runs INSIDE the per-thread asyncio.Lock the caller holds
        # (lock is acquired in `redact_text` outside this method, so the
        # re-entrant call below does NOT re-acquire — no deadlock).
        # D-76: single-re-run cap — after one re-run, do NOT scan again.
        # ==============================================================
        scan_replacements = 0
        if not _scan_rerun_done:
            scanned_text, scan_replacements = await scan_for_missed_pii(
                anonymized_text, registry
            )
            if scan_replacements > 0 and scanned_text != anonymized_text:
                # D-76 / FR-8.5: full re-run of redact_text on the modified
                # text. Re-entrant call computes a fresh delta + upsert
                # against the new surrogate positions. The
                # `_scan_rerun_done=True` kwarg prevents unbounded recursion
                # (single re-run cap; second pass cannot trigger a third).
                return await self._redact_text_with_registry(
                    scanned_text, registry, _scan_rerun_done=True
                )

        # ==============================================================
        # Step 6: delta computation (D-32 / D-48).
        # PERSON deltas: one row per variant in cluster.variants, all sharing
        # the cluster's canonical surrogate (sub-surrogate write-through).
        # Non-PERSON deltas: existing Phase 2 path — one row per real value.
        # All deltas funnel through registry.upsert_delta which is
        # INSERT … ON CONFLICT (thread_id, real_value_lower) DO NOTHING
        # (D-32 — cross-process race-safe).
        # ==============================================================
        deltas: list[EntityMapping] = []
        seen_lower: set[str] = set()  # de-dupe within this call

        # PERSON variant rows (D-48). The canonical's surrogate lives in
        # entity_map under the canonical real value (anonymize() puts it
        # there even when no variant span was detected for the canonical
        # itself — see anonymization.py).
        for cluster in clusters:
            canonical_surrogate = entity_map.get(cluster.canonical)
            if not canonical_surrogate:
                continue  # defensive: empty cluster (shouldn't happen)
            for variant in cluster.variants:
                vlow = variant.casefold()
                if vlow in seen_lower:
                    continue
                seen_lower.add(vlow)
                if registry.contains_lower(vlow):
                    continue  # already persisted (cross-turn or earlier in this call)
                deltas.append(
                    EntityMapping(
                        real_value=variant,
                        real_value_lower=vlow,
                        surrogate_value=canonical_surrogate,
                        entity_type="PERSON",
                        source_message_id=None,  # Phase 5 chat router backfills
                    )
                )

        # Non-PERSON deltas. anonymize()'s entity_map keys are real values,
        # but we want a per-Entity walk so we can carry the correct
        # entity_type for each delta (W-2 invariant). Build a text→Entity
        # index ONCE so the loop is O(n) instead of O(n*m).
        non_person_index: dict[str, Entity] = {e.text: e for e in non_person_entities}
        for ent_text, ent in non_person_index.items():
            surrogate = entity_map.get(ent_text)
            if surrogate is None:
                continue  # hard-redact / no surrogate emitted
            elow = ent_text.casefold()
            if elow in seen_lower:
                continue
            seen_lower.add(elow)
            if registry.contains_lower(elow):
                continue  # already persisted
            deltas.append(
                EntityMapping(
                    real_value=ent_text,
                    real_value_lower=elow,
                    surrogate_value=surrogate,
                    entity_type=ent.type,
                    source_message_id=None,
                )
            )

        if deltas:
            # D-32: eager upsert inside the critical section. Raises on DB
            # error (REG-04 invariant — losing a write would silently break
            # "same real → same surrogate within thread").
            await registry.upsert_delta(deltas)

        latency_ms = (time.perf_counter() - t0) * 1000.0

        # D-18 / D-41 / B4 / D-63: counts, timings, mode flags ONLY.
        # NEVER real values, NEVER member texts, NEVER cluster canonicals.
        logger.debug(
            "redaction.redact_text(reg): thread_id=%s chars=%d entities=%d "
            "clusters=%d cluster_size_max=%d merged_via=%s "
            "surrogates=%d hard=%d uuid_drops=%d deltas=%d "
            "provider_fallback=%s egress_tripped=%s fallback_reason=%s ms=%.2f",
            registry.thread_id,
            len(text),
            len(entities),
            len(clusters),
            max((len(c.members) for c in clusters), default=0),
            clusters_merged_via,
            len(entity_map),
            hard_redacted_count,
            len(sentinels),
            len(deltas),
            provider_fallback,
            egress_tripped,
            fallback_reason or "-",
            latency_ms,
        )

        # Phase 4 D-63 / B4: span attributes — counts/flags ONLY, never
        # real values. Tracing MUST NEVER affect functional behavior; any
        # exception (no active span, provider not configured, OTel/langfuse
        # not installed) is swallowed.
        try:
            span = None
            try:
                from opentelemetry import trace as _otel_trace  # type: ignore[import-not-found]
                span = _otel_trace.get_current_span()
                if span is None or not getattr(span, "is_recording", lambda: False)():
                    span = None
            except Exception:
                span = None
            if span is not None:
                span.set_attribute(
                    "missed_scan_enabled",
                    bool(get_settings().pii_missed_scan_enabled),
                )
                span.set_attribute(
                    "missed_scan_replacements",
                    int(scan_replacements) if not _scan_rerun_done else 0,
                )
                span.set_attribute("scan_rerun_pass", bool(_scan_rerun_done))
        except Exception:
            pass  # tracing must NEVER affect functional behavior

        return RedactionResult(
            anonymized_text=anonymized_text,
            entity_map=entity_map,
            hard_redacted_count=hard_redacted_count,
            latency_ms=latency_ms,
        )

    @traced(name="redaction.de_anonymize_text")
    async def de_anonymize_text(
        self,
        text: str,
        registry: ConversationRegistry,
        mode: Literal["algorithmic", "llm", "none"] | None = None,  # NEW (D-71)
    ) -> str:
        """3-phase placeholder-tokenized de-anonymization pipeline (D-71..D-74).

        Pass 1: replace each known surrogate with an opaque <<PH_xxxx>> token
                (existing Phase 2 behavior).
        Pass 2: when mode='algorithmic' or 'llm', match remaining text against
                this thread's cluster variants and replace mangled forms with
                the corresponding placeholder (NEW in Phase 4 D-72).
        Pass 3: replace each <<PH_xxxx>> with its real value (existing Phase 2
                behavior).

        When mode='none' (default per Settings.fuzzy_deanon_mode), Pass 2 is
        skipped — behavior is identical to Phase 2 (DEANON-01 / DEANON-02 hold).

        Pass 1 sorts registry entries by ``len(surrogate_value)`` DESC then by
        ``len(real_value)`` DESC so the longest surrogate match wins, which
        prevents partial-overlap corruption when surrogates share token prefixes
        and ensures D-48 sub-surrogate variants don't shadow canonical real
        values during placeholder→real mapping.

        D-35 / D-74: hard-redact placeholders (``[CREDIT_CARD]``, ``[US_SSN]``,
        etc.) pass through unchanged in all 3 modes because they are NEVER in
        the registry (Phase 2 D-24 / REG-05) — Pass 1 cannot mint a placeholder
        for them; Pass 2 variants come from the registry and cannot include
        them; Pass 3 only resolves <<PH_xxxx>> tokens.

        Args:
            text: surrogate-bearing text from the LLM.
            registry: per-thread ConversationRegistry (already loaded; no DB
                I/O happens in this method).
            mode: optional explicit override per D-71 — None resolves to
                Settings.fuzzy_deanon_mode (default 'none').

        Returns:
            Same text with surrogates resolved to real values; hard-redact
            ``[ENTITY_TYPE]`` placeholders survive unchanged in all modes
            (D-74 — structural per Phase 2 D-24).
        """
        # Phase 4 D-71: resolve effective mode (param wins; falls back to
        # Settings.fuzzy_deanon_mode, which 60s-TTL cached per Phase 2 D-21).
        settings = get_settings()
        if mode is None:
            mode = settings.fuzzy_deanon_mode  # 'algorithmic' | 'llm' | 'none'
        threshold = settings.fuzzy_deanon_threshold

        t0 = time.perf_counter()
        entries = registry.entries()
        # Sort by len(surrogate_value) DESC — longest surrogate match wins
        # (prevents partial-overlap corruption across DIFFERENT clusters whose
        # surrogates share token prefixes).
        # Tie-break by len(real_value) DESC so canonical real values win over
        # D-48 sub-surrogate variants (first-only / last-only / honorific-
        # prefixed / nickname). All variants in a cluster share ONE
        # surrogate_value (D-45) — without the tie-break, Pass 1 would
        # non-deterministically map the surrogate to a variant's real value
        # like "Maria" instead of the canonical "Maria Santos".
        entries_sorted = sorted(
            entries,
            key=lambda m: (len(m.surrogate_value), len(m.real_value)),
            reverse=True,
        )

        # Pass 1: surrogate -> placeholder token (case-insensitive per DEANON-02).
        out = text
        placeholders: dict[str, str] = {}
        for i, m in enumerate(entries_sorted):
            # Zero-padded width 4 (Claude's Discretion §2 — lexicographic
            # stability in tracing).
            token = f"<<PH_{i:04d}>>"
            out, n = re.subn(
                re.escape(m.surrogate_value),
                token,
                out,
                flags=re.IGNORECASE,
            )
            if n > 0:
                placeholders[token] = m.real_value  # original casing (D-36)

        # Phase 4 D-72: Pass 2 — fuzzy/LLM-match against UNREPLACED variants.
        # mode='none' bypasses Pass 2 entirely — Phase 2 behavior preserved.
        fuzzy_matches_resolved = 0
        fuzzy_provider_fallback = False
        if mode == "algorithmic":
            out, fuzzy_matches_resolved = self._fuzzy_match_algorithmic(
                out, registry, placeholders, threshold
            )
        elif mode == "llm":
            out, fuzzy_matches_resolved, fuzzy_provider_fallback = (
                await self._fuzzy_match_llm(out, registry, placeholders)
            )
        # else mode == "none" → skip Pass 2 entirely.

        # Pass 3: placeholder -> real_value.
        resolved = 0
        for token, real in placeholders.items():
            out, n = re.subn(re.escape(token), real, out)
            resolved += n

        latency_ms = (time.perf_counter() - t0) * 1000.0
        # D-18 / D-41 / D-63 / B4: counts, timings, and mode strings ONLY.
        # NEVER real values, surrogate values, or matched span text — the
        # backing tracing provider (langsmith/langfuse/none) gets these as
        # span attributes via the @traced decorator's structured-log path.
        logger.debug(
            "redaction.de_anonymize_text: thread_id=%s text_len=%d surrogate_count=%d "
            "placeholders_resolved=%d fuzzy_deanon_mode=%s "
            "fuzzy_matches_resolved=%d fuzzy_provider_fallback=%s ms=%.2f",
            registry.thread_id,
            len(text),
            len(entries),
            resolved,
            mode,
            fuzzy_matches_resolved,
            fuzzy_provider_fallback,
            latency_ms,
        )
        return out

    # ------------------------------------------------------------------
    # Phase 4 D-72 / D-73 / D-74 / D-78: Pass 2 helpers.
    # ------------------------------------------------------------------

    def _fuzzy_match_algorithmic(
        self,
        text: str,
        registry: ConversationRegistry,
        placeholders: dict[str, str],
        threshold: float,
    ) -> tuple[str, int]:
        """D-72 algorithmic Pass 2: per-cluster Jaro-Winkler match against the
        thread's surrogate variants; replace mangled chunks with the cluster's
        ``<<PH_xxxx>>`` token. Returns ``(modified_text, replacement_count)``.

        D-68 per-cluster scoping: variants live in clusters keyed by
        ``EntityMapping.cluster_id`` (Phase 3 D-48). Entries whose
        ``cluster_id`` is None (non-PERSON / unclustered PERSON) form solo
        clusters keyed on the casefolded real value so they still benefit
        from a fuzzy lookup against their own surrogate without cross-talk.

        D-74 hard-redact survival: the chunk iterator skips any token that
        already matches a placeholder (``<<PH_xxxx>>``) or a hard-redact
        bracket form (``[ENTITY_TYPE]``) — belt-and-suspenders. Hard-redact
        placeholders are never minted in Pass 1 because they are NEVER in
        the registry (Phase 2 D-24 / REG-05), so they cannot be reverse-
        looked-up here either.
        """
        from collections import defaultdict

        if not placeholders:
            return text, 0

        # Build the cluster -> [variants] map AND surrogate -> placeholder
        # reverse-lookup ONCE. We walk the registry entries dict-of-dicts
        # rather than calling registry.lookup per chunk to keep Pass 2 O(N)
        # in cluster size.
        clusters: dict[str, list[str]] = defaultdict(list)
        surrogate_to_placeholder: dict[str, str] = {}

        # Reverse-lookup the placeholder -> surrogate. The placeholders dict
        # maps token -> real_value (Pass 1 stored real values for casing
        # preservation in Pass 3); we recover the surrogate via registry.
        all_entries = registry.entries()
        for ph_token, real_value in placeholders.items():
            real_lower = real_value.casefold()
            for ent in all_entries:
                if ent.real_value.casefold() == real_lower:
                    cluster_key = (
                        getattr(ent, "cluster_id", None)
                        or f"_solo_{real_lower}"
                    )
                    if ent.surrogate_value not in clusters[cluster_key]:
                        clusters[cluster_key].append(ent.surrogate_value)
                    surrogate_to_placeholder[ent.surrogate_value.casefold()] = (
                        ph_token
                    )
                    break

        if not clusters:
            return text, 0

        placeholder_re = re.compile(r"^<<PH_[0-9a-f]+>>$")
        hard_redact_re = re.compile(r"^\[[A-Z_]+\]$")

        # Right-to-left replacement to preserve offsets across multiple matches.
        span_replacements: list[tuple[int, int, str]] = []
        for chunk_match in re.finditer(r"\S+", text):
            chunk = chunk_match.group(0)
            if placeholder_re.match(chunk):
                continue  # already a Pass-1 placeholder; never re-resolve
            if hard_redact_re.match(chunk):
                continue  # D-74 belt-and-suspenders: hard-redacts are inert
            for variants in clusters.values():
                result = best_match(chunk, variants, threshold=threshold)
                if result is None:
                    continue
                matched_variant, _score = result
                ph_token = surrogate_to_placeholder.get(
                    matched_variant.casefold()
                )
                if ph_token is None:
                    continue
                span_replacements.append(
                    (chunk_match.start(), chunk_match.end(), ph_token)
                )
                break  # first matching cluster wins for this chunk

        if not span_replacements:
            return text, 0

        out = text
        for start, end, ph in sorted(span_replacements, key=lambda r: -r[0]):
            out = out[:start] + ph + out[end:]
        return out, len(span_replacements)

    async def _fuzzy_match_llm(
        self,
        text: str,
        registry: ConversationRegistry,
        placeholders: dict[str, str],
    ) -> tuple[str, int, bool]:
        """D-72 / D-73 LLM Pass 2: ask the configured LLM provider to identify
        mangled-surrogate spans and map each to its ``<<PH_xxxx>>`` token.

        Returns ``(modified_text, replacement_count, fell_back)``. ``fell_back``
        is True when the LLM call failed AND fallback was attempted.

        D-78 soft-fail: on ``_EgressBlocked``, ``ValidationError`` or any other
        ``Exception``, this method NEVER re-raises — it logs a WARNING with
        ``error_class`` only (B4 invariant — no payload, no spans, no values)
        and either falls back to the algorithmic branch (when
        ``settings.llm_provider_fallback_enabled=True`` per D-52) or returns
        the text unchanged (skipping Pass 2 entirely).

        D-73 cloud-payload invariant: the prompt's user content carries the
        Pass-1-output text (where every known surrogate is ALREADY replaced
        by an opaque ``<<PH_xxxx>>`` token) plus a JSON list of cluster
        variants — all surrogate-form strings. The cloud sees ZERO raw real
        values. ``LLMProviderClient.call`` runs the Phase 3 D-53..D-56
        egress filter as defense-in-depth.

        D-73 token-spoofing mitigation: the response is Pydantic-validated
        via ``_FuzzyMatchResponse`` (regex-pinned token shape), and the
        server then asserts each returned token is a member of the Pass-1
        ``placeholders`` dict — fabricated tokens are silently dropped, so
        the LLM cannot inject a foreign-cluster mapping.
        """
        if not placeholders:
            return text, 0, False

        # Build cluster variants payload (D-73 — surrogate-form only).
        clusters_by_token: dict[str, dict] = {}
        all_entries = registry.entries()
        for ph_token, real_value in placeholders.items():
            real_lower = real_value.casefold()
            for ent in all_entries:
                if ent.real_value.casefold() == real_lower:
                    if ph_token not in clusters_by_token:
                        clusters_by_token[ph_token] = {
                            "token": ph_token,
                            "canonical": ent.surrogate_value,
                            "variants": [ent.surrogate_value],
                        }
                    elif ent.surrogate_value not in clusters_by_token[ph_token][
                        "variants"
                    ]:
                        clusters_by_token[ph_token]["variants"].append(
                            ent.surrogate_value
                        )
                    break

        if not clusters_by_token:
            return text, 0, False

        variant_payload = list(clusters_by_token.values())
        messages = [
            {
                "role": "system",
                "content": (
                    "Identify each instance in the user text where a slightly "
                    "mangled form of a known cluster variant appears, and map "
                    "it to that cluster's token. Reply ONLY with JSON in the "
                    'form {"matches":[{"span":"<exact substring of user '
                    'text>","token":"<<PH_xxxx>>"}]}. The placeholders '
                    "<<PH_xxxx>> in the user text are opaque tokens you must "
                    "preserve unchanged; map only NEW mangled forms NOT "
                    "already replaced. Use only tokens from the provided "
                    "cluster list. Do not invent tokens. If nothing matches, "
                    'reply with {"matches":[]}.'
                ),
            },
            {
                "role": "user",
                "content": (
                    "Text:\n"
                    f"{text}\n\n"
                    "Clusters (JSON):\n"
                    f"{json.dumps(variant_payload, ensure_ascii=False)}"
                ),
            },
        ]

        settings = get_settings()
        client = LLMProviderClient()
        try:
            result = await client.call(
                feature="fuzzy_deanon",
                messages=messages,
                registry=registry,
                provisional_surrogates=None,  # D-56: no provisional set for de-anon
            )
            parsed = _FuzzyMatchResponse.model_validate(result)
        except _EgressBlocked:
            # B4 invariant: error_class only — never payload or registry contents.
            logger.warning(
                "event=fuzzy_deanon_skipped feature=fuzzy_deanon "
                "error_class=_EgressBlocked"
            )
            if settings.llm_provider_fallback_enabled:
                out, n = self._fuzzy_match_algorithmic(
                    text, registry, placeholders, settings.fuzzy_deanon_threshold
                )
                return out, n, True
            return text, 0, True
        except (ValidationError, Exception) as exc:  # noqa: BLE001 — D-78 catch-all
            logger.warning(
                "event=fuzzy_deanon_skipped feature=fuzzy_deanon "
                "error_class=%s",
                type(exc).__name__,
            )
            if settings.llm_provider_fallback_enabled:
                out, n = self._fuzzy_match_algorithmic(
                    text, registry, placeholders, settings.fuzzy_deanon_threshold
                )
                return out, n, True
            return text, 0, True

        # Server-side validation: each token MUST be a key in Pass-1's
        # placeholders dict. Tokens not present are silently dropped (D-73
        # — LLM cannot inject foreign tokens). Hard-redact bracket spans
        # are also dropped as belt-and-suspenders (D-74).
        valid_tokens = set(placeholders.keys())
        out = text
        replacements = 0
        for match in parsed.matches:
            if match.token not in valid_tokens:
                continue
            if re.fullmatch(r"\[[A-Z_]+\]", match.span):
                continue
            new_text, n = re.subn(re.escape(match.span), match.token, out)
            out = new_text
            replacements += n
        return out, replacements, False


@lru_cache
def get_redaction_service() -> RedactionService:
    """D-15 singleton getter; lifespan calls this once at startup.

    Returns:
        The process-wide ``RedactionService`` instance. The constructor
        loads Presidio + Faker + the gender detector, so the first call is
        slow (~1-3 s); subsequent calls are O(1).
    """
    return RedactionService()
