---
phase: 03-entity-resolution-llm-provider-configuration
plan: 05
type: execute
wave: 5
depends_on: [02, 03, 04]
files_modified:
  - backend/app/services/redaction/anonymization.py
  - backend/app/services/redaction_service.py
autonomous: true
requirements_addressed: [RESOLVE-01, RESOLVE-02, RESOLVE-03, RESOLVE-04, PROVIDER-04]
must_haves:
  truths:
    - "anonymization.py accepts pre-clustered PERSON entities (list[Cluster]) AND non-PERSON entities (list[Entity]) — D-45 input-shape revision"
    - "Each Cluster gets exactly ONE Faker surrogate; all variants in cluster.variants share it via the cluster_surrogate map"
    - "redaction_service.py runs cluster_persons() INSIDE the existing per-thread asyncio.Lock critical section (D-30 / D-61)"
    - "Mode dispatch: algorithmic (Union-Find) | llm (cloud + provisional + egress filter; local + raw) | none (no clustering, each Entity → own pseudo-cluster)"
    - "On _EgressBlocked OR any LLMProviderClient exception → fall back to algorithmic clusters (D-52 / D-54)"
    - "Variant rows written to entity_registry via existing upsert_delta path (D-48 — one canonical row + first-only + last-only + honorific-prefixed)"
    - "Non-PERSON entities (EMAIL, PHONE, URL) use exact-match normalization, NEVER reach the resolution LLM (D-62 / RESOLVE-04)"
    - "Phase 1 + Phase 2 invariants preserved: B4 log invariant, D-30 lock scope, D-32 INSERT-ON-CONFLICT-DO-NOTHING upsert path, D-37 cross-turn forbidden tokens"
  artifacts:
    - path: "backend/app/services/redaction/anonymization.py"
      provides: "Cluster-aware anonymize() — one Faker call per cluster, sub-surrogate variant rows"
      contains: "list[Cluster]"
    - path: "backend/app/services/redaction_service.py"
      provides: "Mode-dispatched clustering inside the asyncio.Lock; egress fallback"
      contains: "entity_resolution_mode"
  key_links:
    - from: "backend/app/services/redaction_service.py"
      to: "backend/app/services/redaction/clustering.py"
      via: "cluster_persons(person_entities) call inside redact_text"
      pattern: "from app\\.services\\.redaction\\.clustering import"
    - from: "backend/app/services/redaction_service.py"
      to: "backend/app/services/llm_provider.py"
      via: "LLMProviderClient().call('entity_resolution', ...) on mode=llm"
      pattern: "LLMProviderClient"
    - from: "backend/app/services/redaction_service.py"
      to: "backend/app/services/redaction/egress.py"
      via: "_EgressBlocked exception caught for D-54 fallback"
      pattern: "_EgressBlocked"
    - from: "backend/app/services/redaction/anonymization.py"
      to: "backend/app/services/redaction/clustering.py"
      via: "Cluster type accepted as input parameter"
      pattern: "Cluster"
---

<objective>
Wire the Phase 3 cluster-aware pipeline into Phase 1's `anonymization.py` and Phase 2's `redaction_service.py`. After this plan, a `redact_text(text, registry)` call in any of three modes (`algorithmic` / `llm` / `none`) produces:
1. The same cluster-canonical surrogate for every variant in a coreference cluster.
2. One canonical row plus 3-4 variant rows (first-only / last-only / honorific-prefixed / nickname) in `entity_registry` per cluster.
3. A correct fall-back to algorithmic mode on any cloud-LLM failure (network / 5xx / `_EgressBlocked`).

Purpose: Wave 5 — the integration step that makes RESOLVE-01..04 + PROVIDER-04 observable end-to-end. Phase 1 + Phase 2 invariants (B4 log privacy, D-30 lock, D-32 upsert) MUST be preserved.

Output: Two file modifications. anonymization.py grows ~70 lines (cluster-aware path); redaction_service.py grows ~60 lines (mode dispatch + egress fallback wrapper).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md
@.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md
@.planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md
@CLAUDE.md
@backend/app/services/redaction/anonymization.py
@backend/app/services/redaction_service.py
@backend/app/services/redaction/registry.py
@backend/app/services/redaction/clustering.py
@backend/app/services/redaction/egress.py
@backend/app/services/llm_provider.py
@backend/app/config.py

<interfaces>
<!-- Existing primitives this plan calls. Read once; no codebase exploration needed. -->

From backend/app/services/redaction/anonymization.py (Phase 1 + Phase 2 baseline):
- Public function `anonymize(masked_text: str, entities: list[Entity], registry: ConversationRegistry | None = None) -> tuple[str, dict[str, str], int]`.
- Returns (anonymized_text, entity_map, hard_redacted_count).
- Phase 1 D-07/D-08 + Phase 2 D-37 establish forbidden-token expansion from per-call PERSON names ∪ registry.forbidden_tokens().
- Faker dispatch is `_generate_surrogate(entity, faker, forbidden_tokens, used_surrogates)` — preserves the collision budget.
- Right-to-left rewrite is critical for offset stability — DO NOT REORDER.

From backend/app/services/redaction_service.py (Phase 2 final shape after commits d0b8dc3 + 9cc1f42):
- `RedactionService` class with method `redact_text(text: str, thread_id: str | None = None) -> RedactionResult`.
- Per-thread asyncio.Lock created at module load; `_thread_locks: dict[str, asyncio.Lock] = {}`.
- The lock is acquired at the top of `redact_text` and held through the entire call; D-30 invariant.
- Phase 1 detection (Presidio two-pass) runs INSIDE the lock; produces `list[Entity]`.
- Phase 2 calls `registry = await ConversationRegistry.load(thread_id)` and passes registry to anonymize.
- `RedactionResult` is the existing return shape — likely `dataclass` or `BaseModel` with `anonymized_text`, `entity_map`, `hard_redacted_count`, plus tracing-attribute fields. Read the file to confirm.

From backend/app/services/redaction/clustering.py (Plan 03-03 Task 2 output):
- `Cluster(canonical: str, variants: frozenset[str], members: tuple[Entity, ...])`.
- `cluster_persons(person_entities: list[Entity]) -> list[Cluster]`.
- `variants_for(canonical: str) -> frozenset[str]`.

From backend/app/services/redaction/egress.py (Plan 03-03 Task 3 output):
- `egress_filter`, `EgressResult`, `_EgressBlocked` — already used by `LLMProviderClient`. Plan 03-05 catches `_EgressBlocked` at the redaction-service boundary.

From backend/app/services/llm_provider.py (Plan 03-04 output):
- `LLMProviderClient.call(feature, messages, registry=None, provisional_surrogates=None) -> dict`.

From backend/app/config.py (Plan 03-01 output):
- `settings.entity_resolution_mode: Literal["algorithmic", "llm", "none"]`.

D-61 critical-section flow (verbatim from CONTEXT.md):
1. Acquire per-thread asyncio.Lock.
2. Detect entities (Presidio two-pass).
3. **Cluster PERSON entities** (Phase 3 — algorithmic / llm / none branch).
4. Generate Faker surrogates per cluster (Phase 1 collision budget preserved).
5. **Compose variant set per cluster** (D-48 first-only / last-only / honorific-prefixed).
6. Compute deltas vs loaded registry; `await registry.upsert_delta(deltas)` (Phase 2 D-32).
7. Build entity_map for THIS call's text rewrite using ALL variant rows.
8. Release the lock; return RedactionResult.

D-62 (RESOLVE-04): Non-PERSON entities (EMAIL, PHONE, URL, LOCATION, DATE_TIME, IP_ADDRESS) use the EXISTING Phase 1 path — Faker surrogates per entity, no clustering, no LLM. The cluster_persons call receives PERSON-typed entities ONLY.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Revise anonymization.py — cluster-aware Faker surrogate path</name>
  <files>backend/app/services/redaction/anonymization.py</files>
  <behavior>
    - The `anonymize` function MUST accept clusters (PERSON, pre-grouped) AND non-PERSON entities (Phase 1 path). The exact signature shape is the executor's choice, but two compatible options are acceptable:
      - Option A (preferred — explicit signature change): `anonymize(masked_text, clusters: list[Cluster], non_person_entities: list[Entity], registry=None) -> tuple[anonymized_text, entity_map, hard_redacted_count]`. Call sites in redaction_service.py update accordingly (Task 2).
      - Option B (back-compat — keep flat-list signature, branch internally): `anonymize(masked_text, entities, registry=None, *, clusters=None)`. If `clusters` is provided, group PERSON members through them; otherwise fall back to Phase 1 path. Lower-blast-radius; Plan 03-07 tests can exercise both.
    - The executor's choice MUST keep Phase 1's 20 tests passing (verified via `pytest tests/api/test_redaction.py`). Pick whichever option requires the fewest unrelated test edits.
    - Each cluster's canonical real name maps to ONE Faker surrogate (one `_generate_surrogate` invocation per cluster). All cluster.members spans rewrite to that one surrogate.
    - Non-PERSON entities flow through the existing Phase 1 path unchanged (D-62 / RESOLVE-04 — no clustering, no LLM contact).
    - Phase 2 D-37 forbidden_tokens still computed from real-PERSON tokens (now flattened from cluster members) ∪ registry.forbidden_tokens().
    - Right-to-left rewrite preserved for offset stability.
    - Hard-redact path (Phase 1 D-08) preserved verbatim — `[ENTITY_TYPE]` placeholder; never registered.
  </behavior>
  <read_first>
    - backend/app/services/redaction/anonymization.py (Phase 1 + Phase 2 baseline — read the ENTIRE file before editing; the right-to-left rewrite loop, the forbidden-token expansion, and the hard-redact path are each non-trivial)
    - backend/app/services/redaction/clustering.py (Plan 03-03 Task 2 output — Cluster dataclass + variants_for)
    - backend/app/services/redaction/registry.py (ConversationRegistry.lookup signature — used to detect already-registered cluster canonicals)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md D-45, D-48, D-61, D-62
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"backend/app/services/redaction/anonymization.py" (full pseudo-diff with input-shape change)
    - .planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md D-05/D-06/D-07/D-08 (Faker collision budget + per-call forbidden tokens)
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md D-37, D-38 (cross-turn forbidden tokens — PERSON only)
  </read_first>
  <action>
Open `backend/app/services/redaction/anonymization.py`. Read the full file FIRST — the rewrite loop, the forbidden-token expansion, the Faker dispatch, and the hard-redact path are all non-trivial.

Pick Option A or Option B per the behaviour block. The recommendation is Option A (explicit signature change) — it makes the contract obvious to redaction_service.py and to Plan 03-07 tests. With Option A:

1. **Imports** — add at the top of the file:
```python
from app.services.redaction.clustering import Cluster
```

2. **Signature change** — replace the existing `def anonymize(...)` line with:
```python
def anonymize(
    masked_text: str,
    clusters: list[Cluster],                          # D-45: pre-clustered PERSON groups
    non_person_entities: list["Entity"],              # D-62: emails/phones/URLs flow through existing path
    registry: "ConversationRegistry | None" = None,
) -> tuple[str, dict[str, str], int]:
```

3. **Forbidden-token expansion** — replace the Phase 1 + Phase 2 line that built `real_persons` from a flat entity list:
```python
# OLD (Phase 1 + Phase 2):
# real_persons = [e.text for e in entities if e.type == "PERSON"]
# NEW (Phase 3 — flatten from cluster members):
real_persons = [m.text for c in clusters for m in c.members]
bare_persons = [strip_honorific(name)[1] for name in real_persons]
call_forbidden = extract_name_tokens(bare_persons)
if registry is not None:
    forbidden_tokens = call_forbidden | registry.forbidden_tokens()
else:
    forbidden_tokens = call_forbidden
```

4. **Per-cluster Faker dispatch** — INSERT a new pre-rewrite block that allocates ONE surrogate per cluster:
```python
# D-45 / D-48: one Faker surrogate per cluster — variants share it.
cluster_surrogate: dict[str, str] = {}  # casefold(canonical) → surrogate
for cluster in clusters:
    key = cluster.canonical.casefold()
    if registry is not None:
        existing = registry.lookup(cluster.canonical)
        if existing is not None:
            cluster_surrogate[key] = existing
            used_surrogates.add(existing)
            continue
    # Synthesize a single Entity for the canonical to drive _generate_surrogate;
    # the existing collision budget + forbidden-token check still apply.
    pseudo = Entity(
        text=cluster.canonical,
        type="PERSON",
        start=0,
        end=len(cluster.canonical),
        # Whatever bucket field name Phase 1 used — read anonymization.py to confirm.
        bucket="surrogate",
    )
    surrogate = _generate_surrogate(pseudo, faker, forbidden_tokens, used_surrogates)
    cluster_surrogate[key] = surrogate
    used_surrogates.add(surrogate)
```

NOTE — the exact `Entity` constructor field names depend on Phase 1. The executor MUST grep `backend/app/services/redaction/detection.py` (or wherever Phase 1 declared the dataclass) to confirm. The example uses `bucket="surrogate"` based on Phase 1 D-04's two-pass classification; if the field is named `category` / `pii_class` / etc., adjust accordingly.

5. **Right-to-left rewrite** — replace the existing `for ent in sorted(entities, ...)` loop with a unified loop over BOTH cluster members and non-PERSON entities:
```python
# Build the unified rewrite list: each tuple is (Entity, cluster_replacement_or_None).
all_spans: list[tuple["Entity", str | None]] = []
for cluster in clusters:
    surrogate = cluster_surrogate[cluster.canonical.casefold()]
    for member in cluster.members:
        all_spans.append((member, surrogate))
for ent in non_person_entities:
    all_spans.append((ent, None))

out = masked_text
for ent, cluster_replacement in sorted(
    all_spans, key=lambda pair: pair[0].start, reverse=True,
):
    if ent.bucket == "redact":
        replacement = f"[{ent.type}]"  # D-08 hard-redact
        hard_redacted_count += 1
    elif cluster_replacement is not None:
        # PERSON: cluster surrogate already chosen above.
        replacement = cluster_replacement
        entity_map[ent.text] = replacement
    else:
        # Non-PERSON: existing Phase 1 + Phase 2 per-entity path.
        existing = entity_map.get(ent.text) or next(
            (v for k, v in entity_map.items() if k.lower() == ent.text.lower()),
            None,
        )
        if existing is not None:
            replacement = existing
        elif registry is not None:
            registry_hit = registry.lookup(ent.text)
            if registry_hit is not None:
                replacement = registry_hit
                entity_map[ent.text] = replacement
            else:
                replacement = _generate_surrogate(ent, faker, forbidden_tokens, used_surrogates)
                entity_map[ent.text] = replacement
                used_surrogates.add(replacement)
        else:
            replacement = _generate_surrogate(ent, faker, forbidden_tokens, used_surrogates)
            entity_map[ent.text] = replacement
            used_surrogates.add(replacement)
    out = out[: ent.start] + replacement + out[ent.end :]

return out, entity_map, hard_redacted_count
```

6. **DO NOT** change `_generate_surrogate` itself — collision budget, gender-matching, forbidden_tokens, used_surrogates all remain Phase 1 behaviour.

7. **DO NOT** change the right-to-left ordering — offset stability requires it.

8. **DO NOT** alter the hard-redact path (`[ENTITY_TYPE]` placeholder) — it must continue to bypass the registry per Phase 1 D-08 / Phase 2 D-24.

After editing, run the Phase 1 + Phase 2 regression to confirm no behavioural drift on the existing test surface:
```bash
cd backend && source venv/bin/activate && pytest tests/ -x
```
The 39/39 pass count should hold. If it drops, the call sites in `redaction_service.py` (Task 2) are the most likely fix point — Plan 03-07 will add Phase 3 tests last.

CLAUDE.md gotcha: PostToolUse hook will run py_compile + import check on save. The import-check requires backend imports to remain clean.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "
from app.services.redaction.anonymization import anonymize
import inspect
sig = inspect.signature(anonymize)
params = list(sig.parameters.keys())
# Option A: clusters + non_person_entities present
# Option B: entities present + 'clusters' kwarg
has_clusters_param = 'clusters' in params
has_non_person = 'non_person_entities' in params
assert has_clusters_param or 'entities' in params, f'unexpected signature: {params}'
src = open('backend/app/services/redaction/anonymization.py').read()
assert 'cluster_surrogate' in src, 'per-cluster surrogate map missing'
assert 'cluster.canonical' in src or 'cluster.members' in src, 'Cluster fields not used'
assert 'from app.services.redaction.clustering import' in src, 'Cluster import missing'
print('ANONYMIZATION_OK')
" 2>&1 | grep -q "ANONYMIZATION_OK" && cd backend && source venv/bin/activate && pytest tests/ -x -q 2>&1 | tail -5 | grep -E "[0-9]+ passed"</automated>
  </verify>
  <acceptance_criteria>
    - File `backend/app/services/redaction/anonymization.py` imports `Cluster` from `app.services.redaction.clustering`.
    - Function `anonymize` signature accepts either `clusters: list[Cluster]` (Option A) or has a `clusters` keyword parameter (Option B).
    - File contains the literal `cluster_surrogate` (the per-cluster surrogate map).
    - File contains a loop iterating over `cluster.members` (cluster expansion).
    - File contains the literal `forbidden_tokens` expansion using `registry.forbidden_tokens()` (Phase 2 D-37 preserved).
    - File contains `_generate_surrogate(...)` call (Phase 1 collision budget preserved).
    - File contains right-to-left iteration: `sorted(..., key=..., reverse=True)`.
    - Hard-redact path preserved: file contains the literal `f"[{ent.type}]"` and `hard_redacted_count`.
    - All Phase 1 + Phase 2 tests still pass: `pytest tests/ -x` returns 39/39 (or shows the new option-A migration touched 1-2 test signatures, in which case Task 2's redaction_service edits compensate — but the run must still be GREEN).
  </acceptance_criteria>
  <done>anonymize() rewritten to per-cluster Faker dispatch; Phase 1 + Phase 2 invariants preserved; existing tests still pass.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire mode dispatch + variant-row writes + egress fallback into redaction_service.py</name>
  <files>backend/app/services/redaction_service.py</files>
  <behavior>
    - `redact_text(text, thread_id)` reads `settings.entity_resolution_mode` once at the top of the call.
    - Phase 1 detection runs unchanged — produces `list[Entity]`.
    - PERSON entities are split out and routed through the mode dispatcher; non-PERSON entities flow through the existing Phase 1 + Phase 2 path (D-62).
    - Mode `algorithmic`: `clusters = cluster_persons(person_entities)`.
    - Mode `llm`:
        - First, `algorithmic_clusters = cluster_persons(person_entities)`.
        - Build `provisional_surrogates: dict[str, str]` from `algorithmic_clusters` (real_value → algorithmic Faker surrogate placeholder used for the cloud preview only).
        - Construct `messages` = the resolution prompt (system + user JSON-instruction).
        - Try `await LLMProviderClient().call("entity_resolution", messages, registry, provisional_surrogates)`.
        - On `_EgressBlocked`: log `provider_fallback=True`, `fallback_reason=egress_blocked`; use `algorithmic_clusters` as final clusters.
        - On any other exception: log `provider_fallback=True`, `fallback_reason=<network|invalid_response|...>`; use `algorithmic_clusters`.
        - On success: parse the LLM result into refined `clusters` (D-49 caller owns schema validation; for Phase 3 the simplest schema is `{"clusters": [{"canonical": "...", "members": ["..."]}, ...]}` — caller falls back to algorithmic if validation fails).
    - Mode `none`: each PERSON entity becomes its own pseudo-cluster (canonical=entity.text, variants=variants_for(entity.text), members=(entity,)). Span tag `mode="none"` for OBS.
    - After clusters are finalised, call `anonymize(text, clusters, non_person_entities, registry)` with the chosen Option-A signature (or whichever Plan 03-05 Task 1 chose).
    - Variant-row writes: for each cluster, build the deltas list — one row per variant in `cluster.variants` with the SAME surrogate (the cluster's canonical surrogate from the entity_map). Pass to `await registry.upsert_delta(deltas)` — D-32 INSERT-ON-CONFLICT-DO-NOTHING handles cross-thread races.
    - Span attributes extended (D-63): `resolution_mode`, `clusters_formed`, `cluster_size_max`, `clusters_merged_via`, `provider_resolved` (mode=llm), `provider_fallback`, `egress_tripped`. NEVER raw values.
    - The asyncio.Lock scope (Phase 2 D-30) is preserved — clustering + LLM call + variant writes ALL happen INSIDE the lock.
  </behavior>
  <read_first>
    - backend/app/services/redaction_service.py (Phase 2 final shape — read the FULL file before editing; the redact_text method, the per-thread asyncio.Lock acquisition, and the existing entity_map flow are non-trivial)
    - backend/app/services/redaction/anonymization.py (Plan 03-05 Task 1 output — confirm the new signature)
    - backend/app/services/redaction/clustering.py (Cluster type + cluster_persons + variants_for)
    - backend/app/services/llm_provider.py (LLMProviderClient signature)
    - backend/app/services/redaction/egress.py (_EgressBlocked exception type)
    - backend/app/config.py (settings.entity_resolution_mode read path)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md D-45, D-48, D-49, D-52, D-54, D-61, D-63
    - .planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md D-30, D-32, D-37 (lock scope + upsert path + cross-turn forbidden)
  </read_first>
  <action>
Open `backend/app/services/redaction_service.py`. Read the FULL file. Identify:
- The `redact_text(self, text: str, thread_id: str | None = None)` method.
- The `async with self._thread_locks[thread_id]:` (or equivalent) Phase 2 D-30 lock acquisition.
- The Presidio detection call that produces `list[Entity]`.
- The existing `await registry.upsert_delta(...)` call (Phase 2 D-32).
- The existing `anonymize(...)` call (Phase 1 + Phase 2).
- The `RedactionResult` dataclass / Pydantic model and where its tracing-attribute dict is built.

Add the following imports at the top:
```python
from app.config import get_settings
from app.services.llm_provider import LLMProviderClient
from app.services.redaction.clustering import Cluster, cluster_persons, variants_for
from app.services.redaction.egress import _EgressBlocked
```

Inside the asyncio.Lock critical section, after the Presidio detection step that yields `entities: list[Entity]`, INSERT the following block (before the existing `anonymize(...)` call):

```python
# D-61 step 3: split PERSON from non-PERSON; cluster PERSON entities by mode.
person_entities = [e for e in entities if e.type == "PERSON"]
non_person_entities = [e for e in entities if e.type != "PERSON"]

settings = get_settings()
mode = settings.entity_resolution_mode  # 'algorithmic' | 'llm' | 'none'

# Tracing accumulators (D-63). NEVER store raw values here.
provider_resolved: str | None = None
provider_fallback = False
egress_tripped = False
fallback_reason = ""

if mode == "algorithmic":
    clusters = cluster_persons(person_entities)
    clusters_merged_via = "algorithmic"
elif mode == "none":
    # D-62 / Claude's Discretion §"none" mode: explicit pass-through; one pseudo-cluster
    # per PERSON entity (each unique string gets its own surrogate, no merges).
    clusters = [
        Cluster(
            canonical=e.text,
            variants=variants_for(e.text),
            members=(e,),
        )
        for e in person_entities
    ]
    clusters_merged_via = "none"
else:
    # mode == "llm" — pre-cluster algorithmically, then ask the LLM to refine.
    algorithmic_clusters = cluster_persons(person_entities)
    clusters_merged_via = "llm"

    # Build provisional_surrogates for cloud egress filter (D-56).
    # Algorithmic Faker output isn't computed yet (anonymize() does that), so
    # for the egress-filter scope we just use the canonical real values as keys
    # mapped to themselves (the egress filter scans BOTH registry entries AND
    # the in-flight set — using canonical real values here keeps the filter scope
    # exhaustive without leaking provisional surrogates that don't exist yet).
    provisional_surrogates: dict[str, str] = {
        c.canonical: c.canonical for c in algorithmic_clusters
    }

    # Compose the resolution prompt — schema documented in CONTEXT.md D-49.
    prompt_clusters = [
        {"canonical": c.canonical, "members": [m.text for m in c.members]}
        for c in algorithmic_clusters
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "You are a coreference resolver. The user provides preliminary "
                "PERSON clusters. Return JSON {\"clusters\": [{\"canonical\": str, "
                "\"members\": list[str]}, ...]} with the same members regrouped "
                "if you can identify obvious mergeable clusters; otherwise return "
                "the input unchanged. Never invent names. Never include any text "
                "outside the JSON object."
            ),
        },
        {"role": "user", "content": json.dumps({"clusters": prompt_clusters}, ensure_ascii=False)},
    ]

    try:
        client = LLMProviderClient()
        result = await client.call(
            feature="entity_resolution",
            messages=messages,
            registry=registry,
            provisional_surrogates=provisional_surrogates,
        )
        # Parse the LLM-refined clusters; on any schema mismatch fall back.
        refined = result.get("clusters") if isinstance(result, dict) else None
        if not isinstance(refined, list):
            raise ValueError("invalid resolution response")
        # Build clusters from the LLM's regrouping. We re-attach Entity members by
        # looking up each member text in the algorithmic-cluster member pool.
        text_to_entity: dict[str, "Entity"] = {
            m.text: m for c in algorithmic_clusters for m in c.members
        }
        clusters_built: list[Cluster] = []
        for entry in refined:
            canonical = entry.get("canonical") if isinstance(entry, dict) else None
            members_raw = entry.get("members") if isinstance(entry, dict) else None
            if not isinstance(canonical, str) or not isinstance(members_raw, list):
                raise ValueError("invalid resolution response entry")
            members = tuple(text_to_entity[m] for m in members_raw if m in text_to_entity)
            if not members:
                continue
            clusters_built.append(
                Cluster(
                    canonical=canonical,
                    variants=variants_for(canonical),
                    members=members,
                )
            )
        # If the LLM returned no usable clusters, fall back.
        if not clusters_built:
            raise ValueError("resolution response empty after re-attach")
        clusters = clusters_built
        provider_resolved = "cloud-or-local"  # the resolver itself logs the actual one
    except _EgressBlocked as exc:
        # D-54: trip detected pre-call. Algorithmic fallback (already computed).
        clusters = algorithmic_clusters
        provider_fallback = True
        egress_tripped = True
        fallback_reason = "egress_blocked"
        # The egress filter already logged a WARNING with hashes-only.
        # We log the fallback decision at INFO; counts only.
        logger.info(
            "redaction.llm_fallback reason=egress_blocked clusters_formed=%d match_count=%d",
            len(algorithmic_clusters), exc.result.match_count,
        )
    except Exception as exc:
        # Network / 5xx / invalid_response / etc — algorithmic fallback (D-52).
        clusters = algorithmic_clusters
        provider_fallback = True
        fallback_reason = f"{type(exc).__name__}"
        logger.info(
            "redaction.llm_fallback reason=%s clusters_formed=%d",
            type(exc).__name__, len(algorithmic_clusters),
        )
```

Replace the existing `anonymize(masked_text, entities, registry)` call with the new signature:
```python
anonymized_text, entity_map, hard_redacted_count = anonymize(
    masked_text=masked_text,
    clusters=clusters,
    non_person_entities=non_person_entities,
    registry=registry,
)
```

If Plan 03-05 Task 1 chose Option B (back-compat signature), use the kwarg-style call instead:
```python
anonymized_text, entity_map, hard_redacted_count = anonymize(
    masked_text, entities, registry=registry, clusters=clusters,
)
```

After `anonymize` returns, BEFORE the existing `await registry.upsert_delta(...)` call, EXTEND the deltas list to include variant rows (D-48):

```python
# Build the variant-row deltas for D-48 sub-surrogate write-through.
# Each variant of every cluster gets its own row pointing to the cluster's
# canonical surrogate; future thread mentions hit the registry directly.
deltas = []  # whatever Phase 2 named the deltas accumulator — adapt to existing var name
for cluster in clusters:
    canonical_surrogate = entity_map.get(cluster.canonical)
    if not canonical_surrogate:
        # Cluster's canonical was already in registry → no new delta needed.
        continue
    seen_real = set()
    for variant in cluster.variants:
        if variant.casefold() in seen_real:
            continue
        seen_real.add(variant.casefold())
        # The variant rows ALL share the same canonical_surrogate (D-48).
        # The shape of a delta tuple/dict is whatever Phase 2's upsert_delta
        # signature accepts (likely (real_value, surrogate, entity_type) or a
        # dict with those keys). Read registry.upsert_delta signature to confirm.
        deltas.append({
            "real_value": variant,
            "surrogate_value": canonical_surrogate,
            "entity_type": "PERSON",
        })

# Add non-PERSON deltas (Phase 2 path) — keep whatever Phase 2 was already doing.
for ent in non_person_entities:
    surrogate = entity_map.get(ent.text)
    if surrogate is None:
        continue
    if registry is not None and registry.lookup(ent.text) is not None:
        continue  # already in registry
    deltas.append({
        "real_value": ent.text,
        "surrogate_value": surrogate,
        "entity_type": ent.type,
    })

if registry is not None and deltas:
    await registry.upsert_delta(deltas)
```

NB — the EXACT shape of `deltas` (tuple vs dict, field names) depends on Phase 2's `upsert_delta` signature. The executor MUST grep `backend/app/services/redaction/registry.py` for the `def upsert_delta` definition and adapt the dict keys to match. If Phase 2 used `EntityMapping` instances directly, build them via `EntityMapping(...)` calls instead.

EXTEND the tracing-attributes dict (Phase 2 D-41) with the Phase 3 fields (D-63):
```python
# Existing Phase 2 attrs preserved; Phase 3 extends.
span_attrs.update({
    "resolution_mode": mode,
    "clusters_formed": len(clusters),
    "cluster_size_max": max((len(c.members) for c in clusters), default=0),
    "clusters_merged_via": clusters_merged_via,
})
if mode == "llm":
    span_attrs["provider_fallback"] = provider_fallback
    span_attrs["egress_tripped"] = egress_tripped
    if fallback_reason:
        span_attrs["fallback_reason"] = fallback_reason
```

Hard rules (verify after editing):
- The new clustering + LLM-call + variant-write block is INSIDE the existing `async with self._thread_locks[thread_id]:` (or whatever Phase 2 named the lock acquisition). NO new lock surface; NO new lock master.
- The `_EgressBlocked` exception is caught locally — NEVER re-raised to the caller (chat loop). NFR-3 invariant.
- All `logger.info` / `logger.debug` calls log COUNTS / TYPE-NAMES only. NEVER raw values, NEVER `entity.text`, NEVER `members[0].text`.
- `cluster_persons` is called with PERSON-typed entities only (D-62 — non-PERSON never reaches the resolution LLM).
- Mode `none` produces one cluster per entity (no merges).
- Mode `algorithmic` and `none` MUST NOT instantiate `LLMProviderClient`.

After the rewrite, run the full regression:
```bash
cd backend && source venv/bin/activate && pytest tests/ -x
```
The 39/39 pass count from Phase 1+2 should hold (Plan 03-07 adds Phase 3 tests).
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')" 2>&1 | grep -q "OK" && cd backend && source venv/bin/activate && pytest tests/ -x -q 2>&1 | tail -5 | grep -E "[0-9]+ passed" && grep -q "from app.services.llm_provider import LLMProviderClient" backend/app/services/redaction_service.py && grep -q "from app.services.redaction.clustering import" backend/app/services/redaction_service.py && grep -q "from app.services.redaction.egress import _EgressBlocked" backend/app/services/redaction_service.py && grep -q "entity_resolution_mode" backend/app/services/redaction_service.py && grep -q "cluster_persons" backend/app/services/redaction_service.py && grep -q "_EgressBlocked" backend/app/services/redaction_service.py && grep -q "provider_fallback" backend/app/services/redaction_service.py && echo "REDACTION_SERVICE_OK"</automated>
  </verify>
  <acceptance_criteria>
    - `backend/app/services/redaction_service.py` imports `LLMProviderClient`, `cluster_persons`, `variants_for`, `Cluster`, and `_EgressBlocked`.
    - File contains a read of `settings.entity_resolution_mode` (or via `get_settings().entity_resolution_mode`).
    - File contains three branches keyed on `mode == "algorithmic"`, `mode == "llm"`, `mode == "none"`.
    - The `llm` branch instantiates `LLMProviderClient()` and `await`s `.call(feature="entity_resolution", ...)`.
    - The `llm` branch passes BOTH `registry=registry` AND `provisional_surrogates=provisional_surrogates` to the call.
    - The `llm` branch wraps the call in `try ... except _EgressBlocked ... except Exception ...` with algorithmic fallback in BOTH except branches.
    - `cluster_persons(person_entities)` is called with PERSON-typed entities only — file contains `[e for e in entities if e.type == "PERSON"]` (or equivalent split).
    - Variant-row delta accumulation iterates over `cluster.variants` and appends delta entries with the same `surrogate_value = entity_map[cluster.canonical]`.
    - The new code is inside the existing per-thread `async with self._thread_locks` block (Phase 2 D-30 invariant).
    - `from app.main import app` imports cleanly.
    - `pytest tests/` returns ≥39 passing tests (Phase 1 + Phase 2 baseline preserved).
  </acceptance_criteria>
  <done>redaction_service.py wired with mode dispatch, egress fallback, variant-row writes; D-61 lock-scope invariant preserved; Phase 1 + Phase 2 tests still green.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| in-process: Phase 1 detection → Phase 3 clustering | PERSON entities are split out; non-PERSON never reaches the resolution LLM (D-62) |
| in-process: clustering → LLM provider client | The provisional_surrogates dict is built here and crosses into the cloud-side egress filter |
| in-process: LLMProviderClient → algorithmic fallback | _EgressBlocked + Exception both caught at this boundary; never re-raised to chat loop (NFR-3) |
| in-process: clustering → registry.upsert_delta | Variant rows for D-48 are written through Phase 2's INSERT-ON-CONFLICT path |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-EGR-01 | Information Disclosure | Cloud LLM call leaks real value despite egress filter | mitigate | Provisional_surrogates dict spans every algorithmic-canonical real value (D-56); LLMProviderClient runs egress_filter against `registry.entries() ∪ provisional` BEFORE the SDK call. Plan 03-07 SC#2 test exercises end-to-end. |
| T-EGR-02 | Information Disclosure | Trip log line in redaction_service leaks raw value | mitigate | Acceptance criterion bans `entity.text` / `members[0].text` / raw value formatting in logger calls. The `redaction.llm_fallback` log uses counts + type-names only. |
| T-FALLBACK-01 | Reliability | _EgressBlocked re-raises to chat loop and crashes the request | mitigate | Both `except _EgressBlocked` AND `except Exception` set `clusters = algorithmic_clusters` and CONTINUE the redact_text flow. NFR-3 invariant: "never crash, never leak". |
| T-CLUST-01 | Tampering | LLM returns malformed JSON → clustering corrupts | mitigate | The `try` block validates the response shape (`isinstance(refined, list)`, per-entry dict checks); on any schema mismatch raises ValueError → falls back to algorithmic_clusters. |
| T-CLUST-02 | Tampering | LLM hallucinates names → cluster.members reference unknown text | mitigate | The text_to_entity map is built from algorithmic-cluster members only; entries referencing unknown text are silently dropped (`if m in text_to_entity`). Worst case: smaller cluster set → algorithmic-fallback-equivalent. Never invents members. |
| T-LOCK-01 | Reliability | The cloud LLM call hangs INSIDE the asyncio.Lock and blocks all other requests for this thread | mitigate | LLMProviderClient passes `timeout=settings.llm_provider_timeout_seconds` (default 30s) to AsyncOpenAI. SDK raises after timeout; caller catches and falls back. Lock is held ≤ 30s in worst case. |
| T-DATA-02 | Tampering | Variant-row writes produce duplicate rows or wrong surrogates | mitigate | Phase 2 D-32 INSERT-ON-CONFLICT-DO-NOTHING handles cross-thread races; the composite UNIQUE (thread_id, real_value_lower) deduplicates. Each variant for a cluster shares ONE surrogate (entity_map[cluster.canonical]); the per-cluster surrogate is computed exactly once per redact_text call. |
| T-PII-01 | Information Disclosure | mode="none" surfaces real PERSON values to subsequent calls (no clustering, no merging) | accept | `none` mode is explicitly a pass-through (Claude's Discretion); each PERSON entity gets its own surrogate, registry rows still written. The privacy-leak surface is no worse than Phase 2 (which already had no clustering). Documented as a span tag for OBS. |
</threat_model>

<verification>
After this plan completes:
- `git status` shows two modified files: `anonymization.py` + `redaction_service.py`.
- Backend imports cleanly: `python -c "from app.main import app; print('OK')"`.
- Phase 1 + Phase 2 regression: `pytest tests/ -x` returns ≥39/39 (no Phase 3 tests yet — Plan 03-07 adds them).
- A manual smoke-test against the live DB exercises mode=algorithmic with a multi-variant PERSON ("Bambang Sutrisno" + "Pak Bambang" + "Sutrisno" + "Bambang") and confirms 4 entity_registry rows share one surrogate.
- Plan 03-07 (pytest coverage) is unblocked.
</verification>

<success_criteria>
- anonymize() accepts clusters + non-PERSON entities; one Faker call per cluster; variants share the surrogate.
- redaction_service.py dispatches on mode (algorithmic / llm / none); D-61 8-step flow preserved.
- LLM mode wraps cloud call in try/except for `_EgressBlocked` + generic Exception → algorithmic fallback.
- Variant rows written through existing upsert_delta path (D-48 / D-32 invariants).
- Phase 1 + Phase 2 invariants preserved (B4 logs, D-30 lock scope, D-37 forbidden tokens).
- Tracing attributes extended with Phase 3 keys; NEVER raw values.
</success_criteria>

<output>
Create `.planning/phases/03-entity-resolution-llm-provider-configuration/03-05-SUMMARY.md` with:
- Files modified + line-count deltas
- Option chosen for anonymize signature (A or B) + rationale
- Confirmation that the asyncio.Lock scope is unchanged
- Confirmation that `_EgressBlocked` is caught locally (not re-raised)
- Phase 1 + Phase 2 regression: 39/39 still pass
- One smoke-test against live DB showing N variant rows per cluster (manual or scripted)
- Plan 03-07 (tests) is now unblocked.
</output>
