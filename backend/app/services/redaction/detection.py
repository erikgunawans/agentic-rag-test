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
from presidio_analyzer.predefined_recognizers import (
    CreditCardRecognizer,
    CryptoRecognizer,
    DateRecognizer,
    EmailRecognizer,
    IbanRecognizer,
    IpRecognizer,
    MedicalLicenseRecognizer,
    PhoneRecognizer,
    UrlRecognizer,
    UsBankRecognizer,
    UsItinRecognizer,
    UsLicenseRecognizer,
    UsPassportRecognizer,
    UsSsnRecognizer,
)

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


# Country adjectives, language names, and government regulatory acronyms
# identify groups, not individuals — they pollute the registry and trip
# egress on legitimate platform content (the system prompt itself mentions
# "Indonesian"). Cities are DELIBERATELY excluded: "Jakarta" can appear in
# real personal addresses, where a false negative on the address is worse
# than a false positive on the bare city name.
_DENY_LIST_CASEFOLD: frozenset[str] = frozenset({
    # Country (noun + adjective + plural)
    "indonesia",
    "indonesian",
    "indonesians",
    # Language names
    "bahasa",
    "bahasa indonesia",
    "english",
    # Government / regulatory entities
    "ojk",
    "bi",
    "kpk",
    "bpk",
    "mahkamah agung",
    # Legal codes / regulatory acronyms
    "uu pdp",
    "bjr",
    "kuhp",
    "kuhap",
    "uu ite",
    "uupk",
})


def _is_domain_term(span_text: str) -> bool:
    return span_text.casefold() in _DENY_LIST_CASEFOLD


class Entity(BaseModel):
    """A detected PII span after threshold filtering."""

    type: str
    start: int
    end: int
    score: float
    text: str
    bucket: str  # "surrogate" or "redact"


class _PhoneRecognizerXX(PhoneRecognizer):
    """PhoneRecognizer variant that emits a higher confidence score on match.

    Rationale: the upstream PhoneRecognizer hard-codes ``SCORE = 0.4`` and relies
    on Presidio's ``LemmaContextAwareEnhancer`` to lift the score above the
    surrogate threshold (``pii_surrogate_score_threshold = 0.7``) by matching
    nearby context words like "phone" / "telephone" / "mobile". The lemma
    enhancer requires the spaCy NLP engine to produce token lemmas — which the
    multilingual ``xx_ent_wiki_sm`` model does not (it is NER-only). As a
    result, every phone number scores exactly 0.4 under language=xx and is
    silently dropped by the two-pass threshold filter.

    A python-phonenumbers match that successfully parses to a number whose
    region is in our ``supported_regions`` list is high-quality evidence of a
    real phone number. Bumping the score to ``0.75`` (just over the surrogate
    threshold) makes those matches survive the filter and become Faker
    surrogates per Phase 1 SC#1 / FR-2.5.
    """

    SCORE = 0.75


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

    # Presidio's default RecognizerRegistry registers pattern-based recognizers
    # (PhoneRecognizer, CreditCardRecognizer, UsSsnRecognizer, etc.) for
    # `language="en"` only. Because we query `language="xx"` (D-01: multilingual
    # spaCy NER for Indonesian-friendly NER), those pattern recognizers are
    # silently skipped — leaving CREDIT_CARD, US_SSN, IBAN_CODE, PHONE_NUMBER,
    # etc. undetected on every Indonesian chat input. Re-register the relevant
    # pattern recognizers under `supported_language="xx"` so they fire on the
    # masked text. (Plan 06 SUMMARY follow-up #1; surrogate + redact buckets
    # both depend on these.)
    #
    # PhoneRecognizer note: it accepts `supported_regions` controlling which
    # phonenumbers ISO regions to validate against. The library's default
    # ('US', 'UK', 'DE', 'FE', 'IL', 'IN', 'CA', 'BR') omits 'ID' (Indonesia),
    # so Indonesian +62 numbers are not validated. We pass an explicit list
    # including 'ID' and a few common regions present in the legal corpus.
    xx_pattern_recognizers = [
        ("EmailRecognizer", lambda: EmailRecognizer(supported_language="xx")),
        (
            "PhoneRecognizer",
            lambda: _PhoneRecognizerXX(
                supported_language="xx",
                supported_regions=("ID", "US", "UK", "IN"),
            ),
        ),
        ("UrlRecognizer", lambda: UrlRecognizer(supported_language="xx")),
        ("IpRecognizer", lambda: IpRecognizer(supported_language="xx")),
        ("DateRecognizer", lambda: DateRecognizer(supported_language="xx")),
        ("CreditCardRecognizer", lambda: CreditCardRecognizer(supported_language="xx")),
        ("IbanRecognizer", lambda: IbanRecognizer(supported_language="xx")),
        ("UsSsnRecognizer", lambda: UsSsnRecognizer(supported_language="xx")),
        ("UsItinRecognizer", lambda: UsItinRecognizer(supported_language="xx")),
        ("UsBankRecognizer", lambda: UsBankRecognizer(supported_language="xx")),
        ("UsPassportRecognizer", lambda: UsPassportRecognizer(supported_language="xx")),
        ("UsLicenseRecognizer", lambda: UsLicenseRecognizer(supported_language="xx")),
        (
            "MedicalLicenseRecognizer",
            lambda: MedicalLicenseRecognizer(supported_language="xx"),
        ),
        ("CryptoRecognizer", lambda: CryptoRecognizer(supported_language="xx")),
    ]
    registered: list[str] = []
    failed: list[str] = []
    for name, factory in xx_pattern_recognizers:
        try:
            analyzer.registry.add_recognizer(factory())
            registered.append(name)
        except Exception as exc:  # noqa: BLE001 — defensive across Presidio versions
            failed.append(name)
            logger.warning(
                "Presidio recognizer %s failed to register for language=xx: %s",
                name,
                exc,
            )

    logger.info(
        "Presidio analyzer initialised with xx_ent_wiki_sm model "
        "(xx pattern recognizers registered=%d failed=%d).",
        len(registered),
        len(failed),
    )
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
    denied_count = 0
    denied_types: set[str] = set()
    for r in raw_results:
        et = r.entity_type.upper()
        span_text = masked_text[r.start:r.end]

        # Counts + types only in telemetry (B4 invariant — no raw values).
        if _is_domain_term(span_text):
            denied_count += 1
            denied_types.add(et)
            continue

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
                text=span_text,
                bucket=bucket,
            )
        )

    entities.sort(key=lambda e: e.start)

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.debug(
        "redaction.detect: input_chars=%d uuid_drops=%d entities=%d surrogate=%d redact=%d "
        "denied=%d denied_types=%s elapsed_ms=%.2f",
        len(text),
        len(sentinels),
        len(entities),
        sum(1 for e in entities if e.bucket == "surrogate"),
        sum(1 for e in entities if e.bucket == "redact"),
        denied_count,
        sorted(denied_types),
        elapsed_ms,
    )

    return masked_text, entities, sentinels
