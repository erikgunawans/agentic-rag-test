# Phase 3: Entity Resolution & LLM Provider Configuration - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the three entity-resolution modes (`algorithmic` / `llm` / `none`) on top of a configurable LLM-provider abstraction, so PERSON-entity coreference (nicknames, partial names, title-stripped variants) collapses to one canonical surrogate per cluster within a thread, and any cloud auxiliary call is gated by a pre-flight egress filter.

In scope:
- New `LLMProviderClient` (`backend/app/services/llm_provider.py`) — single class, provider-aware, reuses the existing `AsyncOpenAI` dependency from `requirements.txt` against OpenAI-compatible endpoints (LM Studio / Ollama / OpenAI / Together.ai).
- Pre-flight egress filter — wraps every cloud call; scans payload against the persisted registry + the in-flight provisional surrogates from this turn; trips silently fall back to algorithmic clustering.
- Algorithmic resolution module (Union-Find clustering, Indonesian-aware nickname dictionary, sub-surrogate derivation) wired into Phase 1's `redact_text` pipeline **before** Faker generation runs.
- LLM-mode resolution call — local sees raw real names (no egress); cloud sees only provisional surrogates after pre-clustering.
- New env vars + new columns on `system_settings` (migration `030_pii_provider_settings.sql`) for global provider, mode, fallback toggle, and 5 per-feature overrides.
- Admin UI surface — new "PII Redaction & Provider" section on the existing `/admin/settings` page, surfacing the modes, provider, per-feature overrides, and a masked status badge for `CLOUD_LLM_API_KEY`.
- Pytest coverage for all 5 Phase 3 ROADMAP success criteria, including an egress-filter trip test and a provider-failure fallback test.

Explicitly NOT in scope (deferred to later phases):
- Fuzzy de-anonymization / 3-phase placeholder pipeline (Phase 4: DEANON-03..05).
- Optional secondary missed-PII LLM scan (Phase 4: SCAN-01..05) — but the new `LLMProviderClient` MUST be reusable by the Phase 4 SCAN feature without further refactor.
- System-prompt verbatim-formatting guidance (Phase 4: PROMPT-01).
- Chat-loop integration: SSE buffering, `redaction_status` events, tool/sub-agent symmetric coverage (Phase 5: BUFFER-01..03, TOOL-01..04).
- Embedding-provider switch (Phase 6: EMBED-01..02).
- Cross-provider failover (cloud↔local crossover with pre-anonymization on cloud-side fallback) (Phase 6 hardening: PERF-04 finalization).
- Title generation / metadata extraction retrofit onto the new provider client — pre-existing flows continue to use OpenRouter; Phase 4–6 picks up the migration.
- Output-side filter on cloud LLM responses (PRD does not require it; defer to FUTURE-WORK).
- Postgres advisory locks for cross-process safety (Phase 2 D-31 — Phase 6 hardening).

</domain>

<decisions>
## Implementation Decisions

### Algorithmic Resolution — Pipeline Placement & Mechanics

- **D-45 (RESOLVE-02):** **Pre-generation clustering.** Union-Find runs INSIDE `redact_text(text, registry)` BEFORE Faker generates surrogates. Each cluster gets exactly one canonical surrogate; sub-variants ("Pak Bambang", "Sutrisno", nickname) share it. Single registry write per cluster (plus per-variant rows per D-48). Cleanest fit for Phase 2's D-32 INSERT-ON-CONFLICT path; preserves D-37 cross-turn forbidden-tokens; matches PRD FR-4.2 sub-surrogate derivation directly. Rejected: post-pass merge (forces DELETE+INSERT, breaks Phase 2 D-32; complicates asyncio.Lock scope), hybrid cluster-only-new (creates inconsistency with already-registered entities).
- **D-46 (RESOLVE-02):** **Indonesian-aware nickname dictionary as embedded Python dict** at `backend/app/services/redaction/nicknames_id.py` — same pattern as Phase 1's `gender_id.py` already in the package. Frozen `dict[str, str]` mapping nickname → canonical (case-folded keys for O(1) lookup). Indonesian-first coverage (Bambang, Joko, Tini, Iwan, etc.); add a small English block ("Danny → Daniel", "Bob → Robert") for completeness. Loaded once at module import; zero runtime cost beyond the import. When a nickname has multiple canonicals (rare; e.g., "Iwan" → "Suherman" or "Setiawan"), pick the first match deterministically and log the ambiguity at DEBUG (OBS-02).
- **D-47 (RESOLVE-02):** **Strict PRD merge — refuse ambiguous solo merges.** When a solo first-name or solo last-name partial-matches more than one existing cluster, the solo mention becomes its own cluster (gets its own surrogate). Worst case: a duplicate surrogate, never a wrong merge. Logs the ambiguity at DEBUG with `cluster_count=N` (NEVER the value itself, per B4). Strict adherence to PRD FR-4.2 "merges if EXACTLY one cluster has that last name". Rejected: most-recent-mention-wins (positional heuristic causes subtly wrong merges in long threads), skip-as-`[PERSON]`-placeholder (breaks user-readable round-trip).
- **D-48 (RESOLVE-02, REG-04):** **Sub-surrogate derivation eagerly at registry-write.** When a cluster forms, write ALL variants as separate `entity_registry` rows pointing to surrogate components of the canonical surrogate:
  - `Daniel Walsh` → canonical surrogate `Marcus Smith`
  - `Walsh` → `Smith` (last-only row)
  - `Daniel` → `Marcus` (first-only row)
  - `Pak Walsh` → `Pak Smith` (honorific-prefixed row, only if honorific stripping was applied during detection per Phase 1's `honorifics.py`)
  - Nickname (e.g., `Danny`) → `Marcus` (nickname row)

  All rows share the same `thread_id`, satisfy `UNIQUE(thread_id, real_value_lower)` (Phase 2 D-23), and compose with Phase 2 D-37 forbidden-token expansion. Future thread mentions hit the registry directly (O(1) `casefold()` lookup) without re-running clustering. Each cluster's variant set is computed once via `nameparser` + the nickname dict; honorifics are sourced from Phase 1's `honorifics.py` constant set. Rejected: lazy decomposition on lookup (defeats Phase 2 D-27's O(1) hot path), eager-only-on-cross-mention (variable first-mention latency).

### LLM Provider Abstraction — Client Architecture

- **D-49 (PROVIDER-01..05, RESOLVE-03):** **Single `LLMProviderClient` with provider-aware branching** at `backend/app/services/llm_provider.py`. Public surface:
  - `async def call(self, feature: Literal["entity_resolution", "missed_scan", "fuzzy_deanon", "title_gen", "metadata"], messages: list[dict], registry: ConversationRegistry | None = None, provisional_surrogates: dict[str, str] | None = None) -> dict`
  - Resolves the effective provider per call (D-51).
  - For `provider == "cloud"`: wraps the call in the pre-flight egress filter (D-53..D-56) using `registry.entries()` ∪ `provisional_surrogates`.
  - For `provider == "local"`: bypasses the egress filter (no third-party egress) and operates on raw content per FR-9.2.
  - Logs the resolved provider per call (OBS-03).
  - Returns the parsed response dict (caller owns schema validation).
  - Methods are wrapped with `@traced(name="llm_provider.<feature>")` (Phase 1 D-16).
  - Test surface: one class to mock; one place where the egress invariant is enforced. Rejected: ABC + per-provider subclasses (doubles test matrix, easy-to-miss filter wiring), functional-module (spreads filter enforcement across 5 callsites — security regression vector).
- **D-50 (PROVIDER-05):** **Reuse the existing OpenAI Python SDK (`AsyncOpenAI`).** Already in `backend/requirements.txt` for embeddings; works against OpenAI / LM Studio / Ollama / Together.ai by swapping `base_url` + `api_key`. Async via `AsyncOpenAI`; battle-tested timeout/retry. Configuration:
  - Local: `AsyncOpenAI(base_url=settings.local_llm_base_url, api_key="not-needed")` (LM Studio/Ollama don't require keys)
  - Cloud: `AsyncOpenAI(base_url=settings.cloud_llm_base_url, api_key=settings.cloud_llm_api_key)`
  - Both clients lazily instantiated on first call; cached in module-level dict keyed by provider.
  - Default request timeout: 30s (configurable via `LLM_PROVIDER_TIMEOUT_SECONDS`, default 30).
  - Rejected: fresh httpx client (reinvents what OpenAI SDK already does correctly), dual transports (added complexity without clear benefit).

### LLM Provider Abstraction — Per-Feature Override Resolution

- **D-51 (PROVIDER-07, FR-9.6):** **Resolution order for the effective provider per call:**
  1. `<FEATURE>_LLM_PROVIDER` env var (e.g., `ENTITY_RESOLUTION_LLM_PROVIDER`) — wins.
  2. `system_settings.<feature>_llm_provider` column (e.g., `entity_resolution_llm_provider`) — DB-level override.
  3. `LLM_PROVIDER` global env var.
  4. `system_settings.llm_provider` global column.
  5. Default: `"local"` (PRD §6 default).

  Documented in code as a single `_resolve_provider(feature: str) -> Literal["local", "cloud"]` helper. Env wins so deployers can override quickly; DB is the admin-UI surface that satisfies SC#5. The resolved provider name + source (e.g., `feature_env`, `feature_db`, `global_env`, `global_db`, `default`) is logged on every call (OBS-03 / FR-4.3.3). Rejected: DB-first (inverts ops expectations, env-vars effectively useless once any DB row exists), env-only (defeats SC#5's 60s-cache requirement).

### LLM Provider Abstraction — Failure & Fallback

- **D-52 (PERF-04, FR-9.7):** **Ship `LLM_PROVIDER_FALLBACK_ENABLED` config knob now; default false; only algorithmic-fallback path active in Phase 3.**
  - New env var + new `system_settings.llm_provider_fallback_enabled bool default false` column.
  - In Phase 3, on cloud-LLM call failure (network / 5xx / invalid response / egress-filter trip): fall back to algorithmic-clustering result already computed as input. Logged as `provider_fallback=true`, `fallback_reason=<network|invalid_response|egress_blocked>`.
  - Cross-provider failover (cloud→local AND local→cloud crossover) is plumbed-but-disabled in Phase 3; the actual failover code paths ship in Phase 6 hardening when PERF-04 lands fully.
  - Keeps the env-var contract stable; no future-migration churn. Rejected: defer the knob to Phase 6 (forces a config rename and new column), ship full failover now (outside what Phase 3 SC#2 requires; bigger blast radius).

### Pre-Flight Egress Filter

- **D-53 (PROVIDER-04, FR-9.3, NFR-2):** **Casefold + word-boundary regex match.** For each candidate value `v` in the union of `registry.entries()` and the in-flight provisional set: build pattern `r'\b' + re.escape(v.casefold()) + r'\b'` and `re.search` against `payload.casefold()`. Catches `"JOHN DOE"`, `"john doe."`, `"Hi John Doe!"` while not false-tripping on substrings of unrelated tokens. Composes well with Phase 2 D-36's `casefold()` invariant. ~O(n×m) but n is small (one thread's registry); pre-compile patterns; bail-on-first-match. Rejected: substring (false-trips on common Indonesian first-names like "Mei" → "informasi"), strict-token-equality (misses multi-word real values), pluggable strategy (premature for v1.0; security control should not be optional).
- **D-54 (PROVIDER-04, NFR-3):** **On trip, abort the cloud call and fall back to algorithmic clustering.** Per PRD NFR-3 + FR-9.7. The trip is a **security-success**: the leak was prevented. Resolution proceeds with algorithmic-only output for this call; entity-resolution downstream consumers see a partial-but-correct result. User-facing behavior: chat continues normally. The trip is recorded:
  - Span attribute `egress.tripped=true`, `egress.match_count=N`, `egress.entity_types=[...]`, `egress.match_hashes=[sha256(value)[:8], ...]`
  - Log line at WARNING level with the same fields (NEVER raw values per B4)
  - The provider client raises a private `_EgressBlocked` exception internally; the surrounding fallback wrapper catches it and re-runs the call with the algorithmic result.
  - Rejected: raise to chat loop (conflicts with NFR-3 'never crash'), strip-and-proceed (hides upstream pre-anon bug; risky default).
- **D-55 (PROVIDER-04, OBS-02, B4):** **Trip log = counts + entity_types + 8-char SHA-256 hashes only.** Forensic-correlation-friendly without leaking PII into LangSmith / Langfuse / Railway logs. Format: `{"event":"egress_filter_blocked","match_count":2,"entity_types":["PERSON","EMAIL_ADDRESS"],"match_hashes":["3f8a2b1e","9c4d7f2a"]}`. The hashes let an operator confirm "this is the same leak as last hour" without ever exposing the values. NEVER first-N-chars of matched value, NEVER reverse-lookup tables. Reject any future suggestion to log values for "easier debugging" — that's a B4 violation (Phase 1 invariant).
- **D-56 (PROVIDER-04, FR-4.3.2):** **Filter scope = persisted registry + in-flight provisional surrogates.** Cloud-mode resolution sends provisional surrogates derived from algorithmic pre-clustering of THIS turn's new entities. Filter MUST scan against:
  - `registry.entries()` — all real values from prior turns of this thread.
  - The in-flight `dict[real_value, provisional_surrogate]` map being assembled for this call (i.e., new entities detected in this turn whose Faker surrogate is the "provisional" form).

  Otherwise a leak of a brand-new turn-1 entity slips through. Helper signature: `def egress_filter(payload: str, registry: ConversationRegistry, provisional: dict[str, str] | None) -> EgressResult`. `EgressResult.tripped: bool`, `match_count: int`, `entity_types: list[str]`, `match_hashes: list[str]`. Rejected: registry-only (misses first-turn entities), full-Presidio-rescan (doubles warm-path cost; PRD design is registry-based not NER-based for this filter).

### Settings Storage & Admin UI Surface

- **D-57 (PROVIDER-06, SET-01):** **Add columns to existing `system_settings` table via migration `030_pii_provider_settings.sql`.** New columns (all on the single `id=1` row):
  - `entity_resolution_mode text not null default 'algorithmic' check (entity_resolution_mode in ('algorithmic','llm','none'))`
  - `llm_provider text not null default 'local' check (llm_provider in ('local','cloud'))`
  - `llm_provider_fallback_enabled boolean not null default false`
  - `entity_resolution_llm_provider text null check (entity_resolution_llm_provider in ('local','cloud'))`
  - `missed_scan_llm_provider text null check (missed_scan_llm_provider in ('local','cloud'))`
  - `title_gen_llm_provider text null check (title_gen_llm_provider in ('local','cloud'))`
  - `metadata_llm_provider text null check (metadata_llm_provider in ('local','cloud'))`
  - `fuzzy_deanon_llm_provider text null check (fuzzy_deanon_llm_provider in ('local','cloud'))`
  - `pii_missed_scan_enabled boolean not null default true` (Phase 4 will consume; ship the column now to avoid migration churn)

  PATCH endpoint via existing `update_system_settings()`; reads via existing `get_system_settings()` with 60s TTL cache (Phase 2 D-21 / SET-01). Cache invalidation on write is already wired. Rejected: new dedicated `redaction_settings` table (splits cache, breaks the single-page admin model), JSONB blob (loses DB-level validation, diverges from existing column-typed pattern).
- **D-58 (PROVIDER-03, NFR-2):** **`CLOUD_LLM_API_KEY` env-var only; admin UI shows masked status badge.** The key lives in Railway environment (already the pattern for `OPENAI_API_KEY`, `COHERE_API_KEY`). Admin UI surfaces a read-only badge:
  - ✅ "cloud key configured" — `len(settings.cloud_llm_api_key) > 0`
  - ⚠️ "cloud key missing — cloud mode will fail" — empty
  - The badge value comes from a new `GET /admin/settings/llm-provider-status` endpoint that returns `{cloud_key_configured: bool, local_endpoint_reachable: bool}`; never the raw key.
  - Key rotation is a Railway-dashboard / `railway variables set` operation (existing ops pattern).
  - Matches secret-manager hygiene; no DB-write surface for the key.
  - Rejected: admin-UI-write-through-to-Railway (adds Railway-API dep, surfaces cred mgmt to app), encrypted DB column (key-mgmt-for-the-encryption-key, larger blast radius on DB compromise).
- **D-59 (PROVIDER-06):** **Extend the existing `/admin/settings` page with a new "PII Redaction & Provider" section.** No new admin route, no new IconRail entry. Modify `frontend/src/pages/AdminSettingsPage.tsx` to add a section/accordion with:
  - **Mode** — `entity_resolution_mode` radio (`algorithmic` / `llm` / `none`)
  - **Global provider** — `llm_provider` radio (`local` / `cloud`)
  - **Per-feature overrides** — 5 select dropdowns (Inherit / local / cloud)
  - **Fallback** — `llm_provider_fallback_enabled` toggle
  - **Cloud key status** — read-only badge from D-58
  - **Local endpoint status** — read-only badge (probe `LOCAL_LLM_BASE_URL/v1/models` on page load)
  - **Missed-PII secondary scan** — toggle (Phase 4 consumes; surface now to avoid UI churn)

  Save button → existing PATCH endpoint (extended `SystemSettingsUpdate` Pydantic model). i18n strings (Indonesian default + English) follow existing `I18nProvider` pattern. Audit logged via `log_action(action="update", resource_type="system_settings", details={"changed_fields": [...]})`. Rejected: dedicated `/admin/pii-redaction` page (premature split for ~9 fields), two-page split for keys-vs-modes (UX hazard).
- **D-60 (PROVIDER-06):** **Pydantic `Literal` types on API + DB CHECK constraints.** Defense in depth — same pattern as existing `rag_rerank_mode: Literal['none','llm','cohere']` in `admin_settings.py`. New fields on `SystemSettingsUpdate`:
  - `entity_resolution_mode: Literal['algorithmic', 'llm', 'none'] | None = None`
  - `llm_provider: Literal['local', 'cloud'] | None = None`
  - `llm_provider_fallback_enabled: bool | None = None`
  - `entity_resolution_llm_provider: Literal['local', 'cloud'] | None = None`
  - … (4 more per-feature override fields)
  - `pii_missed_scan_enabled: bool | None = None`

  DB CHECK constraints in migration `030_*.sql` mirror the Literal sets exactly. Bugs caught at API edge (422) AND DB layer (23514). Test coverage: API rejects bad enum (422 assert), DB rejects direct SQL with bad enum (23514 assert). Rejected: Pydantic-only (looser; ops scripts can insert garbage), DB-CHECK-only (bad UX — 500 errors instead of 422 validation errors).

### Resolution Pipeline Wiring (composes Phase 1 + Phase 2 + Phase 3)

- **D-61:** **Resolution runs INSIDE the asyncio.Lock critical section** established by Phase 2 D-30. The full flow inside `redact_text(text, registry)` is:
  1. Acquire per-thread asyncio.Lock (Phase 2 D-29/D-30).
  2. Detect entities via Presidio two-pass (Phase 1 D-03/D-04).
  3. **NEW (Phase 3):** Cluster PERSON entities via Union-Find (mode = `algorithmic`) OR via the cluster-then-LLM-refine path (mode = `llm`, calls `LLMProviderClient.call("entity_resolution", ...)`) OR skip clustering (mode = `none`).
  4. Generate Faker surrogates per cluster (Phase 1 D-05/D-06/D-07/D-08), expanded with Phase 2 D-37 thread-wide forbidden tokens.
  5. **NEW (Phase 3):** Compose the variant set per cluster (D-48) — canonical, first-only, last-only, honorific-prefixed, nickname.
  6. Compute deltas vs the loaded registry; `await registry.upsert_delta(deltas)` (Phase 2 D-32).
  7. Build the `entity_map` for this call's text rewrite using ALL variant rows.
  8. Release the lock; return `RedactionResult`.

  Span attributes for `redaction.redact_text` extended (Phase 2 D-41 + Phase 3): `resolution_mode`, `clusters_formed`, `cluster_size_max`, `provider_resolved` (when mode=llm), `provider_fallback` (true if cloud failed), `egress_tripped` (when applicable). NEVER real values.
- **D-62 (RESOLVE-04, FR-4.4):** **Non-PERSON entities use exact-match normalization, never reach the resolution LLM.** Normalization happens at registry-write (Phase 2 D-36 already case-folds via `str.casefold()`); Phase 3 adds:
  - Email: lowercase + strip whitespace.
  - Phone: strip non-digit chars, normalize country prefix where Phase 1 already detected it.
  - URL: lowercase + strip trailing slash + strip leading `www.`.
  - IBAN (hard-redacted in Phase 1, but normalization defined here for consistency): not applicable — never registered.
  - Other: lowercase + strip whitespace.

  The `LLMProviderClient.call("entity_resolution", ...)` payload is constructed from PERSON entities only. Validation: a unit test asserts that the payload assembled for resolution contains only PERSON-type strings. Rejected: send-everything-to-LLM (defeats FR-4.4; surfaces emails/phones to cloud unnecessarily).

### Tracing & Observability

- **D-63 (OBS-02, OBS-03):** **Tracing span attributes for the new layers** (Phase 1 D-18 / Phase 2 D-41 invariants apply: counts and timings only, NEVER real values):
  - `llm_provider.<feature>`: `provider_resolved` (`local` | `cloud`), `provider_source` (`feature_env` | `feature_db` | `global_env` | `global_db` | `default`), `latency_ms`, `success`, `egress_tripped` (bool, only on cloud).
  - `redaction.redact_text` (extended): `resolution_mode`, `clusters_formed`, `clusters_merged_via` (`algorithmic` | `llm` | `none`), `cluster_size_max`, `provider_resolved` (when mode=llm), `provider_fallback` (bool), `egress_tripped` (bool, when mode=llm + cloud).
  - Egress filter trip: WARNING-level structured log line (D-55 format).
  - **Resolved provider per call logged at INFO level** for OBS-03 audit: `{"event":"llm_provider_call","feature":"entity_resolution","provider":"cloud","source":"global_env","success":true,"latency_ms":120}`.

### Testing

- **D-64:** **Pytest coverage for all 5 Phase 3 ROADMAP success criteria** at `backend/tests/api/test_resolution_and_provider.py` + `backend/tests/unit/test_llm_provider_client.py` + `backend/tests/unit/test_egress_filter.py`. Each SC gets at least one test:
  - SC#1 (algorithmic clustering of "Bambang Sutrisno" / "Pak Bambang" / "Sutrisno" / "Bambang") — assert single canonical surrogate; assert all 4 variant rows present in `entity_registry`.
  - SC#2 (cloud LLM call with provisional surrogates + egress-filter trip + algorithmic fallback) — mock `AsyncOpenAI`; inject a payload that contains a registered real value; assert `EgressBlocked` triggered fallback; assert algorithmic result returned; assert no real value in mock-recorded request.
  - SC#3 (local LLM mode) — `LLM_PROVIDER=local`, `ENTITY_RESOLUTION_MODE=llm`; inject a local-LLM-mock that receives raw real names; assert no egress-filter wrapper invoked.
  - SC#4 (non-PERSON normalization) — assert resolution payload contains only PERSON-type strings; emails/phones/URLs go through exact-match normalization without LLM contact.
  - SC#5 (admin UI provider switch propagates within 60s) — PATCH `/admin/settings` with `llm_provider=cloud`; wait for cache TTL; assert next `_resolve_provider("entity_resolution")` returns `cloud` without redeploy.
- **D-65:** **Local LLM mock for CI.** A pytest fixture spins up a tiny FastAPI test app at `pytest-fixture localhost:9999/v1/chat/completions` that returns canned `chat.completions` responses. CI never hits a real Ollama / LM Studio. Cloud calls are mocked at the `AsyncOpenAI` client level (no actual httpx traffic). The egress-filter test exercises the real filter logic against a real (in-memory) registry, but the LLM call is mocked — the assertion is "request was not sent" (i.e., the mock recorded zero invocations after the trip).
- **D-66:** **Egress-filter unit test matrix** — exhaustive coverage of:
  - exact-match casefold trip (`"John Doe"` in payload, `"JOHN DOE"` in registry)
  - word-boundary preservation (`"Johnson"` in payload, `"John"` in registry → MUST NOT trip)
  - multi-word real values (`"Bambang Sutrisno"` in payload as substring → MUST trip)
  - registry-only path (no provisional set)
  - provisional-only path (no persisted registry rows)
  - empty registry + empty provisional (no trip; allow-pass)
  - log-content invariant: parse the captured log line; assert no raw values appear (B4 / D-55).

### Claude's Discretion

- Exact module split — whether `LLMProviderClient`, `_EgressBlocked`, `egress_filter()`, and per-feature override resolver live in one file or split (`llm_provider.py`, `egress_filter.py`, `provider_config.py`). Planner picks based on line-count.
- Whether per-feature overrides are exposed as 5 separate UI dropdowns (D-59) or as an "advanced settings" expander. UI-friendliness call.
- Whether the local-endpoint-reachable badge probes `/v1/models` synchronously on page load, or async after page render. Both are acceptable; async is friendlier.
- Whether the resolved-provider INFO-level log line (D-63) is gated by a `LOG_PROVIDER_RESOLUTION=true` env var (default true) for production-noise control. Recommend keeping it on for OBS-03 audit.
- Whether the variant-row write (D-48) batches into a single `INSERT ... ON CONFLICT DO NOTHING` with multiple value rows or N separate inserts. Single batched insert is faster; planner picks the supabase-py call shape.
- Whether the in-flight provisional set (D-56) is a `dict[str, str]` passed as a parameter or a context-var. Parameter is more explicit and unit-testable.
- Whether the algorithmic `none` mode is a no-op (each unique string gets its own surrogate, current Phase 1-2 behavior) or an explicit pass-through with a span tag for OBS clarity. Recommend explicit pass-through.

### Folded Todos

(None — `gsd-sdk query todo.match-phase 3` returned 0 matches.)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source PRD (authoritative for v1.0 milestone)
- `docs/PRD-PII-Redaction-System-v1.1.md` §3.1 (Core Principle), §3.4 (Auxiliary LLM Calls — provider invariant), §3.6 (Auxiliary LLM Calls — pre-flight egress invariant), §4.FR-4 (Entity Resolution — modes, Union-Find, sub-surrogates), §4.FR-4.3.1 (local provider), §4.FR-4.3.2 (cloud provider — provisional surrogates + egress filter), §4.FR-4.3.3 (provider-agnostic — never invent surrogates, log provider per call), §4.FR-4.4 (non-PERSON normalization), §4.FR-9 (LLM Configuration — global + per-feature overrides), §5.NFR-2 (Security — egress filter required defense-in-depth), §5.NFR-3 (Reliability — graceful degradation), §5.NFR-4 (Observability — log provider per call + egress results), §6 (Configuration Reference — env-var defaults), §7.6 / §11 (Threat model — egress filter as primary control)

### Project + Milestone Plan
- `.planning/PROJECT.md` "Current Milestone" + "Key Decisions" — v1.0 scope
- `.planning/REQUIREMENTS.md` "v1 Requirements" — RESOLVE-01..04, PROVIDER-01..07 are Phase 3's REQ-IDs
- `.planning/ROADMAP.md` "Phase 3: Entity Resolution & LLM Provider Configuration" — goal, dependencies, 5 success criteria

### Phase 1–2 CONTEXT (locked decisions Phase 3 builds on)
- `.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md` — D-03/D-04 (two-pass thresholds), D-05/D-06 (Faker surrogate generation + 10-retry budget), D-07/D-08 (per-call surname/first-name forbidden tokens; hard-redact exclusion from registry), D-13/D-14 (`redact_text(text, registry=None)` signature), D-16 (`@traced` decorator), D-18 (B4 invariant — never log real PII), D-20 (Faker `seed_instance` for tests), `honorifics.py` (Pak/Bu/Bapak/Ibu strip set)
- `.planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md` — D-21/D-22/D-23 (entity_registry table + UNIQUE constraint), D-24 (hard-redacts never in registry), D-25 (service-role-only), D-27/D-28 (ConversationRegistry + EntityMapping), D-29/D-30 (per-thread asyncio.Lock + critical-section scope), D-31 (advisory-lock FUTURE-WORK for Phase 6), D-32 (eager INSERT-ON-CONFLICT-DO-NOTHING), D-33 (per-turn lazy load), D-34/D-35/D-36 (placeholder-tokenized de-anon + case handling), D-37/D-38 (cross-turn forbidden tokens, PERSON-only), D-39/D-40/D-41 (service composition + tracing span attributes)

### Codebase Map (existing patterns to follow / reuse)
- `.planning/codebase/CONVENTIONS.md` — service-module shape, traceable decorator, Pydantic models, audit conventions
- `.planning/codebase/STRUCTURE.md` "Where to Add New Code" → "New backend service" — directory and file conventions
- `.planning/codebase/STACK.md` — confirms `openai` SDK already in `requirements.txt` for embeddings
- `.planning/codebase/INTEGRATIONS.md` — Supabase + Railway env-var patterns

### Concrete code to read before editing (Phase 3 will modify or wrap these)
- `backend/app/config.py` — Phase 1 added `pii_redaction_enabled`, `pii_surrogate_*`, `pii_redact_*`, `tracing_provider` to the `Settings(BaseSettings)` class. Phase 3 adds `entity_resolution_mode`, `llm_provider`, `llm_provider_fallback_enabled`, 5 per-feature overrides, `local_llm_base_url`, `local_llm_model`, `cloud_llm_base_url`, `cloud_llm_model`, `cloud_llm_api_key`, `pii_missed_scan_enabled` (Phase 4 also reads), `llm_provider_timeout_seconds` (default 30).
- `backend/app/services/redaction_service.py` — Phase 2 widened `redact_text(text, registry=None)` (commit `9cc1f42`). Phase 3 inserts the clustering step between detection (Phase 1) and Faker generation (Phase 1) per D-45 / D-61. The asyncio.Lock scope from D-30 is preserved; clustering runs INSIDE it.
- `backend/app/services/redaction/anonymization.py` — Phase 1 surrogate generator + Phase 2 D-37 cross-turn forbidden tokens. Phase 3 expands the input to clustering: instead of receiving a flat list of detected spans, receives a list of clusters (each with a canonical real name + variant set).
- `backend/app/services/redaction/registry.py` — Phase 2 `ConversationRegistry`. Phase 3 adds NO new schema-level methods to the class itself; it just writes more rows per call (sub-surrogate variant rows per D-48).
- `backend/app/services/redaction/__init__.py` — Phase 2 re-exports `ConversationRegistry` + `EntityMapping`. Phase 3 adds re-exports for `LLMProviderClient`, `egress_filter`, `EgressResult` if the module structure pulls them into `app.services.redaction.*`. (Or place provider client at `app.services.llm_provider` and skip the redaction-package re-export — Claude's Discretion.)
- `backend/app/services/redaction/honorifics.py` — Phase 1 honorific strip set. Phase 3 D-48's honorific-prefixed variant row uses this same set.
- `backend/app/services/redaction/gender_id.py` — Phase 1 Indonesian first-name → gender lookup. Phase 3's `nicknames_id.py` follows the same module pattern.
- `backend/app/services/redaction/name_extraction.py` — Phase 1 nameparser wrapper. Phase 3's clustering uses the same wrapper to decompose names into first/middle/last components for variant-row generation.
- `backend/app/services/system_settings_service.py` — `get_system_settings()` (60s TTL cache) + `update_system_settings()` (cache invalidation). Phase 3 reads new columns through this service; Phase 3 does NOT touch the cache implementation.
- `backend/app/routers/admin_settings.py` — `SystemSettingsUpdate` Pydantic model + `PATCH /admin/settings` + `log_action()` audit. Phase 3 extends `SystemSettingsUpdate` with new Literal-typed fields per D-60.
- `backend/app/database.py` — `get_supabase_client()` (service-role) for system-table writes. Phase 3 uses for the registry variant-row writes (Phase 2 D-25 invariant).
- `backend/app/services/embedding_service.py` (or wherever `AsyncOpenAI` is currently imported for embeddings) — Phase 3 reuses the same SDK; new client instances live in `app/services/llm_provider.py`.
- `frontend/src/pages/AdminSettingsPage.tsx` — Phase 3 adds a new section to this page per D-59. i18n strings via `I18nProvider`.
- `supabase/migrations/029_pii_entity_registry.sql` — Phase 2's last applied migration. Phase 3 ships `030_pii_provider_settings.sql`. CLAUDE.md gotcha: never edit applied migrations; use `/create-migration` skill.
- `supabase/migrations/003_user_settings.sql` (NB: misleading filename — this also defines `system_settings` style additions in later migrations) + every subsequent migration that ALTER TABLE'd `system_settings` — Phase 3's planner must verify the current `system_settings` column shape before writing migration 030.

### External docs (planner will fetch via context7 / web)
- OpenAI Python SDK `AsyncOpenAI` — base_url override, timeout/retry config, async streaming (Phase 5 will need streaming; Phase 3 uses non-streaming responses for resolution).
- LM Studio + Ollama OpenAI-compatible endpoint specs — confirm `/v1/chat/completions` shape and any quirks (e.g., Ollama returns slightly different `usage` fields).
- Postgres `CHECK (col IN (...))` semantics under `INSERT ... ON CONFLICT DO UPDATE` — confirm constraint check timing.
- `nameparser.HumanName` for Indonesian names — Phase 1 already verified mononym → `.first` (memory: 2669); Phase 3's variant-row generator must not regress on this.
- Python `re.search` with pre-compiled patterns — confirm performance characteristics for the egress filter at registry sizes of 50–500 entries.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`AsyncOpenAI` client (already imported for embeddings in `backend/app/services/embedding_service.py` or similar)**: Phase 3 reuses for the provider client per D-50. Zero new dependency.
- **`get_system_settings()` / `update_system_settings()` (`system_settings_service.py`)**: 60s TTL cache + cache invalidation. Phase 3 reads through it; the existing PATCH endpoint extends to handle new fields.
- **`SystemSettingsUpdate` Pydantic model (`admin_settings.py` L14)**: Existing `Literal` type pattern for `rag_rerank_mode`. Phase 3 extends with new Literal-typed fields per D-60.
- **`require_admin` dependency (`backend/app/dependencies.py`)**: Phase 3 reuses for the new `GET /admin/settings/llm-provider-status` endpoint per D-58.
- **`log_action()` (`audit_service.py`)**: Phase 3 reuses for admin-UI mutations of provider settings.
- **`@traced` decorator (`tracing_service.py`)**: Phase 1 D-16. Phase 3's new `LLMProviderClient.call()` and `egress_filter()` wrap with this.
- **`ConversationRegistry.entries()` (Phase 2 D-27)**: Phase 3's egress filter consumes this for the persisted-registry portion of D-56 scope.
- **`backend/app/services/redaction/honorifics.py`**: Phase 1 honorific strip set. Phase 3 D-48 reuses for the honorific-prefixed variant row.
- **`backend/app/services/redaction/name_extraction.py`**: Phase 1 nameparser wrapper. Phase 3 clustering uses to decompose names into first/middle/last for variant-row generation.
- **Phase 2 D-32 INSERT-ON-CONFLICT-DO-NOTHING upsert path**: Phase 3 D-48 batches the variant-row writes through the same call (single multi-row insert).
- **Phase 1 `gender_id.py` module pattern**: Frozen Python dict at module level, loaded once at import. Phase 3's `nicknames_id.py` follows the same shape.
- **`@traced` span-attribute conventions (Phase 1 D-18 / Phase 2 D-41)**: Counts and timings only, NEVER real values. Phase 3 D-55 / D-63 inherit.

### Established Patterns
- **Service-module layout**: `backend/app/services/<name>/...` for sub-packaged services, `backend/app/services/<single>.py` for top-level. Phase 3 places `LLMProviderClient` at top-level (`llm_provider.py`) and adds `nicknames_id.py` + clustering helpers inside `redaction/`.
- **Migration numbering**: Sequential, never edit applied (`/create-migration` enforces). Phase 3 → `030_pii_provider_settings.sql`.
- **Pydantic Literal-type validation in admin endpoints**: `rag_rerank_mode: Literal['none','llm','cohere']` → Phase 3 mirrors for mode + provider fields.
- **DB CHECK constraints for enum-like columns**: Existing pattern in `001_initial_schema.sql` for various status fields. Phase 3 D-60 follows.
- **System-table service-role-only RLS**: `system_settings` and `entity_registry` (Phase 2 D-25) both use this pattern. Phase 3's migration 030 doesn't add new tables — it ALTER TABLEs `system_settings`, which already has the correct RLS.
- **Lazy module-level singletons**: Phase 1 Presidio + Faker + nicknames + gender. Phase 3 `LLMProviderClient` instances cached in module-level dict keyed by provider; lazy on first call.
- **i18n on admin pages**: `I18nProvider` (Indonesian default + English). New strings for the PII Redaction section follow the same pattern.

### Integration Points
- **`backend/app/services/redaction_service.py`**: Insert clustering step inside `redact_text(text, registry)` between detection (Phase 1) and Faker generation (Phase 1). Phase 2 D-30 asyncio.Lock scope wraps the new step too. No public-API signature change.
- **`backend/app/services/redaction/anonymization.py`**: Input shape changes from `list[Span]` to `list[Cluster]` (each cluster contains canonical + variant set + Faker-generated surrogate). Phase 2 D-37 forbidden-token expansion still applies.
- **`backend/app/services/redaction/registry.py`**: No new methods. Phase 3 writes more rows per call (variant rows per D-48) through the existing `upsert_delta()`.
- **NEW `backend/app/services/llm_provider.py`**: `LLMProviderClient` + `_resolve_provider` + `_EgressBlocked` + `egress_filter` + `EgressResult` (or split into `egress_filter.py` per Claude's Discretion).
- **NEW `backend/app/services/redaction/nicknames_id.py`**: Frozen Indonesian-aware nickname dict (matches `gender_id.py` pattern).
- **NEW `backend/app/services/redaction/clustering.py`** (or inline in `anonymization.py`): Union-Find clustering, sub-surrogate variant-set generator. Claude's Discretion on file split.
- **NEW `supabase/migrations/030_pii_provider_settings.sql`**: ALTER TABLE `system_settings` ADD COLUMN × 9 (per D-57) with CHECK constraints.
- **`backend/app/config.py`**: ADD ~12 new env-var-backed Settings fields per D-50 / D-51 / D-57.
- **`backend/app/routers/admin_settings.py`**: EXTEND `SystemSettingsUpdate` with the new Literal-typed fields per D-60. Add new `GET /admin/settings/llm-provider-status` endpoint per D-58.
- **`frontend/src/pages/AdminSettingsPage.tsx`**: ADD "PII Redaction & Provider" section per D-59. New i18n strings.
- **NEW `backend/tests/api/test_resolution_and_provider.py`** + **`backend/tests/unit/test_llm_provider_client.py`** + **`backend/tests/unit/test_egress_filter.py`**: Per-SC + per-component test coverage per D-64 / D-65 / D-66.
- **NOT modified in Phase 3**: `backend/app/routers/chat.py` (Phase 5), `backend/app/main.py` lifespan (no new warm-up — provider client lazy-loaded on first call).

</code_context>

<specifics>
## Specific Ideas

- **The egress filter is the security primitive of this milestone.** Once `LLM_PROVIDER=cloud` ships, this filter is what stands between a Railway-hosted backend and an OpenAI invoice that contains "Bambang Sutrisno". Treat it as a hard control: no logging shortcuts, no opt-out env var, defense-in-depth even when upstream pre-anonymization is believed correct.
- **OpenAI SDK reuse is the right answer for v1.0.** LM Studio, Ollama, OpenAI direct, Together.ai all advertise OpenAI-compatibility. The SDK's `AsyncOpenAI(base_url=…)` already supports the swap. Don't roll a new httpx layer to "have more control" — that's the wrong tradeoff for this surface area at v1.0 scale.
- **Variant-row eagerness (D-48) is the central performance design.** Once the registry has rows for every variant of every cluster, future thread mentions hit the registry directly via Phase 2 D-27's O(1) `casefold()` lookup — clustering only runs ONCE per cluster per thread. This trades disk for hot-path latency, which is the right call given Phase 1 PERF-01 (Phase 3 must not regress sub-500ms).
- **Pre-generation clustering (D-45) preserves Phase 2's INSERT-ON-CONFLICT-DO-NOTHING (D-32).** A post-pass approach would force DELETE+INSERT, which complicates the asyncio.Lock semantics, audit log shape, and forbidden-token recomputation. The decision is load-bearing — don't reopen without explicit cause.
- **Strict PRD merge (D-47) on ambiguous solos is conservative-by-design.** A duplicate surrogate is a UX blemish; a wrong merge corrupts the round-trip. Phase 3 picks blemish over corruption every time.
- **`CLOUD_LLM_API_KEY` lives in env-only (D-58).** Railway already does secret management. Adding a DB column to "make it editable from the admin UI" enlarges the blast radius for zero gain. The masked status badge is the right UX compromise.
- **Phase 4 forward-compat is implicit in the provider-client surface (D-49).** The same `LLMProviderClient.call()` is used by Phase 4 missed-PII scan and fuzzy de-anon. Designing for 5 features now (even though Phase 3 ships only entity resolution) avoids a churn-y refactor in Phase 4.
- **Resolution pipeline order (D-61) is non-negotiable.** Cluster → generate → write variants → de-anon. Any deviation breaks Phase 2 D-37 cross-turn forbidden-token correctness.

</specifics>

<deferred>
## Deferred Ideas

- **Cross-provider failover (cloud↔local crossover)** — knob shipped (D-52), behavior deferred to Phase 6 hardening when PERF-04 lands fully.
- **Output-side filter on cloud LLM responses** — PRD does not require it; defer to FUTURE-WORK.
- **Title generation / metadata extraction retrofit onto the new provider client** — pre-existing flows continue to use OpenRouter; Phase 4–6 picks up the migration.
- **Admin-UI write-through for `CLOUD_LLM_API_KEY`** via Railway API — not in v1.0 scope; rotation stays a Railway-dashboard operation.
- **Encrypted DB column for the cloud key** — bigger blast radius than env-only; reject permanently.
- **Pluggable egress-filter strategy** — premature; security control should not be optional. If a future need surfaces (e.g., locale-specific normalization), revisit.
- **Per-feature timeout overrides** (separate timeout for entity resolution vs missed-PII scan) — single global `LLM_PROVIDER_TIMEOUT_SECONDS` is sufficient at v1.0; revisit if profiling shows divergent latency budgets.
- **Streaming responses from the auxiliary LLM** — entity resolution is non-streaming by nature (single clustering decision); streaming is a Phase 5 concern for the main agent.
- **Postgres advisory locks for cross-process safety** — Phase 2 D-31; Phase 6 hardening.
- **Audit table for provider switches** beyond `log_action` audit_trail row — current `log_action` payload is sufficient; revisit if compliance asks for an immutable provider-history view.
- **`none` mode UX badge** in the admin UI signaling "resolution disabled — duplicate surrogates likely" — nice-to-have; defer.
- **Local-endpoint health check on lifespan startup** rather than per-request — premature; per-page-load probe is sufficient for the admin UI.

### Reviewed Todos (not folded)

(None — `gsd-sdk query todo.match-phase 3` returned 0 matches.)

</deferred>

---

*Phase: 03-entity-resolution-llm-provider-configuration*
*Context gathered: 2026-04-26*
