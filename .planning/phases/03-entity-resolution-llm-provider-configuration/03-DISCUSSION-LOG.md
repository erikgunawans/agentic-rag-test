# Phase 3: Entity Resolution & LLM Provider Configuration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 03-entity-resolution-llm-provider-configuration
**Areas discussed:** Algorithmic resolution, Provider abstraction, Pre-flight egress filter, Settings + admin UI

---

## Algorithmic Resolution

### Q1: Where in the redact_text pipeline does Union-Find clustering run for PERSON entities?

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-generation cluster | Cluster all detected PERSON spans BEFORE Faker generates surrogates. Each cluster gets one canonical surrogate; sub-variants share it. Single registry write per cluster. Cleanest for D-41 tracing + D-37 cross-turn forbidden tokens. Matches PRD FR-4.2 sub-surrogate derivation directly. | ✓ |
| Post-generation merge-pass | Phase 1-2 generates per-mention surrogates; a separate post-pass rewrites in-flight surrogates to a chosen canonical. Easier to bolt on, but requires DELETE + INSERT in the registry (breaks the simple INSERT-ON-CONFLICT path from D-32) and complicates the asyncio.Lock scope. | |
| Hybrid: cluster only NEW entities | Already-registered entities keep their surrogate from Phase 2; only NEW spans within the call go through clustering before generation. Simpler than a full re-clustering across the thread, but creates inconsistency if turn-1 happened to assign "Bambang"→4 different surrogates before clustering existed. | |

**User's choice:** Pre-generation cluster
**Notes:** Captured as D-45. Rationale: cleanest fit for Phase 2 D-32 INSERT-ON-CONFLICT-DO-NOTHING + preserves D-37 cross-turn forbidden-tokens.

---

### Q2: Where does the Indonesian-aware nickname dictionary live?

| Option | Description | Selected |
|--------|-------------|----------|
| Embedded Python dict | New `backend/app/services/redaction/nicknames_id.py` — same pattern as Phase 1's `gender_id.py`. Frozen dict[nickname → canonical]. Indonesian-first coverage. Zero startup cost beyond import. | ✓ |
| External JSON/YAML file | Bundled under `backend/app/services/redaction/data/nicknames.json`. Loaded once at lifespan startup. Easier to edit by non-coders, but no benefit over Python dict at v1.0 scale. | |
| DB table (admin-editable) | New `pii_nicknames` table with admin CRUD UI. Premature for v1.0 — dictionary is reference data, not config. | |

**User's choice:** Embedded Python dict
**Notes:** Captured as D-46. Tie-breaking on multi-canonical nicknames (e.g., "Iwan") = first-match deterministic + DEBUG log per OBS-02.

---

### Q3: How should Union-Find handle ambiguous solo-name merges?

| Option | Description | Selected |
|--------|-------------|----------|
| Strict per PRD: refuse to merge | When ambiguous, leave the solo mention as its own cluster (gets its own surrogate). Worst case is a duplicate surrogate, never a wrong merge. Logs the ambiguity at DEBUG for OBS-02. | ✓ |
| Most-recent-mention wins | Merge ambiguous solos with the most recently seen cluster (positional heuristic). Catches more references but can produce subtly wrong merges. | |
| Skip ambiguous solos entirely | Don't even generate a surrogate for ambiguous solo mentions — redact them as `[PERSON]` placeholders. Most conservative but breaks the user-readable round-trip experience. | |

**User's choice:** Strict per PRD
**Notes:** Captured as D-47. Conservative-by-design: blemish over corruption.

---

### Q4: How should sub-surrogate derivation work?

| Option | Description | Selected |
|--------|-------------|----------|
| Derive from canonical at registry-write | When a cluster is formed, write ALL variants (canonical + first-only + last-only + honorific-prefixed + nickname) into the registry as separate rows. Future thread mentions hit the registry directly without re-running clustering. | ✓ |
| Derive lazily on lookup | Registry stores only the canonical real↔surrogate row; lookup logic decomposes mentions and reassembles. Smaller registry but moves complexity into the hot path — defeats Phase 2's O(1) `casefold()` dict lookup (D-27). | |
| Eager full + sub-surrogates only on first cross-mention | Phase 1-2 already wrote canonical row; when Phase 3 sees a later "Walsh" mention and clusters it to that canonical, write the sub-surrogate row at that moment. Less write amplification but variable-time first-mention latency. | |

**User's choice:** Derive from canonical at registry-write
**Notes:** Captured as D-48. Trades disk for hot-path latency — right call given Phase 1 PERF-01 (sub-500ms).

---

## Provider Abstraction

### Q1: How should the LLM provider client be structured?

| Option | Description | Selected |
|--------|-------------|----------|
| Single LLMProviderClient with provider-aware branching | One class at `backend/app/services/llm_provider.py`. Reads global + per-feature config; resolves provider per call; branches to local (no key, no egress filter) or cloud (key required, pre-flight filter wraps the call). One place to enforce the egress invariant. | ✓ |
| Abstract base + LocalLLMClient / CloudLLMClient subclasses | ABC `LLMProviderBase` with two concrete classes. Cleaner type discrimination but doubles the test matrix and risks the egress filter being added to one subclass and not the other. | |
| Functional: provider_call(feature, payload) module functions | No class; just module-level functions per feature. Lightest surface but spreads the egress-filter enforcement across 5 callsites. | |

**User's choice:** Single LLMProviderClient with provider-aware branching
**Notes:** Captured as D-49. Centralizes the egress invariant — security-by-design.

---

### Q2: Which HTTP transport should the provider client use?

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse OpenAI Python SDK | OpenAI SDK already speaks `/v1/chat/completions` natively; works against LM Studio/Ollama/OpenAI/Together.ai by swapping `base_url`+`api_key`. Async via `AsyncOpenAI`. Zero new deps. | ✓ |
| Fresh httpx.AsyncClient | Direct httpx call to `/v1/chat/completions` with hand-rolled OpenAI-compat JSON. More control but reinvents what OpenAI SDK already does correctly. | |
| Both: OpenAI SDK + httpx for debug | OpenAI SDK does the real call; httpx is used only when DEBUG-level egress-filter introspection is enabled. Adds complexity without clear benefit. | |

**User's choice:** Reuse OpenAI Python SDK
**Notes:** Captured as D-50. Already a project dep for embeddings.

---

### Q3: How is per-feature provider override resolved at call time (FR-9.6)?

| Option | Description | Selected |
|--------|-------------|----------|
| Env-var first, then system_settings, then global default | Resolution order: `<FEATURE>_LLM_PROVIDER` env > `system_settings.<feature>_llm_provider` > `LLM_PROVIDER` env > `system_settings.llm_provider` > `"local"`. Env wins for ops; DB satisfies SC#5. | ✓ |
| system_settings first, then env-var, then default | DB-first order. Inverts ops expectations. | |
| Env-var only; system_settings is a read-only mirror | Defeats SC#5. | |

**User's choice:** Env-var first, then system_settings, then global default
**Notes:** Captured as D-51. Source-of-resolution logged per call for OBS-03 audit.

---

### Q4: Should LLM_PROVIDER_FALLBACK_ENABLED ship in Phase 3?

| Option | Description | Selected |
|--------|-------------|----------|
| Ship config knob now; default false; only algorithmic-fallback active | Add the env var + system_settings column. Knob plumbed but only the PRD NFR-3 default behavior fires. Cross-provider failover documented as Phase 6 hardening. | ✓ |
| Defer the knob entirely to Phase 6 | Forces an env-var rename and new system_settings column in Phase 6. Creates churn. | |
| Ship knob + cross-provider failover fully in Phase 3 | Bigger blast radius; outside Phase 3 SC#2 scope. | |

**User's choice:** Ship config knob now; default false; only algorithmic-fallback active
**Notes:** Captured as D-52. Stable env-var contract; no future migration churn.

---

## Pre-Flight Egress Filter

### Q1: What match algorithm should the pre-flight egress filter use?

| Option | Description | Selected |
|--------|-------------|----------|
| Casefold + word-boundary regex | Pattern `r'\b' + re.escape(value.casefold()) + r'\b'` against `payload.casefold()`. Catches "JOHN DOE" / "john doe." but not substrings of unrelated words. | ✓ |
| Casefold + exact substring match | Lowercase both sides. Produces false positives — registry "Mei" trips on payload "informasi". | |
| Strict equality of normalized tokens | Misses multi-word real values. | |
| Pluggable strategy with a sane default | Premature; security control should not be optional. | |

**User's choice:** Casefold + word-boundary regex
**Notes:** Captured as D-53. Composes with Phase 2 D-36 case-folding invariant.

---

### Q2: What happens when the filter trips?

| Option | Description | Selected |
|--------|-------------|----------|
| Abort the cloud call; fall back to algorithmic clustering | Per PRD NFR-3 + FR-9.7. Trip is a security-success. Logged as `egress_filter_blocked=true`. User-facing: chat continues normally. | ✓ |
| Raise PIIEgressViolation exception; let chat loop handle it | Conflicts with NFR-3's 'never crash the application' rule. | |
| Strip matching values from payload, then proceed | Hides upstream pre-anon bug; risky default. | |

**User's choice:** Abort the cloud call; fall back to algorithmic clustering
**Notes:** Captured as D-54.

---

### Q3: What gets recorded when the filter trips?

| Option | Description | Selected |
|--------|-------------|----------|
| Counts + entity_types + matched-value hashes | Span + log: `egress.tripped=true`, `match_count=N`, `entity_types=[…]`, `match_hashes=[sha256(value)[:8], …]`. NEVER raw values. Forensic-correlation-friendly. | ✓ |
| Counts + entity_types only | Loses forensic-correlation utility. | |
| Counts + entity_types + first-N-chars of matched value | B4 violation — "Bam..." identifies a person in a small Indonesian legal team. | |

**User's choice:** Counts + entity_types + matched-value hashes
**Notes:** Captured as D-55. B4 invariant strictly preserved.

---

### Q4: What does the filter scan against?

| Option | Description | Selected |
|--------|-------------|----------|
| Persisted registry + in-flight provisional set | Cloud-mode resolution sends provisional surrogates from this turn's pre-clustering. Filter must scan against `registry.entries()` AND the in-flight provisional dict. | ✓ |
| Persisted registry only | Misses first-turn-mention leaks. | |
| Full Presidio re-scan of the payload | Doubles warm-path cost; PRD design is registry-based, not NER-based. | |

**User's choice:** Persisted registry + in-flight provisional set
**Notes:** Captured as D-56. Filter input shape: `(payload, registry, provisional)`.

---

## Settings + Admin UI

### Q1: How should Phase 3's runtime-mutable settings be persisted?

| Option | Description | Selected |
|--------|-------------|----------|
| Add columns to existing `system_settings` table | New migration `030_pii_provider_settings.sql`. Matches existing single-row pattern; PATCH endpoint updates them; 60s cache refreshes. CHECK constraints enforce enums. | ✓ |
| New dedicated `redaction_settings` table | Doubles the cache, splits admin GET/PATCH. | |
| Single JSONB blob column on system_settings | Loses DB-level validation. | |

**User's choice:** Add columns to existing `system_settings` table
**Notes:** Captured as D-57. 9 new columns; all mode/provider fields use CHECK constraints.

---

### Q2: How is `CLOUD_LLM_API_KEY` stored and surfaced?

| Option | Description | Selected |
|--------|-------------|----------|
| Env-var only; admin UI shows masked status | Key in Railway env (existing pattern for `OPENAI_API_KEY`). Admin UI shows ✅/⚠️ badge. No DB write. | ✓ |
| Env-var primary; admin UI can write-through to env | Adds Railway-API dep; surfaces credential management to the app. | |
| Encrypted column on system_settings | Larger blast radius; key-mgmt-for-the-encryption-key. | |

**User's choice:** Env-var only; admin UI shows masked status
**Notes:** Captured as D-58. New `GET /admin/settings/llm-provider-status` endpoint surfaces the badge; never the raw key.

---

### Q3: Where does the admin UI live?

| Option | Description | Selected |
|--------|-------------|----------|
| New section in existing `/admin/settings` | Add a "PII Redaction & Provider" card to `AdminSettingsPage.tsx` alongside RAG/Tools sections. One PATCH endpoint; one save button. | ✓ |
| New dedicated `/admin/pii-redaction` page | Premature split for ~9 fields. | |
| Two surfaces: PII modes on one page, keys on another | UX hazard. | |

**User's choice:** New section in existing `/admin/settings`
**Notes:** Captured as D-59. i18n + audit_log via existing patterns.

---

### Q4: Where does enum validation live?

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic Literal types + DB CHECK constraints | Defense in depth. Same pattern as `rag_rerank_mode`. Catches at API edge AND DB layer. | ✓ |
| Pydantic only | Direct DB writes can insert garbage. | |
| DB CHECK only | Bad UX (500 errors instead of 422). | |

**User's choice:** Pydantic Literal types + DB CHECK constraints
**Notes:** Captured as D-60.

---

## Claude's Discretion

(Captured in CONTEXT.md "Claude's Discretion" section — file split between `llm_provider.py` / `egress_filter.py` / `provider_config.py`; UI layout of per-feature overrides; sync vs async local-endpoint probe; INFO-log gating; batched vs N-row registry insert; provisional-set parameter vs context-var; explicit pass-through for `none` mode.)

## Deferred Ideas

(Captured in CONTEXT.md `<deferred>` section.)
