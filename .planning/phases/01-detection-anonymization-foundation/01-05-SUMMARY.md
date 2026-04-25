---
phase: 1
plan: 05
subsystem: redaction
tags: [pii, presidio, ner, spacy, detection]
requires: [02, 03, 04]
provides: [detection.detect_entities, detection.get_analyzer, detection.Entity]
affects: [redaction_service (Plan 06)]
tech_stack:
  added:
    - presidio-analyzer (AnalyzerEngine + NlpEngineProvider)
    - spaCy xx_ent_wiki_sm (multilingual NER)
  patterns:
    - "@lru_cache singleton getter"
    - "@traced(name=redaction.detect) span wrapper"
    - "Pydantic BaseModel for service I/O"
key_files:
  created:
    - backend/app/services/redaction/detection.py
  modified: []
decisions:
  - "Surface bucket label on Entity (`bucket: str`) so anonymizer doesn't re-derive it"
  - "Pass `score_threshold=low_threshold` to analyzer.analyze() — Presidio prunes before our two-pass filter"
  - "Bucket sets resolved at module load (no per-call re-read of Settings.pii_*_entities)"
metrics:
  duration_minutes: ~5
  tasks_completed: 1
  files_changed: 1
  completed_date: 2026-04-25
requirements: [PII-01, PII-02, PII-03, PII-04, PII-05]
---

# Phase 1 Plan 05: Detection Module Summary

**One-liner:** Presidio AnalyzerEngine wired to spaCy `xx_ent_wiki_sm` with two-pass per-bucket thresholds and UUID pre-masking, exposed as `detect_entities(text) -> (masked_text, entities, sentinels)` for downstream anonymization.

## Files Created

| File | Lines | Role |
|------|-------|------|
| `backend/app/services/redaction/detection.py` | 159 | Presidio detection layer for the redaction pipeline |

## Public API (consumed by Plan 06)

### `Entity` Pydantic model

```python
class Entity(BaseModel):
    type: str       # Presidio entity type ("PERSON", "EMAIL_ADDRESS", "LOCATION", ...)
    start: int      # span start in MASKED text (post-UUID-substitution)
    end: int        # span end (exclusive)
    score: float    # Presidio confidence
    text: str       # the literal substring of MASKED text covered by [start:end]
    bucket: str     # "surrogate" or "redact" — precomputed at detection time
```

The `bucket` field is precomputed by `detect_entities` so Plan 06's anonymizer can dispatch on it directly without re-consulting `Settings`.

### `get_analyzer() -> AnalyzerEngine`

Lazy `@lru_cache`'d singleton. Builds:

```python
NlpEngineProvider(nlp_configuration={
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "xx", "model_name": "xx_ent_wiki_sm"}],
})
AnalyzerEngine(nlp_engine=..., supported_languages=["xx"])
```

**First-call vs cached-call timing (PERF-01 evidence):**
- Cold call (no prior cache): **579.60 ms**
- Subsequent calls (cached): **0.0004 ms** (~6 orders of magnitude faster)
- Identity check `a is a2`: `True`

Plan 06's lifespan warm-up will pay this 580 ms cost once at startup; the first chat request hits a hot analyzer.

### `detect_entities(text) -> tuple[str, list[Entity], dict[str, str]]`

3-tuple return shape (W10): `(masked_text, entities, sentinels)`.

- `masked_text`: input with every standard 8-4-4-4-12 hex UUID replaced by `<<UUID_N>>` sentinels.
- `entities`: list sorted by `start` offset (ascending) so the anonymizer can do right-to-left replacement without index drift.
- `sentinels`: `{sentinel_token -> original_uuid}` map produced by `apply_uuid_mask`.

Plan 06's `RedactionService.redact_text` will call `detect_entities` once and pass `masked_text` straight into `anonymize` and `sentinels` into `restore_uuids` — eliminating the redundant double-masking that motivated W10.

## Two-Pass Threshold Flow (D-03 / PII-02)

Implemented as **single Presidio call + per-bucket filter** (cheaper than two analyzer calls):

1. `analyzer.analyze(text=masked_text, entities=sorted(_ALL_BUCKET), language="xx", score_threshold=low_threshold)` — Presidio prunes anything below the `pii_redact_score_threshold` (0.3) before returning.
2. Loop the raw results:
   - `entity_type ∈ _SURROGATE_BUCKET` AND `score >= pii_surrogate_score_threshold` (0.7) → keep, `bucket="surrogate"`
   - `entity_type ∈ _REDACT_BUCKET` AND `score >= pii_redact_score_threshold` (0.3) → keep, `bucket="redact"`
   - Anything else (including off-bucket types Presidio sometimes returns) → drop
3. Sort by `start` and return.

Bucket lists come from `Settings.pii_surrogate_entities` / `Settings.pii_redact_entities` (CSV strings), parsed once at module load via `_split_csv` (uppercased, whitespace-stripped). Default surrogate bucket: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, LOCATION, DATE_TIME, URL, IP_ADDRESS. Default redact bucket: CREDIT_CARD, US_SSN, US_ITIN, US_BANK_NUMBER, IBAN_CODE, CRYPTO, US_PASSPORT, US_DRIVER_LICENSE, MEDICAL_LICENSE.

## Smoke Test on Indonesian Sample

Input: `"Pak Bambang Sutrisno tinggal di Jakarta. Email: bambang@example.com. Doc: 6ba7b810-9dad-11d1-80b4-00c04fd430c8."`

Output:
```
masked_text:   "Pak Bambang Sutrisno tinggal di Jakarta. Email: bambang@example.com. Doc: <<UUID_0>>."
entities:      [
  ('PERSON',        'surrogate', 0.85, 'Pak Bambang Sutrisno'),
  ('LOCATION',      'surrogate', 0.85, 'Jakarta'),
  ('EMAIL_ADDRESS', 'surrogate', 1.0,  'bambang@example.com'),
]
sentinels:     {'<<UUID_0>>': '6ba7b810-9dad-11d1-80b4-00c04fd430c8'}
```

All 3 detected entities are in the surrogate bucket with `score >= 0.7` (PII-02 threshold satisfied). The UUID never reached Presidio (PII-04 satisfied). The `Pak` honorific was correctly captured inside the PERSON span — Plan 06's anonymizer will use Plan 04's `strip_honorific`/`reattach_honorific` helpers when generating the surrogate.

**Latency:** Cold detect call (analyzer not yet built): 805.91 ms (includes the 580 ms analyzer init). Warm detect call: 1.90 ms.

## Multilingual Model Coverage Notes

`xx_ent_wiki_sm` (per the spaCy model card) recognises `PER`, `LOC`, `ORG`, `MISC` out of the box. Presidio's recognizer registry maps these to `PERSON`, `LOCATION`, `ORGANIZATION`, `NRP` respectively. The other surrogate-bucket types (`EMAIL_ADDRESS`, `PHONE_NUMBER`, `URL`, `IP_ADDRESS`, `DATE_TIME`) come from Presidio's regex-/heuristic-based recognizers, which are language-agnostic and worked on Indonesian text in the smoke test (e.g. `bambang@example.com` → `EMAIL_ADDRESS` score 1.0).

**Phase 1 boundary:** the multilingual model is sometimes weaker than `id_core_news_lg` on niche Indonesian-only entity classes (e.g. local NIK/NPWP IDs, Indonesian-formatted phone numbers like `0812-3456-7890`). Adding custom recognizers for these is deferred to Phase 6 hardening per the CONTEXT.md "Deferred Ideas" list.

## D-18 Log Privacy Invariant (B4)

Acceptance grep:
```
grep -nE "logger\.(debug|info|warning|error|exception).*\.text|logger\.(debug|info|warning|error|exception).*r\.entity" \
  backend/app/services/redaction/detection.py | grep -v "len("
```
**Result:** 0 matches. The single `logger.debug` call emits counts (`len(text)`, `len(sentinels)`, `len(entities)`, surrogate/redact subcounts), bucket labels, and timings — never entity text or matched values.

## Singleton Cache Behaviour

`get_analyzer()` is decorated with `@lru_cache` (no maxsize → defaults to 128, but only one cache key — no args). Verified:
- Cold call returns `AnalyzerEngine` instance.
- Second call returns the **same** instance (`is` comparison true).
- Cold→warm latency drop: ~580 ms → ~0.0004 ms.

This satisfies D-15 (lazy singleton) and PERF-01 (model loaded once at startup). Plan 06 will add `get_analyzer()` to the FastAPI `lifespan` warm-up sequence so the first request after deploy is hot.

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| `detection.py` exists | PASS |
| `class Entity(BaseModel)` defined with required fields | PASS (+ extra `bucket` field) |
| `get_analyzer()` is `@lru_cache`'d | PASS |
| `xx_ent_wiki_sm` configured | PASS (NlpEngineProvider with `lang_code="xx"`) |
| Two-pass thresholds enforced via `Settings` | PASS |
| `detect_entities` returns 3-tuple `(masked, entities, sentinels)` (W10) | PASS |
| UUIDs pre-masked before NER (PII-04) | PASS — UUID sample produced 1 sentinel, 0 false-positive entities |
| Logger never includes entity text (D-18 / B4) | PASS — grep returns 0 matches |
| `from app.main import app` boots cleanly | PASS |
| Smoke test: PERSON + LOCATION + EMAIL on Indonesian sample | PASS |

## Self-Check: PASSED

- File exists: `backend/app/services/redaction/detection.py` (159 lines)
- Commit exists: `76a6c3e` (`feat(01-05): add Presidio detection module ...`)
- All grep acceptance counts non-zero
- Smoke test produces expected entities and sentinel
- App import succeeds

## Deviations from Plan

None — plan executed exactly as written.

## Hand-off to Plan 06

Plan 06's `RedactionService.redact_text` should:

```python
masked_text, entities, sentinels = detect_entities(text)
# anonymize() walks `entities` (already sorted by start), replaces in masked_text
anonymized = anonymize(masked_text, entities, registry=...)
# restore_uuids() swaps sentinels back to original UUIDs
final = restore_uuids(anonymized, sentinels)
```

**Do NOT call `apply_uuid_mask` again** — the masked text is already in the first tuple element. This is the W10 fix.

The `Entity.bucket` field tells the anonymizer which path to take:
- `bucket == "surrogate"` → look up / generate Faker surrogate (Plan 06 substitution logic)
- `bucket == "redact"` → emit `[ENTITY_TYPE]` placeholder (D-08)
