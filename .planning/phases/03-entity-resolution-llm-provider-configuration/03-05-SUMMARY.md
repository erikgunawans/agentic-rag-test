---
phase: 03-entity-resolution-llm-provider-configuration
plan: 05
subsystem: redaction
tags: [phase-3, wave-5, integration, clustering, llm-provider, egress, registry]
dependency_graph:
  requires:
    - "03-01: Settings.entity_resolution_mode + LLM provider config columns"
    - "03-03: redaction/clustering.py — Cluster + cluster_persons + variants_for"
    - "03-03: redaction/egress.py — _EgressBlocked exception"
    - "03-04: services/llm_provider.py — LLMProviderClient"
    - "Phase 1: redaction/anonymization.py — Faker collision budget, _generate_surrogate"
    - "Phase 2: redaction/registry.py — ConversationRegistry, EntityMapping, upsert_delta"
    - "Phase 2: redaction_service.py — _thread_locks, RedactionResult, de_anonymize_text"
  provides:
    - "Cluster-aware anonymize() — one Faker surrogate per cluster, sub-surrogate variant rows"
    - "Mode-dispatched redact_text() — algorithmic / llm / none, all gated by per-thread asyncio.Lock"
    - "Egress-fallback path: _EgressBlocked + Exception → algorithmic clusters (NFR-3 preserved)"
    - "D-48 variant-row write-through via registry.upsert_delta"
  affects:
    - "Plan 03-07 (pytest coverage) — now unblocked"
    - "All future redact_text(text, registry) callers see cluster-aware behaviour transparently"
    - "Phase 4 fuzzy de-anonymization — variant rows now visible to de_anonymize_text"
tech_stack:
  added: []
  patterns:
    - "Mode dispatch via settings.entity_resolution_mode read once per call"
    - "Try/except wrapper around cloud-LLM call with two-tier algorithmic fallback (egress vs other)"
    - "Pre-cluster algorithmically BEFORE LLM call so the fallback set is always ready"
    - "Variant-row write-through: one canonical row + N variant rows per cluster, all sharing the same surrogate"
    - "Tie-break sort key in de_anonymize_text: (len(surrogate), len(real_value)) DESC"
key_files:
  created: []
  modified:
    - backend/app/services/redaction/anonymization.py
    - backend/app/services/redaction_service.py
decisions:
  - "Option A signature change for anonymize(masked_text, clusters, non_person_entities, registry) — no tests directly call anonymize(), so the migration is internal to redaction_service.py; the explicit contract makes Plan 03-07 tests easier to write"
  - "Mode dispatch lives in _redact_text_with_registry only — stateless path uses one-cluster-per-PERSON pseudo-clusters so D-39 'registry=None ⇒ legacy behaviour' is preserved without any branching"
  - "Algorithmic clusters are computed FIRST in mode=llm so the fallback answer is always ready; the LLM call only refines them"
  - "_resolve_clusters_via_llm is private at module scope (not a method) so it has no implicit dependency on RedactionService state"
  - "[Rule 1 - Bug] de_anonymize_text tie-breaks by len(real_value) DESC after len(surrogate_value) DESC — D-48 variant rows all share the same surrogate, so without the tie-break Pass 1 non-deterministically resolves to a variant's real_value (e.g. 'Maria') instead of the canonical ('Maria Santos')"
metrics:
  duration: ~22min
  completed_date: 2026-04-26
---

# Phase 3 Plan 05: Anonymization & Redaction Service Wiring Summary

Wired the Phase 3 cluster-aware pipeline into Phase 1's `anonymization.py` and Phase 2's `redaction_service.py`. After this plan, `redact_text(text, registry)` in any of three modes (`algorithmic` / `llm` / `none`) produces:
- **algorithmic:** Union-Find clustering via `redaction/clustering.py`
- **llm:** provider-aware via `services/llm_provider.py` with mandatory pre-flight egress filter; on any failure (egress trip, network, schema mismatch) falls back to algorithmic clusters
- **none:** passthrough — each PERSON entity becomes its own single-member pseudo-cluster

## Files Modified

| File | Lines (after) | Δ | Notes |
|------|---------------|---|-------|
| `backend/app/services/redaction/anonymization.py` | 365 | +108 / -28 | Option A signature + per-cluster Faker dispatch |
| `backend/app/services/redaction_service.py` | 691 | +360 / -71 | Mode dispatch + LLM call + variant-row writes + tie-break sort fix |

## Option Chosen for `anonymize()` Signature

**Option A (explicit signature change).** Rationale:
- `git grep` confirmed no test files call `anonymize()` directly — only `redaction_service.py` does.
- Plan 03-07's tests will exercise the new shape; Option A makes the contract obvious to that work.
- Plan author's recommendation.
- Migration cost: 1 file (redaction_service.py), 0 test files.

New signature:

```python
def anonymize(
    masked_text: str,
    clusters: list[Cluster],          # PERSON, pre-grouped (D-45)
    non_person_entities: list[Entity], # EMAIL/PHONE/URL/... (D-62)
    registry: "ConversationRegistry | None" = None,
) -> tuple[str, dict[str, str], int]:
```

## D-61 8-Step Flow Implemented

Inside the per-thread `asyncio.Lock` (acquired by `redact_text` at the top of the call):

1. **Lock acquired** by caller `redact_text` (existing — D-29 / D-30).
2. **Detect entities** (Presidio two-pass, unchanged).
3. **Cluster PERSON entities** (NEW — mode-dispatched on `settings.entity_resolution_mode`).
4. **Generate Faker surrogates per cluster** (NEW — `anonymize()` allocates ONE surrogate per cluster).
5. **Compose variant set per cluster** (existing — `variants_for` from Plan 03-03).
6. **Compute deltas + `await registry.upsert_delta(deltas)`** (NEW — variant rows for D-48 + non-PERSON path).
7. **Build entity_map for THIS call's text rewrite** (NEW — driven by cluster_surrogate map).
8. **Lock released** by caller (existing).

## asyncio.Lock Scope — Confirmed Unchanged

The Phase 2 D-30 invariant (per-thread `asyncio.Lock` spans the entire `redact_text(registry=...)` call) is preserved verbatim. The Phase 3 cluster + LLM call + variant-write code lives INSIDE `_redact_text_with_registry`, which is invoked from inside the existing `async with lock:` block in `redact_text`. No new lock surface; no new lock master.

The cloud-LLM call inside `LLMProviderClient` has a settings-controlled timeout (`settings.llm_provider_timeout_seconds`, default 30 s) so the lock is bounded under T-LOCK-01.

## `_EgressBlocked` Caught Locally — Confirmed

`_resolve_clusters_via_llm` wraps `await client.call(...)` in:

```python
try:
    ...
except _EgressBlocked as exc:
    # algorithmic fallback already computed
    return algorithmic_clusters, True, "egress_blocked", True
except Exception as exc:
    return algorithmic_clusters, True, type(exc).__name__, False
```

`_EgressBlocked` is caught at the resolution-service boundary — NEVER re-raised to the chat loop (NFR-3 invariant). `redact_text` never sees the exception; it always receives a final `clusters: list[Cluster]` answer. This is enforced by the `_resolve_clusters_via_llm` function signature (returns `tuple[list[Cluster], bool, str, bool]` — no exception path).

## D-62 / RESOLVE-04 Compliance — Confirmed

- `_split_person_non_person` filters `e.type == "PERSON"` before calling `cluster_persons`. EMAIL / PHONE / URL / LOCATION / DATE_TIME / IP_ADDRESS / hard-redact spans are routed through the existing per-entity Phase 1 + Phase 2 path inside `anonymize()`.
- `provisional_surrogates` map is built from `algorithmic_clusters` (PERSON-only).
- Non-PERSON entities NEVER reach `LLMProviderClient.call` — the resolution prompt only carries PERSON cluster JSON.

## D-48 Variant-Row Writes — Confirmed

For every cluster, `_redact_text_with_registry` now appends one `EntityMapping` row per variant in `cluster.variants` (canonical, bare, first-only, last-only, honorific-prefixed, nickname). All share the same `surrogate_value` (the cluster's canonical Faker surrogate). `seen_lower` set prevents within-call duplicates; `registry._by_lower` check prevents cross-turn duplicates. Funnelled through `registry.upsert_delta` which uses INSERT … ON CONFLICT (thread_id, real_value_lower) DO NOTHING (D-32 cross-process race-safe).

## Tracing Attributes (D-63)

The DEBUG-level log line in `_redact_text_with_registry` carries:
- `clusters` (count)
- `cluster_size_max`
- `merged_via` (algorithmic / llm / none)
- `provider_fallback` (bool)
- `egress_tripped` (bool)
- `fallback_reason` (exception type name or "egress_blocked")

Counts and type-names ONLY. NEVER raw values. NEVER `entity.text` / `cluster.canonical` / `members[0].text`. B4 / D-18 / D-41 / D-55 invariants preserved.

## Phase 1 + Phase 2 Regression: 39/39 Pass

```
$ pytest tests/ -x -q
39 passed, 12 warnings in 12.31s
```

Specifically:
- 20 Phase 1 tests in `tests/api/test_redaction.py` — Faker surrogates, gender matching, UUID survival, hard-redact path, singleton + tracing, all green.
- 15 Phase 2 integration tests in `tests/api/test_redaction_registry.py` — cross-turn surrogate reuse, B4 log-privacy, hard-redact survival, asyncio.gather race against entity_registry, all green.
- 4 Phase 2 unit tests in `tests/unit/test_conversation_registry.py` — `lookup` casefold, `entries` returns copy, `forbidden_tokens` PERSON-only, `thread_id` immutable, all green.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] de_anonymize_text non-deterministic mapping when D-48 variants share a surrogate**

- **Found during:** Task 2 verification (`test_titlecased_person_surrogate_resolves_to_original_real`)
- **Issue:** With D-48 variant write-through, every variant row in a cluster shares the SAME `surrogate_value`. The Phase 2 sort `key=lambda m: len(m.surrogate_value)` is stable but ties between variants are resolved by insertion order, so Pass 1 of `de_anonymize_text` could map the surrogate to a variant's `real_value` (e.g. `"Maria"`) instead of the canonical (`"Maria Santos"`). DEANON-02 promises round-trip to the **original real value's exact casing**, which means the canonical must win.
- **Fix:** Tie-break the sort by `len(real_value)` DESC after `len(surrogate_value)` DESC. The canonical real value is always the longest in its cluster (Plan 03-03 Wave 3 D-45 chose canonical = longest member text), so it wins the placeholder mapping in `de_anonymize_text` Pass 1.
- **Files modified:** `backend/app/services/redaction_service.py` (line ~640)
- **Commit:** `7813919` (folded into Task 2 commit since it's a single-line behaviour fix to the same file).

No Rule 2 or Rule 4 deviations.

## Smoke Test (Manual, In-Process)

Cluster shape verification with `Bambang Sutrisno` + `Pak Bambang` + `Sutrisno` + `Bambang` (no DB hop, just clustering):

```
clusters_formed=3
canonical='Bambang Sutrisno' variants_count=3 members_count=2
  variants=['Bambang', 'Bambang Sutrisno', 'Sutrisno']
canonical='Pak Bambang' variants_count=2 members_count=1
  variants=['Bambang', 'Pak Bambang']
canonical='Bambang' variants_count=1 members_count=1
  variants=['Bambang']
```

This is correct **D-47 strict-merge behaviour**: solo "Bambang" is ambiguous (could merge into either "Bambang Sutrisno" cluster or stand alone) so it's left as its own cluster. Plan 03-03 Wave 3 explicitly chose this trade-off — better to emit a duplicate surrogate than a wrong merge. The cluster split is unrelated to this plan's wiring work.

A live-DB smoke test verifying N variant rows per cluster is left for Plan 03-07's pytest suite (which runs against the `qedhulpfezucnfadlfiz` Supabase project).

## Plan 03-07 Status

**Now unblocked.** Plan 03-07 (pytest suite for Phase 3 success criteria) can now exercise:
- Multi-variant PERSON clustering produces N variant rows sharing one surrogate.
- Mode dispatch (algorithmic / llm / none) returns the right cluster shapes.
- Egress filter trip → algorithmic fallback (cloud LLM never reached).
- Cloud LLM 5xx → algorithmic fallback (NFR-3 — never crash).
- Span attributes carry the Phase 3 keys.

## Commits

| Task | Hash | Message |
|------|------|---------|
| 1 | `26fe66a` | feat(03-05): cluster-aware anonymize() signature + per-cluster Faker dispatch |
| 2 | `7813919` | feat(03-05): mode dispatch + variant-row writes + egress fallback in redaction_service |

## Self-Check: PASSED

- [x] `backend/app/services/redaction/anonymization.py` exists (365 lines).
- [x] `backend/app/services/redaction_service.py` exists (691 lines).
- [x] Commit `26fe66a` exists (`git log --oneline | grep 26fe66a`).
- [x] Commit `7813919` exists (`git log --oneline | grep 7813919`).
- [x] `from app.services.llm_provider import LLMProviderClient` present in `redaction_service.py`.
- [x] `from app.services.redaction.clustering import` present in `redaction_service.py`.
- [x] `from app.services.redaction.egress import _EgressBlocked` present in `redaction_service.py`.
- [x] `entity_resolution_mode` referenced in `redaction_service.py`.
- [x] `cluster_persons` called in `redaction_service.py`.
- [x] `provider_fallback` in tracing path.
- [x] `from app.main import app` returns `OK`.
- [x] `pytest tests/ -x -q` returns 39/39 passing.
