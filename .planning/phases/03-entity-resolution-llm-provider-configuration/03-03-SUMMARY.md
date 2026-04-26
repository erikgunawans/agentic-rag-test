---
phase: 03-entity-resolution-llm-provider-configuration
plan: 03
subsystem: backend/app/services/redaction
tags: [redaction, clustering, egress, nicknames, union-find, security]
requires:
  - backend/app/services/redaction/honorifics.py (Phase 1 — strip_honorific)
  - backend/app/services/redaction/detection.py (Phase 1 — Entity)
  - backend/app/services/redaction/registry.py (Phase 2 — ConversationRegistry, EntityMapping)
  - backend/app/services/redaction/name_extraction.py (Phase 1 — nameparser idiom)
  - backend/app/services/redaction/gender_id.py (Phase 1 — analog for nicknames_id shape)
provides:
  - lookup_nickname (Indonesian-aware nickname → canonical first-name lookup)
  - Cluster (frozen dataclass: canonical, variants, members)
  - cluster_persons (Union-Find PERSON clustering with D-46/D-47 rules)
  - variants_for (sub-surrogate variant set generator — D-48)
  - egress_filter (casefold + word-boundary regex pre-flight egress filter — D-53/D-56)
  - EgressResult (frozen dataclass: tripped, match_count, entity_types, match_hashes)
  - _EgressBlocked (internal exception carrying EgressResult — D-54)
affects:
  - Plan 03-04 (LLMProviderClient — imports egress_filter, EgressResult, _EgressBlocked)
  - Plan 03-05 (redaction_service wiring — imports cluster_persons, variants_for)
tech-stack:
  added: []
  patterns:
    - "Module-level frozen dict + casefolded lookup helper (mirrors gender_id.py)"
    - "Union-Find with path compression for entity coreference clustering"
    - "TYPE_CHECKING import to break circular dependency for ConversationRegistry"
    - "SHA-256[:8] hash logging — forensic correlation without raw-PII leak (D-55 / B4)"
key-files:
  created:
    - backend/app/services/redaction/nicknames_id.py (89 lines)
    - backend/app/services/redaction/clustering.py (247 lines)
    - backend/app/services/redaction/egress.py (115 lines)
  modified: []
decisions:
  - "Confirmed Entity import path matches anonymization.py: `from app.services.redaction.detection import Entity` (line 45 of anonymization.py)"
  - "Confirmed EntityMapping field names from registry.py: `entity_type: str`, `real_value: str` — used verbatim in egress_filter candidate-list construction"
  - "53 nickname dict entries (≥30 required by acceptance criterion) — 25 Indonesian-first + 28 English"
  - "Used `if honorific:` rather than `if honorific is not None:` in variants_for — Phase 1's strip_honorific returns `None` for missing prefix (truthiness handles both None and empty string)"
metrics:
  duration: "4m 20s"
  completed_date: "2026-04-26"
  tasks: 3
  files_created: 3
  files_modified: 0
  total_lines_added: 451
  commits: 3
---

# Phase 3 Plan 3: Nicknames, Clustering, Egress — Wave 3 Leaf Modules Summary

**One-liner:** Three independent leaf modules under `backend/app/services/redaction/` — Indonesian nickname lookup, Union-Find PERSON coreference clustering with sub-surrogate variant generation, and the pre-flight egress filter that secures every cloud-LLM call against PII leakage — all stateless / pure-function shape, total 451 lines.

## Outcome

Wave 3 of Phase 3 is complete. The three modules that Plan 03-04 (LLM provider client) and Plan 03-05 (redaction-service wiring) compose are now in place, isolated from each other except for `clustering.py` importing `lookup_nickname` and `strip_honorific`. None of the new modules reaches across trust boundaries; all logging adheres to the B4 / D-18 / D-55 invariant (counts and 8-char SHA-256 hashes only — never raw values).

## Files Shipped

| File | Lines | Public Exports |
|------|------:|----------------|
| `backend/app/services/redaction/nicknames_id.py` | 89 | `lookup_nickname` |
| `backend/app/services/redaction/clustering.py` | 247 | `Cluster`, `cluster_persons`, `variants_for` |
| `backend/app/services/redaction/egress.py` | 115 | `egress_filter`, `EgressResult`, `_EgressBlocked` |

## Pre-Write Verification

Per the plan's `<read_first>` blocks, two upstream-dependency verifications were performed before authoring the leaf files:

1. **`Entity` import path for `clustering.py`** — `grep -n "from app.services.redaction" backend/app/services/redaction/anonymization.py | grep -i entity` returned line 45: `from app.services.redaction.detection import Entity`. `clustering.py` uses this path verbatim.

2. **`EntityMapping.real_value` field for `egress.py`** — `grep -n "real_value" backend/app/services/redaction/registry.py` returned the exact field name (line 58: `real_value: str`) and `entity_type` (line 61). `egress.py` reads `ent.entity_type` and `ent.real_value` per entry — no field-name guesswork required.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | nicknames_id.py — Indonesian-aware nickname → canonical lookup (D-46) | `496cc57` |
| 2 | clustering.py — Union-Find + sub-surrogate variants (D-45..D-48) | `86ce3d4` |
| 3 | egress.py — pre-flight egress filter + EgressResult + _EgressBlocked (D-53..D-56) | `5510d80` |

## Verification Results

### Per-task automated checks (from PLAN.md `<verify>` blocks)

- Task 1: `lookup_nickname('Danny') == 'daniel'`, `lookup_nickname('Bambs') == 'bambang'`, case-insensitive, missing → `None`, 53 entries ≥ 30 — PASSED.
- Task 2: `variants_for('Bambang Sutrisno')` → frozenset containing `'Bambang Sutrisno'`, `'Bambang'`, `'Sutrisno'`; `variants_for('Pak Bambang Sutrisno')` includes `'Pak Bambang'`, `'Pak Sutrisno'`, `'Pak Bambang Sutrisno'`; `cluster_persons([])` → `[]` — PASSED.
- Task 3: `EgressResult` frozen, `_EgressBlocked` carries result, `_hash8(v)` is `sha256(v.encode("utf-8")).hexdigest()[:8]` — PASSED.

### Functional clustering checks

- D-45/D-46 single-cluster fold: `[Daniel Sutrisno, Daniel, Danny]` → 1 cluster, canonical `Daniel Sutrisno`, 3 members — PASSED.
- D-47 strict refuse-ambiguous: `[Daniel Sutrisno, Daniel Wijaya, Daniel]` → 3 clusters (solo `Daniel` does NOT merge into either Daniel-* cluster) — PASSED.

### Functional egress checks

- Trip path: payload contains real value `Bambang Sutrisno` from registry → `tripped=True`, `match_count=1`, `entity_types=['PERSON']`, `match_hashes=['<8-hex>']` — PASSED.
- No-trip path: payload contains only the surrogate `Daniel Wijaya` → `tripped=False` — PASSED.
- Word-boundary preservation: real_value `Ana` against payload `Banana bread.` → `tripped=False` (substring inside larger word does NOT match) — PASSED.
- Provisional-only path: empty registry, `provisional={'Joko Wijaya': 'Surrogate1'}`, payload contains `Joko Wijaya` → `tripped=True`, `entity_types=['PERSON']` — PASSED.

### Phase 1 + Phase 2 regression

```
cd backend && pytest tests/ --tb=short
======================= 39 passed, 12 warnings in 12.72s =======================
```

**39/39 tests pass** — no Phase 1 / Phase 2 public API was modified by this plan (Wave 3 modules are leaves; nothing imports them yet outside the smoke-tests in this plan). Backend import check `from app.main import app` also passes.

## Threat Model Coverage (from PLAN.md `<threat_model>`)

| Threat ID | Disposition | Implemented As |
|-----------|-------------|----------------|
| T-EGR-01 (egress bypass) | mitigate | `egress_filter` regex `\b + re.escape(value.casefold()) + \b` against `payload.casefold()` — registry ∪ provisional |
| T-EGR-02 (trip log leaks PII) | mitigate | trip-log format string contains ONLY `match_count=%d`, `entity_types=%s`, `match_hashes=%s` (no raw value, no payload, no first-N-chars) |
| T-EGR-03 (provisional bypass) | mitigate | `egress_filter(payload, registry, provisional)` signature enforces both inputs; provisional path verified |
| T-CLUST-01 (wrong cluster merge) | mitigate | D-47 strict refuse-ambiguous: solo with multiple candidate clusters → own cluster; verified with `[Daniel Sutrisno, Daniel Wijaya, Daniel]` test |
| T-LOG-01 (clustering logs entity.text) | mitigate | All `logger.debug` format strings use `%d` only; no `%s` formatting on `entity.text` or `person_entities[i].text` |

## Deviations from Plan

None — plan executed exactly as written. The plan's full target file content for Task 2 included a `# Entity import — verify the path matches anonymization.py's import before editing.` comment with `# noqa: E402`; on inspection of the actual file the `noqa` was redundant (no module-level statement precedes the import) and was omitted to keep the file lint-clean. Functional behavior is identical.

## Plans Unblocked

- **Plan 03-04** (`LLMProviderClient`) — imports `egress_filter`, `EgressResult`, `_EgressBlocked` from `egress.py`.
- **Plan 03-05** (redaction-service wiring) — consumes `cluster_persons`, `variants_for`, `Cluster` from `clustering.py`.

## Self-Check: PASSED

Files exist:
- `backend/app/services/redaction/nicknames_id.py` — FOUND
- `backend/app/services/redaction/clustering.py` — FOUND
- `backend/app/services/redaction/egress.py` — FOUND

Commits exist:
- `496cc57` — FOUND (Task 1)
- `86ce3d4` — FOUND (Task 2)
- `5510d80` — FOUND (Task 3)

39/39 Phase 1+2 tests still pass.
