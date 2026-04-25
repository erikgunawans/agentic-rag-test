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

import logging
import time
from functools import lru_cache

from pydantic import BaseModel, ConfigDict

from app.services.redaction.anonymization import (
    anonymize,
    get_faker,
    get_gender_detector,
)
from app.services.redaction.detection import detect_entities, get_analyzer

# W10: the UUID pre-mask helper is intentionally NOT imported here. It is
# called exactly once per ``redact_text`` invocation, from inside
# ``detect_entities``, and the resulting sentinel map is threaded back
# through this module via the 3-tuple return. We only need ``restore_uuids``
# to put the original UUIDs back after substitution.
from app.services.redaction.uuid_filter import restore_uuids
from app.services.tracing_service import traced

logger = logging.getLogger(__name__)


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

    @traced(name="redaction.redact_text")
    async def redact_text(self, text: str) -> RedactionResult:
        """D-13: detect + anonymize. Phase 1 stateless.

        Args:
            text: Raw input text. May contain UUIDs, Indonesian or English
                names, emails, phone numbers, credit-card-like strings, etc.

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


@lru_cache
def get_redaction_service() -> RedactionService:
    """D-15 singleton getter; lifespan calls this once at startup.

    Returns:
        The process-wide ``RedactionService`` instance. The constructor
        loads Presidio + Faker + the gender detector, so the first call is
        slow (~1-3 s); subsequent calls are O(1).
    """
    return RedactionService()
