# Phase 5: Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27
**Phase:** 05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co
**Areas discussed:** Redaction-enabled flag — source of truth, Buffering UX & SSE event shape, Tool-call symmetry — chokepoint placement, Sub-agent / auxiliary-LLM coverage scope

---

## Redaction-enabled flag — source of truth

### Q1 (D-83): Where does the redaction-enabled flag live for v1.0?

| Option | Description | Selected |
|--------|-------------|----------|
| Global only (current state) | Keep `settings.pii_redaction_enabled` (env var, default True). Drop per-thread TODOs. | ✓ (locked by Claude per "You decide") |
| Per-thread `threads.redaction_enabled` column (migration 032) | Add column, admin UI toggle, frontend changes. | |
| Hybrid: global env + system_settings.pii_redaction_enabled | Promote to system_settings 60s TTL cache. | |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 1 (Global only).
**Notes:** SC#5 names env var literal `PII_REDACTION_ENABLED=false`; per-thread granularity not on PROJECT.md v1.0 scope; per-thread flag deferred to v1.1 backlog.

### Q2 (D-84): When PII_REDACTION_ENABLED=false, what code path runs through chat.py?

| Option | Description | Selected |
|--------|-------------|----------|
| Identical to pre-milestone CHAT-06 — zero new code paths reached | Top-level branch only. | |
| Always run pipeline; pipeline becomes pass-through when off | Single code path; redaction_service early-return only. | |
| Hybrid: top-level branch + pipeline functions remain idempotent-on-off | Both — chat.py branch AND redaction_service early-return. | ✓ (locked by Claude per "You decide") |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 3 (Hybrid).
**Notes:** Honors Phase 1's TODO at redaction_service.py:388-393 ("the gate goes here, not in callers, so every downstream consumer benefits automatically") AND SC#5's behavioral contract. Two cheap bool checks; defense-in-depth against forgotten future call sites.

### Q3 (D-85): How should chat.py persist the user message and assistant response?

| Option | Description | Selected |
|--------|-------------|----------|
| Persist BOTH in REAL form (PRD §3.3 step 9) | `messages.content` real PII; re-anonymize history each turn. | ✓ (locked by Claude per "You decide") |
| Cache anonymized form in sibling column | Add `messages.anonymized_content`; migration 032. | |
| Persist user message in ANONYMIZED form | Surrogate-form storage; de-anon on every fetch. | |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 1 (real form).
**Notes:** PRD §3.3 step 9 is binding. Per-thread registry deterministic so re-runs correct. Phase 6 PERF-02 may revisit caching.

### Q4 (D-86): Where does the registry get loaded for a chat turn?

| Option | Description | Selected |
|--------|-------------|----------|
| Once at top of event_generator() — passed through | Phase 2 D-33 verbatim. | ✓ (locked by Claude per "You decide") |
| Per-redact-call — each site loads its own | N DB SELECTs per turn. | |
| Module-level cache keyed by thread_id | Phase 2 deferred to Phase 6. | |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 1 (once per turn, threaded).
**Notes:** Phase 2 D-33 is the binding decision. ToolService.execute_tool gains a `registry` parameter — unavoidable cost of TOOL-04.

---

## Buffering UX & SSE event shape

### Q1 (D-87): When redaction is ON, how should the de-anonymized response be delivered?

| Option | Description | Selected |
|--------|-------------|----------|
| Single-batch delta after de-anon completes | ONE delta event; matches FR-6.3 verbatim. | ✓ (locked by Claude per "You decide") |
| Fake-stream chunked delivery | Split buffer into ~50-char slices with sleep. | |
| Two-phase: stream raw surrogates first, replace later | Briefly leaks surrogates to user. | |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 1 (single-batch).
**Notes:** FR-6.1 + FR-6.3 both name "single batch on completion"; PRD §7.3 acknowledges latency tradeoff is acceptable with status events. Frontend useChatState.ts:138-183 renders identically.

### Q2 (D-88): Where do `redaction_status` events sit in the SSE timeline?

| Option | Description | Selected |
|--------|-------------|----------|
| Two events: `anonymizing` + `deanonymizing` bracket buffer window | FR-6.2 verbatim — singular phrasing implies one of each. | ✓ (locked by Claude per "You decide") |
| Per-stage events at every redact_text / de_anonymize_text site | Noisy; frontend dedup complexity. | |
| Single coarse `active`/`complete` events | Loses stage information. | |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 1 (two bracketing events).
**Notes:** Concretely: `anonymizing` after agent_start (covers history anon + tool-loop), `deanonymizing` after stream_response buffer completes before de_anonymize_text runs.

### Q3 (D-89): What happens to tool_start / tool_result / agent_start / thread_title events when redaction is ON?

| Option | Description | Selected |
|--------|-------------|----------|
| Suppress payloads; emit only `{type, tool}` skeleton | Preserves tool-name badge UX without leaking surrogates. | ✓ (locked by Claude per "You decide") |
| De-anonymize tool args/results before emitting | Doubles per-turn de-anon work for marginal UX value. | |
| Suppress entirely | Kills tool-activity transparency. | |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 1 (skeleton emit).
**Notes:** BUFFER-03's "sub-agent reasoning events" maps to tool-call payloads in this codebase. agent_start.display_name is static AgentDefinition field — PII-free. thread_title's underlying LLM call moved to PII-aware path (see D-96).

### Q4 (D-90): If de_anonymize_text raises mid-turn, what does the user see?

| Option | Description | Selected |
|--------|-------------|----------|
| Graceful degrade — fall back to Pass-1-only de-anon, log + emit partial | Same pattern as Phase 4 D-78 missed-scan soft-fail. | ✓ (locked by Claude per "You decide") |
| Emit raw surrogate-form buffer | UX-broken (Faker names visible). | |
| Hard-fail — emit error event, abort | Loses entire LLM response; contradicts NFR-3. | |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 1 (graceful degrade).
**Notes:** Pass-1-only is pure registry lookup (Phase 2 D-34 algorithm) — cannot raise. PRD NFR-3 forbids "crash" and "leak". Counter `pii_deanon_degraded_total{reason}`.

---

## Tool-call symmetry — chokepoint placement

### Q1 (D-91): Where does de-anon-input / re-anon-output logic live?

| Option | Description | Selected |
|--------|-------------|----------|
| Centralized shim in `_run_tool_loop` (tool-agnostic) | Recursive walker; UUID + len<3 skip rules. | ✓ (locked by Claude per "You decide") |
| Per-tool wrappers inside tool_service.execute_tool switch | 8 tools to wire today; easy to forget on a 9th. | |
| Hybrid: centralized shim + tool-specific allowlist | Schema drift cost. | |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 1 (centralized walker).
**Notes:** New module `backend/app/services/redaction/tool_redaction.py`. tool_service.py stays tool-agnostic. Phase 1 D-04 UUID filter is the defense-in-depth complement.

### Q2 (D-92): How is locking + perf handled for large tool-result anonymization?

| Option | Description | Selected |
|--------|-------------|----------|
| Sentinel-joined single redact_text on concatenated buffer | Sentinel collision risk. | |
| Per-string redact_text — N calls | N lock acquisitions; strictly worse. | |
| New `redact_text_batch` method on RedactionService | Single asyncio.Lock acquisition spans batch. | ✓ (locked by Claude per "You decide") |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 3 (batch method).
**Notes:** New public method `RedactionService.redact_text_batch(texts, registry)`. Phase 6 PERF-02 may add Presidio-level batching if profiling justifies.

### Q3 (D-93): When does history anonymization happen in chat.py?

| Option | Description | Selected |
|--------|-------------|----------|
| Single batched call BEFORE the tool loop | Uses D-92 batch primitive; one chokepoint. | ✓ (locked by Claude per "You decide") |
| Per-message redact_text in a loop | N lock acquisitions; strictly worse. | |
| Lazy redact at LLM-payload-build time | Scattered call sites — easy to forget. | |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 1 (single batched call).
**Notes:** ONE asyncio.Lock acquisition for entire history; ONE DB upsert batch.

### Q4 (D-94): How is defense-in-depth handled on the main chat path that bypasses LLMProviderClient?

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-flight egress check at the chat.py call site | OpenRouterService stays untouched. | ✓ (locked by Claude per "You decide") |
| Refactor OpenRouterService to delegate to LLMProviderClient | Large blast radius. | |
| Skip egress filter on main chat call | Violates NFR-2. | |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 1 (pre-flight at call site).
**Notes:** Three call sites (tool-loop's complete_with_tools, branch A stream_response, branch B stream_response). Reuses Phase 3 egress_filter helper unchanged. Trip = log per Phase 3 D-55 + emit error event + abort turn cleanly. No algorithmic fallback (chat LLM IS the answer step). OpenRouterService refactor deferred to Phase 6+.

---

## Sub-agent / auxiliary-LLM coverage scope

### Q1 (multiselect): Which auxiliary LLM call sites are in scope for Phase 5 PII-coverage?

| Option | Description | Selected |
|--------|-------------|----------|
| `agent_service.classify_intent` (intent classifier) | Sees raw body.message + history[-3:] today. | ✓ |
| `chat.py:269-283` thread-title generation | Sees raw body.message; PRD §3.6 explicit. | ✓ |
| 4 sub-agent paths (research / data_analyst / general / explorer) | Already covered automatically by D-86/D-91/D-93/D-94. | ✓ |
| `document_tool_service` create/compare/compliance/analyze | Separate router; not chat-loop. | ✓ (initially selected, then deselected in Q2) |

**User's choice:** All four initially. Document_tool_service was then explicitly deselected in Q2 follow-up.

### Q2 (D-95): Confirm document_tool_service expansion?

| Option | Description | Selected |
|--------|-------------|----------|
| YES — expand Phase 5 to cover it (4 LLM call sites added) | ~3-5 days additional work; new REQ-IDs needed. | |
| NO — keep Phase 5 chat-loop only; defer document_tool_service | Lock to 3 chat-loop items. | ✓ (user explicit selection) |
| DEFER — document the gap as a known v1.0 limitation | Pragmatic compromise. | |

**User's choice:** "NO — keep Phase 5 chat-loop only; defer document_tool_service to a future phase".
**Notes:** Phase 5 stays chat-loop only. document_tool_service + metadata_service deferred to v1.1 / future-phase backlog. Reasoning: ROADMAP boundary is "Chat-Loop Integration"; expanding requires milestone-scope amendment.

### Q3 (D-96): How are classify_intent + thread-title generation covered?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep both on OpenRouterService with anonymized inputs + pre-flight egress | Smaller change. | |
| Migrate both to LLMProviderClient with new feature enums | Adds migration + admin UI. | |
| Hybrid: classify_intent stays on OpenRouterService; title_gen migrates to LLMProviderClient | PRD §3.6 explicit on title_gen; column already shipped. | ✓ (locked by Claude per "You decide") |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 3 (hybrid).
**Notes:** title_gen migration is zero-new-migration (Phase 3 D-49 Literal already includes `title_gen`; D-57 already shipped `title_gen_llm_provider` column). LLM-emitted title de-anonymized via mode='none' before persistence + emit. classify_intent inputs anonymized via per-turn registry; pre-flight egress wrapper.

### Q4 (D-97): Phase 5 testing strategy?

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror Phase 4's test_phase4_integration.py pattern (~600 lines, 7 classes) | Consistent with Phase 1-4 patterns. | ✓ (locked by Claude per "You decide") |
| Split into per-SC files | Diverges from naming pattern; duplicates fixtures. | |
| Single end-to-end test with deep assertions | Hard to debug per-SC failure. | |
| You decide | User delegated decision. | (selected) |

**User's choice:** "You decide" — Claude locked Option 1 (mirror Phase 4 pattern).
**Notes:** test_phase5_integration.py with 7 test classes (TestSC1_PrivacyInvariant, TestSC2_BufferingAndStatus, TestSC3_SearchDocumentsTool, TestSC4_SqlGrepAndSubAgent, TestSC5_OffMode, TestB4_LogPrivacy, TestEgressTrip_ChatPath). Privacy-invariant assertion via mocked AsyncOpenAI capture + `entry.real_value not in payload` for every payload.

---

## Closure check

| Option | Description | Selected |
|--------|-------------|----------|
| I'm ready for context — write CONTEXT.md | Lock 15 decisions, write CONTEXT.md + DISCUSSION-LOG.md, commit. | ✓ |
| Explore more gray areas | Identify additional gray areas. | |

**User's choice:** "I'm ready for context — write CONTEXT.md".
**Notes:** Phase 5 ready for `/gsd-plan-phase 5`.

---

## Claude's Discretion

The user delegated EVERY question via "You decide" (4/4 in Areas 1-4 except the multiselect in Area 4 Q1 and the explicit document_tool_service confirmation in Q2). Claude locked decisions D-83 through D-97 (15 decisions) based on:

- **PRD verbatim wording** (FR-6.1/6.2/6.3, NFR-2, NFR-3, §3.3 step 9, §3.6, §7.3) where the PRD prescribes specific behavior
- **Phase 1-4 carry-forward semantics** (Phase 1 D-04/D-13/D-14/D-16/D-18, Phase 2 D-21/D-23/D-24/D-29-30/D-32-37, Phase 3 D-45/D-48/D-49/D-51-57, Phase 4 D-71/D-78-82) where prior phases already locked the load-bearing primitives
- **Smallest blast radius that satisfies the SC** when multiple defensible options exist (chose Option 1 / 3 over OpenRouterService refactors and milestone-scope expansions)
- **PRD §3.6 explicit naming** to break ties (title_gen migrates because PRD names it; classify_intent stays where it is because PRD doesn't)

In addition to the explicit "You decide" delegations, Claude has discretion on:
- Module split for the tool-redaction walker (single file vs split)
- `_run_tool_loop` lift to module-level helper (planner picks based on diff size)
- `tool_redaction.py` walker recursion depth limit (default 10 levels)
- Frontend SSEEvent type-union extension shape
- Spinner UI i18n strings
- Whether `redact_text_batch` releases the lock between strings (v1.0: no; Phase 6 PERF-02 may revisit)
- Egress trip emit shape (`{type: error}` vs `{type: redaction_status, stage: blocked}`)
- Title-gen de-anon mode (D-96 specifies `mode='none'`; if profiling shows fuzzy helps title quality, Phase 6 may revisit)

## Deferred Ideas

- **Per-thread `threads.redaction_enabled` column + admin UI toggle** — v1.1 / future-phase backlog
- **`messages.anonymized_content` sibling-column cache** — Phase 6 PERF-02 if profiling justifies
- **Module-level LRU cache of `ConversationRegistry` instances** — Phase 6 perf hardening
- **Fake-stream chunked delivery of buffered de-anon output** — Phase 6+ if user feedback warrants
- **`OpenRouterService` refactor to delegate through `LLMProviderClient`** — Phase 6+ unification
- **Presidio-level batch NER in `redact_text_batch`** — Phase 6 PERF-02 optimization
- **`document_tool_service` (create/compare/compliance/analyze) auxiliary LLM coverage** — v1.1 / future-phase backlog (per D-95)
- **`metadata_service` document-metadata extraction PII coverage** — v1.1 / future-phase backlog
- **Post-stream output-side filter on cloud LLM responses** — PRD does not require it
- **Frontend redesign of streaming UX for buffered mode** — minimum-viable spinner ships Phase 5; full polish later
- **Latency-budget regression test (anonymization < 500ms, full chat < 5s)** — Phase 6 PERF-02
- **Egress-trip alerting / rate limit / kill-switch** — Phase 6 hardening
- **`tool_calls` JSONB column anonymization for stored tool records** — D-85 stores in real form
- **Re-key the asyncio.Lock from `thread_id` to `(thread_id, user_id)`** — out of v1.0 scope
- **`redact_text_batch` lock-release-between-strings micro-optimization** — Phase 6 perf if measured contention warrants
