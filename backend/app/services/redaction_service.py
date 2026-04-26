"""Public RedactionService — composes detection + anonymization (D-13..D-15).

This is the single entry point for Phase 1's PII redaction layer. It glues
together the four building blocks shipped earlier in the phase:

- ``uuid_filter`` (Plan 04) — pre-mask UUIDs so Presidio never touches them.
- ``detection`` (Plan 05) — Presidio + spaCy ``xx_ent_wiki_sm`` two-pass
  threshold filter; returns ``(masked_text, entities, sentinels)``.
- ``anonymization`` (Plan 06 — this plan) — substitutes each entity with a
  Faker surrogate or a ``[TYPE]`` placeholder.
- ``tracing_service`` (Plan 01) — provides the ``@traced`` decorator.

Design invariants:

- W10: ``redact_text`` calls ``detect_entities`` exactly once and uses the
  returned 3-tuple directly. The UUID-masking helper is NOT called from
  here — it lives inside ``detect_entities``. This file imports only
  ``restore_uuids``.
- D-13: public method is ``async def redact_text(text) -> RedactionResult``.
  Phase 2 will widen the signature to accept a registry; the async shape is
  stable for that future.
- D-14: Phase 1 is stateless — no per-conversation registry, no thread
  parameter, no caching of real values across calls.
- D-15: ``get_redaction_service()`` is ``@lru_cache``'d. The FastAPI lifespan
  calls it once at startup so Presidio + Faker + gender detector are loaded
  before the first chat request (PERF-01).
- D-18: ``redact_text`` is wrapped in ``@traced(name="redaction.redact_text")``
  for OBS-01. Span attributes are counts and timings only — never real
  entity values (B4).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from functools import lru_cache

from pydantic import BaseModel, ConfigDict

from app.services.redaction.anonymization import (
    anonymize,
    get_faker,
    get_gender_detector,
)
from app.services.redaction.detection import detect_entities, get_analyzer
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
_thread_locks: dict[str, asyncio.Lock] = {}
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


class RedactionService:
    """Phase 1 redaction service — stateless, single async public method (D-14).

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
        """D-13 / D-14 / D-39: detect + anonymize. Stateless or registry-aware.

        Args:
            text: Raw input text. May contain UUIDs, Indonesian or English
                names, emails, phone numbers, credit-card-like strings, etc.
            registry: When ``None`` (Phase 1 default — D-39), behaviour is
                identical to the stateless legacy path. When supplied, the
                call is wrapped in a per-thread ``asyncio.Lock`` (D-29 / D-30)
                and:
                  - existing real values reuse their stored surrogate (REG-04)
                  - Faker generation honours both per-call AND per-thread
                    forbidden tokens (D-37)
                  - newly-introduced mappings are upserted to the
                    ``entity_registry`` table inside the critical section
                    (D-32).

        Returns:
            ``RedactionResult`` with anonymized text, the real -> surrogate
            map for surrogate-bucket entities, the count of hard-redact
            placeholders emitted, and total latency in milliseconds.

        Raises:
            RedactionError: if the input contains the literal sentinel
                substring ``<<UUID_`` (D-11). Surfaced from the UUID
                pre-mask helper inside ``detect_entities``.
        """
        # TODO(Phase 5): gate `if not get_settings().pii_redaction_enabled:
        # return RedactionResult(anonymized_text=text, entity_map={},
        #                        hard_redacted_count=0, latency_ms=0.0)`
        # Phase 1 ships the flag in Settings (Plan 02) for forward-compat
        # with Phase 5 SC#5; the gate goes here, not in callers, so every
        # downstream consumer benefits automatically.
        if registry is None:
            # D-39: stateless legacy path. Phase 1 body unchanged.
            return await self._redact_text_stateless(text)

        # D-29 / D-30: per-thread lock spans detect → generate → upsert.
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

    async def _redact_text_stateless(self, text: str) -> RedactionResult:
        """Phase 1 stateless redact path — body unchanged from the original
        ``redact_text`` (D-39: registry=None ⇒ identical legacy behaviour).
        """
        t0 = time.perf_counter()

        # W10: detect_entities returns the masked text it built so we don't
        # double-mask. Entity offsets are relative to masked_text, NOT the
        # original input.
        masked_text, entities, sentinels = detect_entities(text)

        anonymized_masked, entity_map, hard_redacted_count = anonymize(
            masked_text, entities
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
    ) -> RedactionResult:
        """Registry-aware redact path. Caller holds the per-thread lock.

        Mirrors the body of ``_redact_text_stateless`` but threads ``registry``
        into ``anonymize(...)`` so existing surrogates are reused and
        forbidden tokens honour ``registry.forbidden_tokens()`` (Plan 05
        Task 1). Then computes the delta (entries in ``entity_map`` whose
        ``real_value_lower`` is not already in ``registry._by_lower``) and
        persists it via ``await registry.upsert_delta(deltas)`` (D-32).

        W-2 invariant: every delta carries the correct Presidio
        ``entity_type`` derived from the same call's ``entities`` list. We
        build a ``text → Entity`` index ONCE so the delta loop is O(n)
        (instead of an O(n*m) ``next(...)`` linear scan) and assert the
        index lookup never misses (Phase 1's anonymize() contract guarantees
        every ``entity_map`` key is precisely an ``Entity.text`` from the
        same call — Plan 05 Task 1 preserves this for the registry-hit path
        too).
        """
        t0 = time.perf_counter()

        masked_text, entities, sentinels = detect_entities(text)

        # Phase 2 swap: pass `registry=` so anonymize() reuses existing
        # surrogates and expands the forbidden-token set thread-wide.
        anonymized_masked, entity_map, hard_redacted_count = anonymize(
            masked_text, entities, registry=registry
        )
        anonymized_text = restore_uuids(anonymized_masked, sentinels)

        # === Delta computation (W-2) ===
        # entity_map keys are real values. Build a text→Entity index ONCE
        # so the delta loop is O(n) instead of O(n*m).
        entity_index: dict[str, "Entity"] = {e.text: e for e in entities}

        deltas: list[EntityMapping] = []
        for real_value, surrogate in entity_map.items():
            real_lower = real_value.casefold()
            if real_lower in registry._by_lower:
                # Already persisted — registry.lookup() hit during anonymize().
                continue
            ent = entity_index.get(real_value)
            # Invariant: anonymize() never produces an entity_map key that
            # isn't an Entity.text in `entities`. If this assertion fires,
            # anonymize() has regressed (Phase 1 D-07 contract violation) —
            # surface, do not mask with "UNKNOWN".
            assert ent is not None, (
                f"anonymize() produced entity_map key with no matching Entity: "
                f"thread_id={registry.thread_id!r} key_len={len(real_value)}"
            )
            deltas.append(
                EntityMapping(
                    real_value=real_value,
                    real_value_lower=real_lower,
                    surrogate_value=surrogate,
                    entity_type=ent.type,
                    source_message_id=None,  # Phase 5 chat router backfills
                )
            )
        if deltas:
            # D-32: eager upsert inside the critical section. Raises on DB
            # error (REG-04 invariant — losing a write would silently break
            # "same real → same surrogate within thread").
            await registry.upsert_delta(deltas)

        latency_ms = (time.perf_counter() - t0) * 1000.0

        # D-18 / D-41 / B4: counts and timings only — never real values.
        logger.debug(
            "redaction.redact_text(reg): chars=%d entities=%d surrogates=%d hard=%d uuid_drops=%d deltas=%d ms=%.2f",
            len(text),
            len(entities),
            len(entity_map),
            hard_redacted_count,
            len(sentinels),
            len(deltas),
            latency_ms,
        )

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
    ) -> str:
        """D-34: 1-phase placeholder-tokenized round-trip (DEANON-01 / DEANON-02).

        Forward-compat with Phase 4's 3-phase fuzzy upgrade (FR-5.4) — Phase 4
        will insert its placeholder-tokenized fuzzy-match pass BETWEEN the
        existing two passes (surrogate→placeholder, placeholder→real) without
        rewriting this call site.

        Algorithm:
          1. Sort registry entries by ``len(surrogate_value)`` DESC — guarantees
             longest match wins, prevents partial-overlap corruption when
             surrogates share token prefixes (e.g. "Bambang Sutrisno" must be
             replaced before "Bambang").
          2. Pass 1: surrogate → placeholder token (case-insensitive per
             DEANON-02 via ``re.IGNORECASE``).
          3. Pass 2: placeholder → real_value (original casing preserved per
             D-36).

        D-35: hard-redact placeholders (``[CREDIT_CARD]``, ``[US_SSN]``, etc.)
        pass through unchanged because they are NEVER in the registry (D-24 /
        REG-05). They are simply not matched by Pass 1.
        """
        t0 = time.perf_counter()
        entries = registry.entries()
        # Sort by len(surrogate_value) DESC — longest match wins.
        entries_sorted = sorted(
            entries,
            key=lambda m: len(m.surrogate_value),
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

        # Pass 2: placeholder -> real_value.
        resolved = 0
        for token, real in placeholders.items():
            out, n = re.subn(re.escape(token), real, out)
            resolved += n

        latency_ms = (time.perf_counter() - t0) * 1000.0
        # D-41 / B4: counts and timings only — NEVER real values.
        logger.debug(
            "redaction.de_anonymize_text: text_len=%d surrogate_count=%d placeholders_resolved=%d ms=%.2f",
            len(text),
            len(entries),
            resolved,
            latency_ms,
        )
        return out


@lru_cache
def get_redaction_service() -> RedactionService:
    """D-15 singleton getter; lifespan calls this once at startup.

    Returns:
        The process-wide ``RedactionService`` instance. The constructor
        loads Presidio + Faker + the gender detector, so the first call is
        slow (~1-3 s); subsequent calls are O(1).
    """
    return RedactionService()
