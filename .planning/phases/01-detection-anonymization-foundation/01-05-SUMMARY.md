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

---

## Patch — xx-language recognizer coverage (2026-04-25, post-Plan 06)

**Why:** Plan 06's smoke test surfaced a coverage gap (logged in `01-06-SUMMARY.md` as Known follow-up #1). Presidio's default `RecognizerRegistry` registers pattern-based recognizers (PhoneRecognizer, CreditCardRecognizer, UsSsnRecognizer, IbanRecognizer, etc.) for `language="en"` only. Because `get_analyzer()` queries `language="xx"` (D-01: multilingual spaCy NER for Indonesian-friendly NER), every pattern recognizer was silently skipped — leaving CREDIT_CARD, US_SSN, US_ITIN, US_BANK_NUMBER, IBAN_CODE, CRYPTO, US_PASSPORT, US_DRIVER_LICENSE, MEDICAL_LICENSE, PHONE_NUMBER, URL, IP_ADDRESS, DATE_TIME undetected on every Indonesian chat input. Phase 1 SC#1 / FR-2.5 / FR-3.5 require these to be redacted or surrogate-substituted.

**Patch (single file: `backend/app/services/redaction/detection.py`):**

After the `AnalyzerEngine` is constructed, walk a list of factory closures and call `analyzer.registry.add_recognizer(...)` for each one with `supported_language="xx"`. Failures are logged at `WARNING` (defensive across Presidio versions; do not block startup) and tallied so the success/failure count appears in the analyzer-init INFO log.

### Recognizer classes registered for `language="xx"`

| Class | Entity type | Result |
|---|---|---|
| `EmailRecognizer` | `EMAIL_ADDRESS` | registered |
| `_PhoneRecognizerXX` (subclass) | `PHONE_NUMBER` | registered |
| `UrlRecognizer` | `URL` | registered |
| `IpRecognizer` | `IP_ADDRESS` | registered |
| `DateRecognizer` | `DATE_TIME` | registered |
| `CreditCardRecognizer` | `CREDIT_CARD` | registered |
| `IbanRecognizer` | `IBAN_CODE` | registered |
| `UsSsnRecognizer` | `US_SSN` | registered |
| `UsItinRecognizer` | `US_ITIN` | registered |
| `UsBankRecognizer` | `US_BANK_NUMBER` | registered |
| `UsPassportRecognizer` | `US_PASSPORT` | registered |
| `UsLicenseRecognizer` | `US_DRIVER_LICENSE` | registered |
| `MedicalLicenseRecognizer` | `MEDICAL_LICENSE` | registered |
| `CryptoRecognizer` | `CRYPTO` | registered |

**Failures:** none. All 14 registered cleanly under Presidio's installed version. Startup INFO log now reads: `Presidio analyzer initialised with xx_ent_wiki_sm model (xx pattern recognizers registered=14 failed=0).`

### `_PhoneRecognizerXX` subclass — score floor fix (Rule 2: critical functionality)

Registering `PhoneRecognizer(supported_language="xx")` alone was insufficient: the upstream `PhoneRecognizer` hard-codes `SCORE = 0.4` and relies on Presidio's `LemmaContextAwareEnhancer` to lift it above the `pii_surrogate_score_threshold` (0.7) by matching nearby context words like "phone" / "telephone" / "mobile". The lemma enhancer requires the spaCy NLP engine to produce token lemmas — which `xx_ent_wiki_sm` does not (NER-only). So every parsed phone number scored exactly `0.4` and was silently dropped by the two-pass threshold filter, breaking SC#1.

A python-phonenumbers match that successfully parses to a number whose region is in `supported_regions` is high-quality evidence of a real phone number. The patch defines a thin subclass `_PhoneRecognizerXX` that overrides the class attribute to `SCORE = 0.75` (just over the surrogate threshold). All other behavior is inherited unchanged.

`supported_regions=("ID", "US", "UK", "IN")` — the upstream default omits `ID` (Indonesia), so Indonesian `+62` numbers were not even being matched. The patch passes an explicit list that includes Indonesia plus a few common regions present in the legal corpus.

### Before/after entity-type coverage on the smoke sentence

Sentence: `Pak Bambang Sutrisno bekerja di Jakarta. Phone: +628123456789. KK: 4111-1111-1111-1111. SSN: 555-12-3456. Doc: <UUID>`

| Entity type | Before patch | After patch |
|---|---|---|
| PERSON (`Pak Bambang Sutrisno`) | detected (0.85) | detected (0.85) |
| LOCATION (`Jakarta`) | detected (0.85) | detected (0.85) |
| **PHONE_NUMBER** (`+628123456789`) | **NOT detected** | **detected (0.75)** |
| **CREDIT_CARD** (`4111-1111-1111-1111`) | **NOT detected** | **detected (1.00)** |
| **US_SSN** (`555-12-3456`) | **NOT detected** | **detected (0.50)** |
| UUID sentinel | masked (1) | masked (1) |

(Note: the prompt-canonical sentence used SSN `123-45-6789` which Presidio's `UsSsnRecognizer.invalidate_result` explicitly rejects as a sample value — substituting any non-sample SSN like `555-12-3456` makes the recognizer fire as expected.)

### End-to-end through `redact_text`

```text
in:  Pak Bambang Sutrisno. Email: bambang@example.com. Phone: +628123456789. KK: 4111-1111-1111-1111. Doc: 6ba7b810-9dad-11d1-80b4-00c04fd430c8
out: Pak Sutan Eman Wibowo. Email: qnatsir@example.com. Phone: (0344) 171 4961. KK: [CREDIT_CARD]. Doc: 6ba7b810-9dad-11d1-80b4-00c04fd430c8
hard_redacted_count: 1
entity_map keys: ['+628123456789', 'bambang@example.com', 'Pak Bambang Sutrisno']
```

- Credit card → `[CREDIT_CARD]` placeholder (hard-redact bucket, FR-3.5 — never recorded in `entity_map`).
- Phone number → Faker `id_ID` surrogate `(0344) 171 4961` (Indonesian format).
- UUID preserved exactly.
- `hard_redacted_count = 1` correctly reflects the credit card.

### Invariants preserved

- `get_analyzer()` is still `@lru_cache`'d — registration runs once per process at first call (PERF-01 holds; lifespan warm-up still pays the cost off-request).
- `detect_entities` still returns the same 3-tuple `(masked_text, entities, sentinels)` (W10).
- D-18 / B4: the new `logger.warning` and `logger.info` calls in the registration loop emit recognizer **class names and counts only** — no user data, no entity text.
- Patch is fully scoped to `detection.py`; Plan 06's `redaction_service.py`, `anonymization.py`, `__init__.py`, and `main.py` are untouched.

### Why this isn't deferred to Phase 6

It was originally logged as a Phase 6 follow-up in the Plan 06 SUMMARY, but on review the gap blocks Phase 1 SC#1 ("any text passing through the new redaction service yields realistic, gender-matched, collision-free Indonesian-locale surrogates without leaking real values") for the entire hard-redact bucket. Per executor Rule 2 (auto-add missing critical functionality), the fix lands on master immediately rather than waiting on a hardening phase that may be weeks away.
