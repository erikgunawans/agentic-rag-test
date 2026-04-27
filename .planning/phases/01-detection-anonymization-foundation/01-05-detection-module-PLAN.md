---
phase: 1
plan_number: 05
title: "Detection module: Presidio analyzer with xx_ent_wiki_sm + two-pass thresholds + bucket env-driven entity selection"
wave: 2
depends_on: [02, 03, 04]
requirements: [PII-01, PII-02, PII-03, PII-04, PII-05]
files_modified:
  - backend/app/services/redaction/detection.py
autonomous: true
must_haves:
  - "`detection.detect_entities(text)` returns a list of `Entity` objects (Pydantic) with fields `type`, `start`, `end`, `score`, `text`, where each entity's `score` >= the appropriate per-bucket threshold (D-03)."
  - "`detection.get_analyzer()` is `@lru_cache`'d and lazily constructs a `presidio_analyzer.AnalyzerEngine` configured with the spaCy `xx_ent_wiki_sm` model (D-01)."
  - "Two-pass detection: surrogate-bucket entities returned ONLY if score >= `pii_surrogate_score_threshold`; hard-redact-bucket entities returned ONLY if score >= `pii_redact_score_threshold` (D-03 / PII-02)."
  - "UUID pre-mask is applied BEFORE Presidio analysis so document-ID lookalikes never appear in the returned entity list (PII-04)."
  - "`detect_entities(text)` returns the 3-tuple `(masked_text, entities, sentinels)` so RedactionService can pass `masked_text` directly to `anonymize` without calling `apply_uuid_mask` a second time (W10)."
  - "Logger calls in `detection.py` NEVER include real entity values (`entity.text`, `r.entity_text` etc.) — only counts, types, and timings (D-18 / CLAUDE.md)."
---

<objective>
Build the `detection` module that wraps Presidio AnalyzerEngine with the spaCy `xx_ent_wiki_sm` NLP engine (D-01), applies two-pass thresholds per entity bucket (D-03), reads bucket membership from `Settings.pii_surrogate_entities` / `Settings.pii_redact_entities` (PII-03), and pre-masks UUIDs via Plan 04's `uuid_filter` helpers (PII-04).

This module is the read-only side of the redaction pipeline: it discovers PII spans but does not generate surrogates. Plan 06 (anonymization) consumes its output.

Purpose: PII-01 / PII-02 / PII-03 / PII-04 / PII-05 are all detection-layer concerns. Centralising them in one module lets Plan 06's `RedactionService` stay focused on the substitution logic.

Output: A single new file `backend/app/services/redaction/detection.py` exposing:
- `class Entity(BaseModel)` — Pydantic model for a detected entity span.
- `def get_analyzer() -> AnalyzerEngine` — `@lru_cache`'d singleton getter.
- `def detect_entities(text: str) -> tuple[str, list[Entity], dict[str, str]]` — main entry point. Returns `(masked_text, entities, sentinels)` so callers can reuse `masked_text` directly without re-invoking `apply_uuid_mask` (W10 efficiency fix).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md
@backend/app/config.py
@backend/app/services/redaction/__init__.py
@backend/app/services/redaction/uuid_filter.py
@backend/app/services/tracing_service.py

CONTEXT.md decisions consumed in this plan:
- D-01: Use `xx_ent_wiki_sm` as the spaCy NLP engine fed into Presidio (multilingual, Indonesian-friendly).
- D-03: Honour `PII_SURROGATE_SCORE_THRESHOLD=0.7` and `PII_REDACT_SCORE_THRESHOLD=0.3`; both read from `Settings`.
- D-09: Pre-input mask + post-NER restore strategy for UUIDs.
- D-15: `@lru_cache`'d singleton getter pattern for the analyzer.
- D-18: Wrap detection ops with `@traced(name="redaction.detect")`. Span attributes include input length, entity counts per type, surrogate vs redact bucket counts, UUID-filter drops, total latency. NEVER log real values.

Public API (consumed by Plan 06):
```python
from pydantic import BaseModel

class Entity(BaseModel):
    type: str           # Presidio entity type, e.g. "PERSON", "EMAIL_ADDRESS"
    start: int          # span start (in MASKED text, post-UUID-substitution)
    end: int            # span end (exclusive)
    score: float        # Presidio confidence
    text: str           # the literal substring of MASKED text covered by [start:end]
    bucket: str         # "surrogate" or "redact" - precomputed by detect_entities

def get_analyzer() -> AnalyzerEngine: ...

def detect_entities(text: str) -> tuple[str, list[Entity], dict[str, str]]:
    """Returns (masked_text, entities, uuid_sentinels). All three are needed by Plan 06:
       - masked_text: the UUID-pre-masked text the entity offsets reference;
         RedactionService passes this directly to `anonymize` (avoids calling
         apply_uuid_mask twice — W10).
       - entities: list of detected PII spans (post-bucket-threshold filtering),
         offsets relative to masked_text.
       - uuid_sentinels: the {sentinel -> original_uuid} map needed to restore
         UUIDs in the final anonymized text.
    """
```

Existing patterns to mirror:
- `@lru_cache` getter: `backend/app/config.py` `get_settings()` (lines 74-76).
- `logger = logging.getLogger(__name__)` per service (CONVENTIONS.md §Logging).
- Pydantic `BaseModel` for service I/O (matches `RedactionResult` shape used in Plan 06).
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Create detection.py with Presidio analyzer singleton, Entity model, and two-pass detect_entities</name>
  <files>backend/app/services/redaction/detection.py</files>
  <read_first>
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md (D-01 model choice, D-03 thresholds, D-09 UUID strategy, D-15 lazy singleton, D-18 tracing)
    - backend/app/config.py (Settings.pii_surrogate_entities, pii_redact_entities, pii_surrogate_score_threshold=0.7, pii_redact_score_threshold=0.3 as appended in Plan 02)
    - backend/app/services/redaction/uuid_filter.py (apply_uuid_mask returns (masked_text, sentinels)); detect_entities (this file) returns (masked_text, entities, sentinels) per W10
    - backend/app/services/tracing_service.py (the @traced decorator from Plan 01)
    - Microsoft Presidio docs via context7 (`mcp__context7__resolve-library-id` "presidio-analyzer" then `get-library-docs` for AnalyzerEngine + NlpEngineProvider configuration with custom spaCy model)
  </read_first>
  <action>
Create `backend/app/services/redaction/detection.py` with this complete content:

```python
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
```

Notes for the executor:
- `_SETTINGS` is captured at module load time. Bucket sets are immutable for the process lifetime — env-var changes require a backend restart. This matches D-03 (no per-call re-read) and the existing `Settings` access pattern.
- `score_threshold=low_threshold` is passed to `analyzer.analyze` so Presidio prunes very-low-confidence results before we filter; saves a small amount of work and matches the two-pass design.
- The `@traced(name="redaction.detect")` decorator from Plan 01 is the ONE tracing wrapper. Internal helpers (`apply_uuid_mask`, the actual Presidio call) do not get their own decorators in Phase 1 — D-18 explicitly says "if non-trivial", and these are trivial.
- The `entities` list is sorted by `start` so downstream anonymization can replace right-to-left without index drift.
- Logger uses `%s`-formatting (CONVENTIONS.md §Logging) and reports counts only — no entity text values. **B4 enforcement:** the acceptance grep `logger\.(debug|info|warning|error|exception).*\.text` MUST return 0 matches; if a future edit adds `logger.debug("entity=%s", entity.text)` the grep gate fails.
- `xx` language code is correct for `xx_ent_wiki_sm` (the multilingual spaCy model uses `xx` as its language tag).
  </action>
  <verify>
    <automated>cd backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "from app.services.redaction.detection import Entity, get_analyzer, detect_entities; print(Entity.model_fields.keys()); a = get_analyzer(); print(type(a).__name__); masked, ents, sents = detect_entities('Pak Bambang Sutrisno tinggal di Jakarta. Email: bambang@example.com. Doc: 6ba7b810-9dad-11d1-80b4-00c04fd430c8'); print(len(ents), len(sents)); assert len(sents) == 1; assert '<<UUID_0>>' in masked; assert any(e.type == 'PERSON' for e in ents) or len(ents) > 0; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `backend/app/services/redaction/detection.py` exists.
    - `grep -n "class Entity(BaseModel):" backend/app/services/redaction/detection.py` returns 1 match.
    - `grep -n "def get_analyzer" backend/app/services/redaction/detection.py` returns 1 match.
    - `grep -n "@lru_cache" backend/app/services/redaction/detection.py` returns 1 match.
    - `grep -n "def detect_entities" backend/app/services/redaction/detection.py` returns 1 match.
    - `grep -n "@traced(name=\"redaction.detect\")" backend/app/services/redaction/detection.py` returns 1 match.
    - `grep -n "xx_ent_wiki_sm" backend/app/services/redaction/detection.py` returns at least 1 match.
    - `grep -n "from app.services.redaction.uuid_filter import apply_uuid_mask" backend/app/services/redaction/detection.py` returns 1 match.
    - `cd backend && source venv/bin/activate && python -c "from app.services.redaction.detection import get_analyzer; a = get_analyzer(); print(type(a).__name__)"` exits 0 and prints `AnalyzerEngine`.
    - `cd backend && source venv/bin/activate && python -c "from app.services.redaction.detection import detect_entities; masked, ents, s = detect_entities('Bambang lives in Jakarta. Email: a@b.com'); print(len(ents)); print([(e.type, e.bucket) for e in ents])"` exits 0; the printed list contains at least one entity tagged with bucket `'surrogate'` (likely PERSON or EMAIL_ADDRESS).
    - `cd backend && source venv/bin/activate && python -c "from app.services.redaction.detection import detect_entities; masked, ents, s = detect_entities('Doc 6ba7b810-9dad-11d1-80b4-00c04fd430c8 ok'); assert len(s) == 1, s; assert '<<UUID_0>>' in masked; print('UUID masked: OK')"` exits 0 and prints `UUID masked: OK`.
    - **B4 (no real PII in logs):** `grep -nE "logger\.(debug|info|warning|error|exception).*\.text|logger\.(debug|info|warning|error|exception).*r\.entity" backend/app/services/redaction/detection.py | grep -v "len("` returns 0 matches (logger emits counts/types only, never entity values).
    - `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"` exits 0.
  </acceptance_criteria>
  <done>detection.py compiles, Presidio analyzer initialises with xx_ent_wiki_sm, detect_entities runs end-to-end on Indonesian and English text, two-pass thresholds enforced via Settings, UUIDs masked before NER, @traced wrapper applied.</done>
</task>

</tasks>

<verification>
After the task completes:
```bash
cd backend && source venv/bin/activate
python -m spacy download xx_ent_wiki_sm  # if not done in Plan 03
python -c "
from app.services.redaction.detection import detect_entities
masked_text, ents, sentinels = detect_entities('Pak Bambang Sutrisno tinggal di Jakarta. Email: bambang@example.com. Doc: 6ba7b810-9dad-11d1-80b4-00c04fd430c8.')
print('masked_text:', masked_text)
print('entities:', [(e.type, e.bucket, e.score, e.text) for e in ents])
print('uuid sentinels:', sentinels)
"
# Expected: at least 1 PERSON, 1 EMAIL_ADDRESS, 1 LOCATION entity, all bucket='surrogate', all scores >= 0.7. Exactly 1 sentinel for the UUID.
```
</verification>

<success_criteria>
1. PII-01 satisfied: Presidio AnalyzerEngine with xx_ent_wiki_sm correctly identifies the 7 surrogate-bucket entity types at high threshold and 9 hard-redact-bucket types at low threshold.
2. PII-02 satisfied: two-pass thresholds applied per bucket — `score >= 0.7` for surrogate types, `score >= 0.3` for redact types; entities outside both thresholds are dropped.
3. PII-03 satisfied: bucket membership read from `Settings.pii_surrogate_entities` / `Settings.pii_redact_entities` env-driven CSV strings.
4. PII-04 satisfied at the detection layer: UUIDs are pre-masked before Presidio sees the text, so document-ID lookalikes never become Entity instances.
5. PII-05 satisfied: thresholds read from `Settings.pii_surrogate_score_threshold` / `Settings.pii_redact_score_threshold`; env-var overrides take effect at process start.
6. D-15 satisfied: `get_analyzer()` is `@lru_cache`'d so subsequent calls reuse the loaded model.
7. D-18 satisfied: every `detect_entities` call appears as a `redaction.detect` span in the configured tracing provider; span attributes are counts and timing only.
</success_criteria>

<output>
After completion, create `.planning/phases/01-detection-anonymization-foundation/01-05-SUMMARY.md` capturing:
- The exact `Entity` Pydantic schema (so Plan 06's anonymization code knows what to consume).
- The two-pass threshold flow as actually implemented (high vs low + which bucket each came from).
- A note on Presidio's behaviour for the multilingual model: which entity types it recognises out-of-the-box on Indonesian text vs which need post-Phase-1 custom recognizers.
- Confirmation that `get_analyzer()` is single-call-cached and lifespan warm-up will route through it (Plan 06 wires the lifespan call).
</output>
