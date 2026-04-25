"""PII detection via Presidio AnalyzerEngine + spaCy xx_ent_wiki_sm.

Phase 1 (PII-01..05) responsibilities:
- D-01: NLP engine = spaCy xx_ent_wiki_sm (multilingual, Indonesian-friendly).
- D-03: two-pass thresholds - surrogate bucket >= 0.7, redact bucket >= 0.3.
- D-09: UUID pre-mask before NER so document IDs never appear as entities.
- D-15: @lru_cache singleton; lifespan calls get_analyzer() at startup so the
  first chat request is hot.
- D-18: every detect call traced via @traced(name="redaction.detect"); span
  attributes are counts only, never real values.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from pydantic import BaseModel
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from app.config import get_settings
from app.services.redaction.uuid_filter import apply_uuid_mask
from app.services.tracing_service import traced

logger = logging.getLogger(__name__)

# Presidio entity-type buckets (resolved at module load from Settings).
_SETTINGS = get_settings()


def _split_csv(value: str) -> set[str]:
    return {item.strip().upper() for item in value.split(",") if item.strip()}


_SURROGATE_BUCKET: set[str] = _split_csv(_SETTINGS.pii_surrogate_entities)
_REDACT_BUCKET: set[str] = _split_csv(_SETTINGS.pii_redact_entities)
_ALL_BUCKET: set[str] = _SURROGATE_BUCKET | _REDACT_BUCKET


class Entity(BaseModel):
    """A detected PII span after threshold filtering."""

    type: str
    start: int
    end: int
    score: float
    text: str
    bucket: str  # "surrogate" or "redact"


@lru_cache
def get_analyzer() -> AnalyzerEngine:
    """Lazy singleton: build AnalyzerEngine with xx_ent_wiki_sm spaCy model.

    Configuration:
    - NLP engine: spaCy xx_ent_wiki_sm (multilingual, ~12MB).
    - Default recognizers enabled (PERSON, EMAIL_ADDRESS, PHONE_NUMBER, etc.).

    The model file must be downloaded once via:
        python -m spacy download xx_ent_wiki_sm
    On Railway this is part of the build hook (see Plan 03 SUMMARY).
    """
    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "xx", "model_name": "xx_ent_wiki_sm"}],
    }
    provider = NlpEngineProvider(nlp_configuration=nlp_config)
    nlp_engine = provider.create_engine()
    analyzer = AnalyzerEngine(
        nlp_engine=nlp_engine,
        supported_languages=["xx"],
    )
    logger.info("Presidio analyzer initialised with xx_ent_wiki_sm model.")
    return analyzer


@traced(name="redaction.detect")
def detect_entities(text: str) -> tuple[str, list[Entity], dict[str, str]]:
    """Detect PII entities in `text` with two-pass thresholds.

    Steps:
      1. Pre-mask UUIDs (D-09): produces masked_text + sentinels map.
      2. Run Presidio analyzer once on masked_text, requesting all bucket
         entity types at the LOWER threshold (`pii_redact_score_threshold`).
      3. Filter results into the two buckets:
         - surrogate-bucket entity & score >= surrogate_threshold -> kept
         - redact-bucket entity & score >= redact_threshold       -> kept
         - everything else dropped.
      4. Return (masked_text, entities, sentinels). RedactionService passes
         `masked_text` directly to `anonymize` and `sentinels` to
         `restore_uuids` after substitution — eliminates a redundant second
         call to `apply_uuid_mask` (W10).

    Args:
        text: Raw input text. May contain UUIDs.

    Returns:
        (masked_text, entities, sentinels). `entities` is sorted by start
        offset and offsets reference `masked_text`. `sentinels` is the dict
        produced by uuid_filter.apply_uuid_mask.
    """
    t0 = time.perf_counter()

    masked_text, sentinels = apply_uuid_mask(text)

    analyzer = get_analyzer()
    settings = get_settings()
    low_threshold = settings.pii_redact_score_threshold
    high_threshold = settings.pii_surrogate_score_threshold

    raw_results = analyzer.analyze(
        text=masked_text,
        entities=sorted(_ALL_BUCKET),
        language="xx",
        score_threshold=low_threshold,
    )

    entities: list[Entity] = []
    for r in raw_results:
        et = r.entity_type.upper()
        if et in _SURROGATE_BUCKET:
            if r.score < high_threshold:
                continue
            bucket = "surrogate"
        elif et in _REDACT_BUCKET:
            if r.score < low_threshold:
                continue
            bucket = "redact"
        else:
            # Defensive: Presidio returned an entity type not in either bucket.
            continue

        entities.append(
            Entity(
                type=et,
                start=r.start,
                end=r.end,
                score=float(r.score),
                text=masked_text[r.start:r.end],
                bucket=bucket,
            )
        )

    entities.sort(key=lambda e: e.start)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.debug(
        "redaction.detect: input_chars=%d uuid_drops=%d entities=%d surrogate=%d redact=%d elapsed_ms=%.2f",
        len(text),
        len(sentinels),
        len(entities),
        sum(1 for e in entities if e.bucket == "surrogate"),
        sum(1 for e in entities if e.bucket == "redact"),
        elapsed_ms,
    )

    return masked_text, entities, sentinels
