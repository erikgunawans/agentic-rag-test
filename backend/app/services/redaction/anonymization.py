"""Surrogate / hard-redact substitution (D-04..D-08, ANON-01..06).

Pure programmatic find-and-replace. NO LLM calls (ANON-06).

This module is the back half of the Phase 1 redaction pipeline:
``detect_entities`` (Plan 05) produces a masked text plus the list of
``Entity`` spans; this module substitutes each span with either a
Faker(``id_ID``) surrogate (surrogate-bucket) or a literal ``[ENTITY_TYPE]``
placeholder (hard-redact bucket — D-08).

Per-bucket logic:

- **Surrogate bucket** (PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION,
  DATE_TIME, URL, IP_ADDRESS): generate Faker output, gender-matched for
  PERSON via ``gender_id.lookup_gender`` then ``gender-guesser`` fallback
  (D-04, D-05). Honorifics are stripped before the gender lookup and
  reattached to the surrogate (D-02). The same real value reuses the same
  surrogate within one call (ANON-03).

- **Hard-redact bucket** (CREDIT_CARD, US_SSN, US_ITIN, US_BANK_NUMBER,
  IBAN_CODE, CRYPTO, US_PASSPORT, US_DRIVER_LICENSE, MEDICAL_LICENSE):
  every instance becomes ``[ENTITY_TYPE]`` verbatim — same placeholder for
  every occurrence within one call (D-08). Hard-redact entries are NOT
  recorded in the returned ``entity_map`` (FR-3.5).

Collision-budget (D-06, ANON-05): up to 10 retries against the per-call set
of real first-name / surname tokens (D-07) and already-used surrogates.
After 10 failed attempts, fall back to a deterministic
``[ENTITY_TYPE_<6-hex-blake2b>]`` placeholder.

Privacy (D-18 / B4): logger calls in this module never include real entity
values — only counts, types, and timings.
"""

from __future__ import annotations

import hashlib
import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Literal

import gender_guesser.detector as gg
from faker import Faker

from app.services.redaction.detection import Entity
from app.services.redaction.gender_id import lookup_gender
from app.services.redaction.honorifics import reattach_honorific, strip_honorific
from app.services.redaction.name_extraction import extract_name_tokens

if TYPE_CHECKING:
    # Forward-ref only (Phase 2). Runtime import omitted to avoid a potential
    # circular import: registry.py imports name_extraction + honorifics from
    # this sub-package, and a runtime back-edge from anonymization → registry
    # would close the cycle. The `registry` parameter is annotated with the
    # quoted string "ConversationRegistry | None" so the runtime never resolves
    # this name.
    from app.services.redaction.registry import ConversationRegistry  # noqa: F401

logger = logging.getLogger(__name__)

_COLLISION_RETRIES = 10  # D-06


@lru_cache
def get_faker() -> Faker:
    """D-04: Faker(``id_ID``) singleton.

    Indonesian-locale generator powers all surrogate-bucket replacements
    (PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION, DATE_TIME, URL,
    IP_ADDRESS). Cached so the lifespan warm-up loads it once at boot
    (PERF-01).
    """
    return Faker("id_ID")


@lru_cache
def get_gender_detector() -> gg.Detector:
    """D-05: ``gender-guesser`` fallback singleton.

    Used only when the Indonesian gender table (``gender_id.lookup_gender``)
    returns ``"unknown"``. Returns one of ``"male"``, ``"female"``,
    ``"mostly_male"``, ``"mostly_female"``, ``"andy"``, ``"unknown"``.
    """
    return gg.Detector(case_sensitive=False)


def _resolve_gender(first_name: str) -> Literal["M", "F", "unknown"]:
    """D-05: Indonesian table primary, ``gender-guesser`` fallback, else unknown.

    Args:
        first_name: A bare first name (no honorific, no surname).

    Returns:
        ``"M"`` / ``"F"`` if a definite gender is found; ``"unknown"`` when
        both the Indonesian table and gender-guesser report ambiguous /
        no match. Callers treat ``"unknown"`` as the "use random Faker
        gender" sentinel.
    """
    primary = lookup_gender(first_name)
    if primary in ("M", "F"):
        return primary
    g = get_gender_detector().get_gender(first_name)
    if g in ("male", "mostly_male"):
        return "M"
    if g in ("female", "mostly_female"):
        return "F"
    return "unknown"


def _hash_fallback(entity_type: str, real_value: str) -> str:
    """D-06: deterministic ``[TYPE_<6-hex>]`` fallback after collision budget exhausted.

    Distinct from hard-redact placeholders so Phase 2 de-anonymization can
    still round-trip if the real value lives in the conversation registry.
    """
    short = hashlib.blake2b(real_value.encode("utf-8"), digest_size=3).hexdigest().upper()
    return f"[{entity_type}_{short}]"


def _faker_call(
    faker: Faker, entity_type: str, gender: Literal["M", "F", "unknown"]
) -> str:
    """Dispatch to the right Faker method per surrogate-bucket entity type."""
    if entity_type == "PERSON":
        if gender == "M":
            return faker.name_male()
        if gender == "F":
            return faker.name_female()
        return faker.name()
    if entity_type == "EMAIL_ADDRESS":
        return faker.email()
    if entity_type == "PHONE_NUMBER":
        return faker.phone_number()
    if entity_type == "LOCATION":
        return faker.city()
    if entity_type == "DATE_TIME":
        return faker.date()
    if entity_type == "URL":
        return faker.url()
    if entity_type == "IP_ADDRESS":
        return faker.ipv4()
    # Defensive: an unrecognised surrogate-bucket type. Fall through to a
    # hash placeholder rather than raising — keeps the pipeline robust
    # against future Presidio recognisers we forgot to map.
    return _hash_fallback(entity_type, "")


def _generate_surrogate(
    entity: Entity,
    faker: Faker,
    forbidden_tokens: set[str],
    used_surrogates: set[str],
) -> str:
    """D-06 collision budget + D-07 surname x-check + ANON-03 dedup.

    For PERSON entities: strips honorific, resolves gender on the bare first
    name, generates a gender-matched Faker name, rejects any candidate whose
    tokens overlap real first-name / surname tokens (D-07). After 10 retries,
    falls back to ``[PERSON_<hash>]``. The honorific is reattached either way.

    For non-PERSON surrogate entities: simple Faker dispatch with collision
    rejection against ``used_surrogates`` only.
    """
    if entity.type == "PERSON":
        honorific, bare = strip_honorific(entity.text)
        first_token = bare.split()[0] if bare.split() else bare
        gender = _resolve_gender(first_token)
    else:
        honorific = None
        gender = "unknown"

    for _ in range(_COLLISION_RETRIES):
        candidate = _faker_call(faker, entity.type, gender)
        if candidate in used_surrogates:
            continue
        if entity.type == "PERSON":
            cand_tokens = {t.lower() for t in candidate.split() if t}
            if cand_tokens & forbidden_tokens:
                continue
            return reattach_honorific(honorific, candidate)
        return candidate

    # Budget exhausted (D-06). Hash fallback uses the REAL value as input —
    # the hash never leaks the real value (3-byte blake2b) but does give a
    # stable per-input placeholder for testing reproducibility.
    fallback = _hash_fallback(entity.type, entity.text)
    if entity.type == "PERSON":
        return reattach_honorific(honorific, fallback)
    return fallback


def anonymize(
    masked_text: str,
    entities: list[Entity],
    registry: "ConversationRegistry | None" = None,
) -> tuple[str, dict[str, str], int]:
    """Substitute entities right-to-left to keep offsets stable.

    Args:
        masked_text: The UUID-masked text from ``detect_entities``. Entity
            offsets reference THIS string, not the original input.
        entities: Detected PII spans, each carrying a ``bucket`` of either
            ``"surrogate"`` or ``"redact"``.
        registry: When supplied (Phase 2 D-37 / D-32 / REG-04), the per-call
            cross-call collision check expands its forbidden-token set with
            ``registry.forbidden_tokens()`` and existing real-value surrogates
            are reused via ``registry.lookup()`` (skipping Faker entirely).
            When ``None`` (Phase 1 default — D-39), behaviour is identical to
            the stateless legacy path.

    Returns:
        ``(anonymized_text, entity_map, hard_redacted_count)`` where
        ``entity_map`` contains ONLY surrogate-bucket pairs (real -> surrogate);
        hard-redact entries are excluded per FR-3.5 / D-08. In registry mode
        the map still uses ``Entity.text`` as the key (Plan 05 W-2 invariant)
        so the caller can diff against ``registry.entries()`` to compute the
        delta to upsert.
    """
    faker = get_faker()
    real_persons = [e.text for e in entities if e.type == "PERSON"]
    # D-07: build the per-call forbidden-token set from real PERSON names.
    # Honorifics are stripped before tokenisation so e.g. "Pak" doesn't
    # accidentally land in the forbidden set.
    bare_persons = [strip_honorific(name)[1] for name in real_persons]
    # D-07 / D-37: per-call ∪ per-thread forbidden-token set. Per-PERSON only (D-38).
    call_forbidden = extract_name_tokens(bare_persons)
    if registry is not None:
        forbidden_tokens = call_forbidden | registry.forbidden_tokens()
    else:
        forbidden_tokens = call_forbidden

    entity_map: dict[str, str] = {}
    used_surrogates: set[str] = set()
    hard_redacted_count = 0
    out = masked_text

    # Right-to-left iteration: replacing later spans first keeps earlier
    # offsets valid even when the surrogate length differs from the original.
    for ent in sorted(entities, key=lambda e: e.start, reverse=True):
        if ent.bucket == "redact":
            replacement = f"[{ent.type}]"  # D-08
            hard_redacted_count += 1
        else:
            # REG-04 / D-32 / I-4: if the registry already has this real value,
            # reuse the existing surrogate and skip Faker generation entirely.
            # Add to entity_map so the caller (redact_text) can still observe
            # what was substituted in THIS call; the delta computation will
            # exclude it (real_value already in registry._by_lower).
            #
            # I-4 ordering: this O(1) registry lookup runs BEFORE the O(n)
            # within-call scan below — short-circuits when the registry has
            # the entity, and makes control flow easier to read (registry hit
            # → continue; miss → fall through to Phase 1's within-call + Faker
            # logic).
            if registry is not None:
                hit = registry.lookup(ent.text)
                if hit is not None:
                    entity_map[ent.text] = hit
                    out = out[: ent.start] + hit + out[ent.end :]
                    continue

            # ANON-03: same real value -> same surrogate within one call.
            # Case-insensitive lookup catches "Bambang" / "bambang" variants.
            existing = entity_map.get(ent.text) or next(
                (v for k, v in entity_map.items() if k.lower() == ent.text.lower()),
                None,
            )
            if existing is not None:
                replacement = existing
            else:
                replacement = _generate_surrogate(
                    ent, faker, forbidden_tokens, used_surrogates
                )
                entity_map[ent.text] = replacement
                used_surrogates.add(replacement)
        out = out[: ent.start] + replacement + out[ent.end :]

    logger.debug(
        "redaction.anonymize: entities=%d surrogate_pairs=%d hard_redacted=%d",
        len(entities),
        len(entity_map),
        hard_redacted_count,
    )

    return out, entity_map, hard_redacted_count
