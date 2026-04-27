# Phase 5: Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage) - Context

**Gathered:** 2026-04-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship the end-to-end chat-loop wiring so a real chat round-trip preserves the privacy invariant — full LLM-response buffering when redaction is active, `redaction_status` SSE events for UX, and symmetric anonymize-input / de-anonymize-output coverage across every tool, every sub-agent path, and every auxiliary LLM call inside the chat loop. This phase composes Phases 1–4's primitives into the user-visible product surface; no new redaction algorithms ship here.

In scope:
- **Top-level redaction gate** — `event_generator()` branches on `settings.pii_redaction_enabled`. When OFF, run the existing CHAT-06 path verbatim (no registry load, no SSE `redaction_status` events, no buffering). When ON, run the full pipeline. Defense-in-depth secondary gate inside `RedactionService.redact_text` (the existing TODO at `redaction_service.py:388-393`).
- **Per-turn registry threading** — `ConversationRegistry.load(thread_id)` called once at the top of `event_generator()`; the instance is passed as a parameter through `_run_tool_loop`, `ToolService.execute_tool`, and the auxiliary LLM call sites (title-gen, classify_intent).
- **Anonymize-history-then-LLM** — single `RedactionService.redact_text_batch(history_strings + [user_message], registry)` call before the tool loop. New batch primitive on RedactionService: one asyncio.Lock acquisition, per-string Presidio NER, batched upsert.
- **Buffered final response** — when redaction is ON, `OpenRouterService.stream_response(...)` chunks are accumulated locally instead of emitted progressively. After completion, run `RedactionService.de_anonymize_text(buffer, registry, mode=settings.fuzzy_deanon_mode)` once, emit a single `delta: {delta: <full_text>, done: false}` followed by `delta: {done: true}`.
- **`redaction_status` SSE events** — two events per turn when redaction is ON: `{type: redaction_status, stage: anonymizing}` after `agent_start` (covers history anon + tool-loop iterations), `{type: redaction_status, stage: deanonymizing}` after the buffer completes and before `de_anonymize_text` runs.
- **Tool I/O symmetry** — new helper module `backend/app/services/redaction/tool_redaction.py` exposes `deanonymize_tool_args(args, registry)` and `anonymize_tool_output(output, registry, redaction_service)`. Both are recursive walkers over arbitrary JSON-shaped structures; skip rules: UUID regex match (`^[0-9a-f-]{36}$`) and `len < 3`. Invoked in `_run_tool_loop` around `tool_service.execute_tool(...)`. `tool_service.py` itself stays tool-agnostic.
- **Skeleton SSE for tool events** — when redaction is ON, `tool_start` and `tool_result` events emit only `{type, tool}` (no `input` / `output` payloads). Frontend's existing tool-name badge UX preserved without leaking surrogate-form text.
- **Sub-agent coverage** — the 4 chat-loop agents (research / data_analyst / general / explorer) are covered automatically by D-86 + D-91 + D-93 + D-94 because they run inside `_run_tool_loop` against the same `OpenRouterService` calls. PRD §3.5's "share parent's redaction-service instance" is automatic via the `get_redaction_service()` `@lru_cache` singleton.
- **Auxiliary LLM coverage** — `agent_service.classify_intent` stays on `OpenRouterService` but inputs are anonymized via the per-turn registry before the call AND a pre-flight egress filter wraps the call. `chat.py:269-283` thread-title generation migrates to `LLMProviderClient.call(feature='title_gen', messages=anonymized_messages, registry=registry)` (Phase 3 D-49 already lists `title_gen` in the `feature` Literal; Phase 3 D-57 already shipped the `title_gen_llm_provider` column — zero new migration). LLM-emitted title is run through `de_anonymize_text` before persistence and emit.
- **Pre-flight egress on the main chat path** — Phase 3's `egress_filter(payload, registry, provisional=None)` wraps every `OpenRouterService.complete_with_tools` and `stream_response` call when redaction is ON (three call sites in chat.py). Trip = log per Phase 3 D-55, emit a single error event, abort the turn cleanly. No algorithmic fallback (chat LLM is the answer-generation step).
- **Graceful degrade on de-anon failure** — if the 3-phase `de_anonymize_text` pipeline raises mid-turn (provider failure on fuzzy LLM, missed-scan re-anon error), catch and fall back to Pass-1-only registry exact-match (the Phase 2 D-34 algorithm — pure registry lookup, cannot raise). Emit the partial result. `@traced` span tag `deanon_degraded=true`, counter `pii_deanon_degraded_total{reason}`.
- **Persistence semantics** — both user message and final assistant response are stored in `messages.content` in REAL form (PRD §3.3 step 9). Every chat turn re-anonymizes the full prior history; the per-thread registry guarantees deterministic surrogates so re-runs are correct (Phase 2 D-32 INSERT-ON-CONFLICT-DO-NOTHING absorbs duplicate writes).
- **Frontend SSE handling** — `frontend/src/lib/api.ts` SSEEvent discriminated union extended with `redaction_status`. `frontend/src/hooks/useChatState.ts` dispatch gains a case for the new event (display a subtle status spinner in the streaming bubble). No regression of existing CHAT-06 event handlers when redaction is OFF.
- **Pytest coverage** — `backend/tests/api/test_phase5_integration.py` mirrors the Phase 4 pattern (~600 lines, 7 test classes per ROADMAP SC#1..SC#5 + B4 caplog + egress trip). Privacy-invariant assertion (SC#1) via mocked `AsyncOpenAI` client that captures every recorded request payload; `for entry in registry.entries(): assert entry.real_value not in payload` for every captured payload.

Explicitly NOT in scope (deferred to later phases):
- **Per-thread `threads.redaction_enabled` column + admin UI toggle** — Phase 5 locks on the global env var `PII_REDACTION_ENABLED` (per SC#5 wording). Per-thread granularity is a Phase 6+ enhancement.
- **`messages.anonymized_content` sibling-column cache** — Phase 6 PERF-02 may revisit if profiling shows history-anonymization dominates per-turn latency.
- **Module-level LRU cache of `ConversationRegistry` instances** — Phase 6 perf hardening (Phase 2 'Deferred' list noted this).
- **Fake-stream chunked delivery of buffered de-anon output** — Phase 6+ if user feedback warrants progressive-feel UX.
- **`OpenRouterService` refactor to delegate through `LLMProviderClient`** — Phase 6+ unification; Phase 5 wraps with pre-flight egress filter at the call site instead.
- **Presidio-level batch NER in `redact_text_batch`** — Phase 6 PERF-02 optimization if profiling justifies.
- **`document_tool_service` (create / compare / compliance / analyze) auxiliary LLM coverage** — NOT chat-loop; expanding Phase 5 to cover it would add ~3-5 days of work and require a milestone-scope amendment (new REQ-IDs, possible new `document_registry` scope). Tracked as a v1.1 / future-phase backlog item.
- **`metadata_service` document-metadata extraction PII coverage** — same rationale as `document_tool_service`.
- **Post-stream output-side filter on cloud LLM responses** — PRD does not require it; carries forward Phase 3's deferral.
- **Frontend redesign of streaming UX for buffered mode** — minimum-viable integration ships a subtle spinner; full UX polish is a follow-up.
- **Latency-budget regression test** — Phase 6 PERF-02 owns this.

</domain>

<decisions>
## Implementation Decisions

### Redaction-Enabled Flag — Source of Truth & Off-Mode Plumbing

- **D-83 (BUFFER-01..03, TOOL-01..04, SC#5):** **Global env var `PII_REDACTION_ENABLED` is the v1.0 source of truth.** `settings.pii_redaction_enabled` (already shipped Phase 1, default `True`). The Phase 4 D-80 forward-reference to a per-thread flag is retired in Phase 5 — the TODO comments at `chat.py:218` and `agent_service.py:13` ("Phase 5 will swap to per-thread flag") are deleted, not implemented. SC#5 names the env var literal `PII_REDACTION_ENABLED=false`; per-thread granularity is not on PROJECT.md v1.0 scope; adding it would require migration 032 + thread-row column + admin UI toggle + i18n strings + RLS edge cases for one boolean. Per-thread flag tracked as a v1.1 / future-phase backlog item.

- **D-84 (SC#5, NFR-3):** **Hybrid gate — top-level branch + service-layer early-return.** Two cheap bool checks, both honoring different load-bearing contracts:
  1. **Top-level branch in `event_generator()`:** `if not settings.pii_redaction_enabled: <run existing Phase 0 CHAT-06 path verbatim>`. Zero registry load, zero SSE `redaction_status` events, zero `redact_text_batch` call, zero buffering. SC#5's "no behavioral regression" enforced at the surface where regression would actually be observed (frontend SSE event sequence).
  2. **Service-layer early-return inside `RedactionService.redact_text`:** Phase 1's TODO at `redaction_service.py:388-393` materialized — `if not get_settings().pii_redaction_enabled: return RedactionResult(anonymized_text=text, entity_map={}, hard_redacted_count=0, latency_ms=0.0)` BEFORE `_get_thread_lock` so the off-path is lock-free. Honors Phase 1 author's intent ("the gate goes here, not in callers, so every downstream consumer benefits automatically") for any forgotten future call site.
  
  Defense-in-depth covers both surfaces. Two cheap bool checks per call. Rejected: pure top-level (leaves Phase 1 TODO unimplemented), pure service-layer (forces the chat.py registry-load + SSE event emission cost on every off-mode turn).

- **D-85 (BUFFER-01, PRD §3.3 step 9):** **Persist BOTH user and assistant messages in REAL (de-anonymized) form.** The user message inserted at `chat.py:91-98` stays as raw real PII (current behavior, line 96: `'content': body.message`). The assistant response is the de-anonymized text (already real after `de_anonymize_text`). Every turn re-anonymizes the full prior history; the per-thread registry guarantees deterministic surrogates so re-runs are correct (Phase 2 D-32 INSERT-ON-CONFLICT-DO-NOTHING absorbs duplicate writes — zero new DB rows for already-known entities). Matches PRD §3.3 step 9 verbatim. Rejected: sibling `messages.anonymized_content` column (1 migration + cache-invalidation drift when registry mutations or fuzzy modes change), persist surrogate-form (contradicts PRD §3.3 step 9; massive blast radius — every messages GET endpoint, audit, frontend rendering needs de-anon wrappers).

- **D-86 (PRD §3.3 step 3, Phase 2 D-33):** **Registry loaded once at top of `event_generator()`; threaded as parameter through every redaction call site in the turn.** After thread validation, before history assembly: `registry = await ConversationRegistry.load(thread_id)` (one DB SELECT per turn). The single instance is passed through `_run_tool_loop`, `ToolService.execute_tool`, the auxiliary LLM call sites (classify_intent, title-gen), and any sub-agent path. Honors Phase 2 D-33 verbatim ("Lazy load at start of each chat turn"). `ToolService.execute_tool()` signature gains a `registry: ConversationRegistry | None = None` parameter; this is the unavoidable cost of TOOL-04 ("share parent's redaction-service instance"). Rejected: per-call-site `ConversationRegistry.load()` (N DB SELECTs per turn; potential mid-turn state divergence), module-level LRU cache (Phase 2 explicitly deferred to Phase 6).

### Buffering & SSE Event Shape

- **D-87 (BUFFER-01, FR-6.1, FR-6.3):** **Single-batch `delta` delivery after de-anon completes.** When redaction is ON: buffer the entire `OpenRouterService.stream_response(...)` output locally (accumulate `chunk["delta"]` strings into a single `full_response` buffer; emit zero progressive `delta` events during the stream). After buffering completes, run `de_anonymize_text(full_response, registry, mode=settings.fuzzy_deanon_mode)` once, emit ONE `data: {type: delta, delta: <de_anonymized_text>, done: false}` event followed immediately by `data: {type: delta, delta: '', done: true}`. Matches FR-6.3 verbatim ("emitted as a single batch on completion"); matches PRD §7.3 ("latency trade-off acceptable when paired with progress status events"). Frontend `useChatState.ts:138-183` already accumulates `delta` content into `streamingContent` so a single big chunk vs many tiny chunks renders identically — no frontend dispatcher change needed beyond the new `redaction_status` case. Rejected: fake-streaming chunked delivery (violates FR-6.3 "single batch"; misleads LangSmith spans because deltas no longer correspond to real LLM tokens), two-phase stream-then-replace (briefly leaks surrogates to user — privacy invariant break).

- **D-88 (BUFFER-02, FR-6.2):** **Two `redaction_status` SSE events bracket the buffer window.** Event timeline when redaction is ON:
  1. `agent_start: {agent, display_name}` (existing — emitted at top of branch A; branch B emits no agent event but the rest of the timeline still applies)
  2. `redaction_status: {stage: anonymizing}` (NEW — emitted immediately after the registry load + history-anonymization batch, before the first `OpenRouterService.complete_with_tools` call. Covers history anon + every tool-loop iteration.)
  3. `tool_start: {type, tool}` / `tool_result: {type, tool}` (skeleton form per D-89 — no payload)
  4. `redaction_status: {stage: deanonymizing}` (NEW — emitted after the final `stream_response` buffer completes, before `de_anonymize_text` runs)
  5. `delta: {delta: <full_de_anonymized_text>, done: false}` (single batch per D-87)
  6. `agent_done: {agent}` (existing)
  7. `thread_title: {thread_id, title}` (existing — emitted only on first exchange of a thread; the title is in real form per D-96)
  8. `delta: {delta: '', done: true}` (existing terminator)

  Singular `anonymizing` / `deanonymizing` phrasing in FR-6.2 implies one event per stage — not per-call. Rejected: per-stage events at every redact_text / de_anonymize_text site (noisy SSE; frontend dedup complexity), single coarse `active`/`complete` (loses stage information FR-6.2 names).

- **D-89 (BUFFER-03):** **Skeleton emit for `tool_start` / `tool_result` when redaction is ON; full payloads only when redaction is OFF.** When ON: `tool_start` event = `{type: 'tool_start', tool: <name>}` (NO `input` field); `tool_result` event = `{type: 'tool_result', tool: <name>}` (NO `output` field). Frontend's existing tool-name badge UX preserved (the badge uses `tool` name only, not `input`/`output`); user sees what the agent is doing without seeing surrogate-form text. PRD BUFFER-03 "sub-agent reasoning events suppressed" maps to tool-call payloads in this codebase (the visible reasoning trace). When redaction is OFF, current full-payload behavior preserved (SC#5). `agent_start.display_name` is a static `AgentDefinition` field — PII-free. Rejected: de-anonymize tool args/output before emit (each tool emit costs a 3-phase de-anon pass; tool_result outputs can be 50KB+ of RAG chunks; doubles/triples per-turn de-anon work for marginal UX value), suppress entirely (kills useful tool-activity transparency; over-strict reading of BUFFER-03's "reasoning" wording).

- **D-90 (PERF-04, NFR-3, OBS-02):** **Graceful degrade on de-anon failure — fall back to Pass-1-only exact-match.** If the 3-phase `de_anonymize_text` pipeline raises mid-turn (provider failure on fuzzy LLM mode, missed-scan re-anon error from Phase 4 D-78 path, validation failure):
  - Catch the exception, run `de_anonymize_text(text, registry, mode='none')` on the surrogate-form buffer (this invokes Pass-1-only registry exact-match — the Phase 2 D-34 algorithm — which is a pure registry lookup and cannot raise).
  - Emit the partial result as the single `delta` event (D-87 unchanged).
  - Log at WARNING with B4-compliant payload: `{"event":"deanon_degraded", "feature":"deanonymize_text", "fallback_mode":"none", "error_class":"<TimeoutError|HTTPError|ValidationError>", "reason":"<one-line>"}`. Never log raw payloads or PII.
  - Tag the `@traced(name='redaction.de_anonymize_text')` span: `deanon_degraded=true`, `degraded_reason=<error_class>`.
  - Increment counter metric `pii_deanon_degraded_total{reason}` (Prometheus/StatsD style; observability skill TBD by ops — Phase 6 hardens).
  - User sees real names mostly resolved with maybe-some-mangled surrogates surviving.

  Same pattern as Phase 4 D-78 missed-scan soft-fail. PRD NFR-3 forbids "crash" and "leak"; this satisfies both. Rejected: emit raw surrogate-form buffer (UX-broken — user sees Faker names like "Aaron Thompson DDS" instead of their real names), hard-fail with error event (loses the entire LLM response the user was waiting for; contradicts NFR-3).

### Tool-Call Symmetry — Chokepoint, Batching, Pre-Flight

- **D-91 (TOOL-01..04):** **Centralized recursive walker in new `backend/app/services/redaction/tool_redaction.py`.** Module exposes:

  ```python
  async def deanonymize_tool_args(
      args: Mapping[str, Any],
      registry: ConversationRegistry,
      redaction_service: RedactionService,
  ) -> dict[str, Any]:
      """Recursive walk over args; replace surrogate-form strings with real values.
      Skip rules: re.fullmatch(r'[0-9a-f-]{36}', s) (UUID regex), len(s) < 3."""

  async def anonymize_tool_output(
      output: Any,
      registry: ConversationRegistry,
      redaction_service: RedactionService,
  ) -> Any:
      """Recursive walk over output; collect strings, run redact_text_batch on the
      collected list, re-zip back into the structure. Same skip rules as above."""
  ```

  Invoked in `chat.py` `_run_tool_loop` AROUND `tool_service.execute_tool(...)`:
  ```python
  args = await deanonymize_tool_args(func_args, registry, redaction_service)
  tool_output = await tool_service.execute_tool(func_name, args, user_id, tool_context, registry=registry)
  tool_output = await anonymize_tool_output(tool_output, registry, redaction_service)
  ```
  
  `tool_service.py` itself stays tool-agnostic — no per-tool wiring sprawl. The walker is naturally correct for every tool because Phase 1 D-04's UUID filter is also a defense-in-depth: even if a UUID slips past the skip rule and hits `redact_text`, `detect_entities` short-circuits on UUID-shaped strings. RAG chunks (PRD §3.2 says ingestion is NOT redacted) get their `chunk["content"]` field anonymized on the way out — new entities first-mentioned in retrieved chunks get registered into the per-thread registry at this point. Rejected: per-tool wrappers in `tool_service.execute_tool` switch (8 tools to wire today — search_documents, query_database, web_search, kb_list_files, kb_tree, kb_grep, kb_glob, kb_read — easy to forget when adding a 9th tool), hybrid centralized + tool-specific allowlist (schema drift cost when tools evolve; another file to maintain).

- **D-92 (TOOL-01..04, PERF-04):** **New `RedactionService.redact_text_batch(texts: list[str], registry: ConversationRegistry) -> list[str]` public method.** Single asyncio.Lock acquisition spans the batch; per-string `_redact_text_with_registry` runs internally (existing implementation reused — no Phase 1 NER refactor). For a 10-result `search_documents` output (~5 string fields per result = ~50 strings), this is 1 lock acquisition + 50 NER passes + 50 INSERT-ON-CONFLICT-DO-NOTHING upserts. Each upsert is fast for known entities (Phase 2 D-32). Phase 6 PERF-02 may add Presidio-level batch NER if profiling shows the per-string NER passes dominate per-turn latency (current Phase 1 NER is ~50ms per call). The batch primitive also satisfies the de-anon side: a corresponding `RedactionService.de_anonymize_text_batch` is NOT needed because de-anon is a pure registry lookup (no DB or lock acquisition); per-string de-anon is cheap. Rejected: sentinel-joined single NER call (sentinel collision risk if Presidio NER spans across the boundary; restoration after Presidio modifies the buffer is fragile), per-string `redact_text` (N lock acquisitions, strictly worse).

- **D-93 (BUFFER-01, TOOL-01..04, D-86, D-92):** **Single batched `redact_text_batch` call at top of `event_generator()` after registry load and BEFORE `agent_start` emit.** Concretely:

  ```python
  registry = await ConversationRegistry.load(body.thread_id)  # D-86
  if settings.pii_redaction_enabled:
      raw = [m["content"] for m in history] + [body.message]
      anonymized = await redaction_service.redact_text_batch(raw, registry)
      history = [{**h, "content": a} for h, a in zip(history, anonymized[:-1])]
      anonymized_message = anonymized[-1]
  else:
      anonymized_message = body.message  # D-84 off-path
  # ... downstream uses `history` + `anonymized_message`
  ```

  ONE asyncio.Lock acquisition for the entire history; ONE DB upsert batch (per D-92). All history surrogates resolved before any LLM contact. Rejected: per-message redact_text in a loop (N lock acquisitions; strictly worse than batch), lazy redact at LLM-payload-build time (scattered call sites: branch A's message build, branch B's message build, classify_intent's message build, title-gen's message build — easy to forget, single chokepoint is safer).

- **D-94 (BUFFER-01, NFR-2, PRD §11):** **Pre-flight egress filter wraps every `OpenRouterService` call when redaction is ON.** Three call sites in `chat.py`:
  - `_run_tool_loop` → `openrouter_service.complete_with_tools(messages, tools, model)` (per-iteration tool-call rounds)
  - Branch A → `openrouter_service.stream_response(messages, model)` (multi-agent final answer)
  - Branch B → `openrouter_service.stream_response(messages, model)` (single-agent final answer)
  
  Each site, when redaction is ON, is wrapped:
  ```python
  if settings.pii_redaction_enabled:
      result = egress_filter(json.dumps(messages), registry, provisional=None)
      if result.tripped:
          # log per Phase 3 D-55 (counts + entity_types + 8-char SHA-256 hashes)
          # emit redaction_status: {stage: blocked} + delta: {done: true}
          raise EgressBlockedAbort()
  # ... proceed with LLM call
  ```
  
  Trip behavior: structured-log + emit error event (`{type: error, message: 'egress_blocked'}`) + abort the turn cleanly. NO algorithmic fallback — chat LLM IS the answer-generation step (unlike Phase 3 entity_resolution which has algorithmic fallback). Reuses Phase 3 `egress_filter` helper unchanged; no new code in `egress_filter` itself. `provisional=None` is correct because D-93's history-anonymization batch already commits new entities to DB before any cloud LLM contact (in-flight provisional set = ∅ after history anon). Phase 3 D-49's `LLMProviderClient` egress filter remains the chokepoint for auxiliary calls (entity_resolution, missed_scan, fuzzy_deanon — all already wired). Rejected: refactor `OpenRouterService` to delegate through `LLMProviderClient` (large blast radius — touches title-gen, classify_intent, document_tool_service; LLMProviderClient lacks streaming support; adds 'chat_completion' to Literal feature enum), skip egress filter on main chat call (violates NFR-2 "defense-in-depth required"; Phase 1 NER miss could leak raw PII to OpenRouter unchecked).

### Sub-Agent / Auxiliary-LLM Coverage

- **D-95 (BUFFER-03, TOOL-04):** **Phase 5 stays chat-loop-only.** In scope: 4 sub-agent paths inside `_run_tool_loop` (research / data_analyst / general / explorer), `agent_service.classify_intent`, `chat.py:269-283` thread-title generation. Out of scope (deferred to v1.1 / future-phase backlog): `document_tool_service` (create/compare/compliance/analyze) auxiliary LLM coverage; `metadata_service` document-metadata extraction PII coverage. Rationale: Phase 5's ROADMAP title is "Chat-Loop Integration"; expanding to non-chat-loop adds ~3-5 days of work, requires a milestone-scope amendment (new REQ-IDs absent from REQUIREMENTS.md today), and may need a separate `document_registry` scope (those tools are document-scoped, not conversation-scoped). The 4 chat-loop sub-agent paths are covered automatically by D-86 (registry threading) + D-91 (walker) + D-93 (history anon) + D-94 (pre-flight egress) because they run inside `_run_tool_loop` against the same `OpenRouterService` calls. PRD §3.5's "share parent's redaction-service instance" is automatic via the `get_redaction_service()` `@lru_cache` singleton in the codebase (already module-level singleton at `redaction_service.py:1041`).

- **D-96 (PRD §3.6, Phase 3 D-49, D-57):** **Hybrid auxiliary-LLM coverage — `title_gen` migrates to `LLMProviderClient`, `classify_intent` stays on `OpenRouterService` with anonymized inputs + pre-flight egress.**
  - **`thread-title generation` (chat.py:269-283):** Replace the existing `openrouter_service.complete_with_tools(title_messages)` call with `await llm_provider_client.call(feature='title_gen', messages=anonymized_title_messages, registry=registry)`. The `feature='title_gen'` Literal is already in Phase 3 D-49's enum; the `title_gen_llm_provider` `system_settings` column is already shipped from Phase 3 D-57; the per-feature override resolution (Phase 3 D-51) flows through automatically. Egress filter and provider routing are inherited from Phase 3 — Phase 5 adds zero new code in `LLMProviderClient`. Input messages are anonymized via the per-turn registry (D-93 already covers `body.message`). LLM emits a surrogate-form title; Phase 5 runs `de_anonymize_text(title, registry, mode='none')` (Pass-1-only is sufficient — titles are short and the registry should hit-or-miss exact-match; fuzzy is overkill here) before persistence + `thread_title` SSE event emit. Zero new migration; zero admin UI change.
  - **`agent_service.classify_intent`:** Stays on `OpenRouterService.complete_with_tools(messages, tools=None, model=model, response_format={"type": "json_object"})`. Phase 5 changes:
    1. Anonymize `body.message + history[-3:]` via the per-turn registry before calling. The anonymization is part of D-93's history batch — `classify_intent` receives the already-anonymized message + history strings as parameters from `chat.py` (signature change: `classify_intent(message: str, history: list[dict], openrouter_service, model)` keeps shape; caller passes anonymized values).
    2. Pre-flight egress filter wraps the call (D-94 pattern reused as a private helper or extended to cover the call site).
    3. LLM returns `OrchestratorResult.agent` enum string (`"research"` / `"general"` / `"data_analyst"` / `"explorer"`) — no de-anonymization needed (no PII in the output).
  
  Rejected: full migration of both to `LLMProviderClient` (1 new migration for `intent_classification_llm_provider` column + 2 admin UI fields + LLMProviderClient gains a non-streaming text-output use case that may not fit cleanly with `response_format=json_object`; blast radius into Phase 3 file), keep both on OpenRouterService (ignores PRD §3.6's explicit naming of `title_gen`).

### Testing

- **D-97 (Phase 5 ROADMAP SC#1..SC#5):** **Mirror Phase 4's `test_phase4_integration.py` pattern at `backend/tests/api/test_phase5_integration.py`.** ~600 lines, 7 test classes:
  - **`TestSC1_PrivacyInvariant`** — Live Supabase + mocked `AsyncOpenAI` client wrapped to capture EVERY recorded request payload across `complete_with_tools` and `stream_response` calls. Run a representative chat turn that mentions a real PERSON, EMAIL, and PHONE. Assertion: `for payload in captured_llm_payloads: for entry in registry.entries(): assert entry.real_value not in payload`. Plus LangSmith span-attribute capture if `@traced` is mocked (Phase 1 D-16 pattern).
  - **`TestSC2_BufferingAndStatus`** — `FastAPI TestClient` SSE consumption; assert event sequence: `agent_start → redaction_status:anonymizing → tool_start (skeleton) → tool_result (skeleton) → redaction_status:deanonymizing → delta (single, full text) → agent_done → thread_title (first exchange) → delta:done`.
  - **`TestSC3_SearchDocumentsTool`** — Mocked `search_documents` response with seeded chunks containing real PII; assert tool was invoked with the REAL query (de-anonymized from LLM's surrogate-form `args["query"]`); assert the `messages.append({role: 'tool', ...})` payload sent to the LLM contains surrogates only.
  - **`TestSC4_SqlGrepAndSubAgent`** — `query_database` (de-anon SQL → execute → re-anon results), `kb_grep` (de-anon pattern → execute → re-anon results), and a sub-agent (research) invocation that performs a tool call — assert parent's registry instance is passed through; no double-anonymization (calling `redact_text` on already-surrogate text returns identity).
  - **`TestSC5_OffMode`** — Set `PII_REDACTION_ENABLED=false`; assert event sequence == pre-milestone CHAT-06 baseline + ZERO `redaction_status` events + ZERO buffering (progressive `delta` events flow as before) + tool_start/tool_result emit FULL payloads.
  - **`TestB4_LogPrivacy`** — `caplog` invariant: assert no real PII appears in any log record across the full chat turn (extends Phase 1 B4 / Phase 2-3 / Phase 4 D-78 pattern to Phase 5's new D-90 degrade log + D-94 egress trip log).
  - **`TestEgressTrip_ChatPath`** — Inject a payload that contains a registered real value (simulate Phase 1 NER miss); assert the egress filter trips; assert NO LLM call was made; assert error event emitted; assert turn aborts cleanly.
  
  Live Supabase project `qedhulpfezucnfadlfiz` for `entity_registry` (Phase 4 `test_phase4_integration.py` already wires this). Mocked OpenAI SDK at the `AsyncOpenAI` client level — no actual httpx traffic. Test fixture seeds: deterministic Faker via `seed_instance` (Phase 1 D-20 carryover).

### Claude's Discretion

- **Module split for the tool-redaction walker** — whether `deanonymize_tool_args` and `anonymize_tool_output` live in one file (`tool_redaction.py`) or split into separate modules. Single file is simpler and they share the recursive walker helper.
- **`_run_tool_loop` lift** — whether to keep it as a closure inside `event_generator` (current shape) or lift to a top-level method on a helper class. Phase 5's added redaction parameters increase the closure's capture set; refactor may improve readability. Planner picks based on diff size.
- **`tool_redaction.py` walker recursion limit** — depth limit on recursion to prevent pathological inputs; default 10 levels is defensible. Planner picks.
- **Frontend SSEEvent type union extension** — whether to add `redaction_status` as a new variant or wrap inside the existing `progress`/`status` patterns. Add a discriminated `redaction_status` variant for cleanliness.
- **Spinner UI strings** — Indonesian + English i18n strings for "Anonymizing…" / "Restoring names…". Translation copy is the i18n maintainer's call.
- **Whether `redact_text_batch` releases the lock between strings** — for N=50 strings, holding the lock for ~2.5s blocks any concurrent same-thread chat turn. Acceptable for v1.0 (one user, one thread, low contention). Phase 6 PERF-02 may revisit.
- **Egress trip emit shape** — whether to emit a generic `{type: error, message: 'egress_blocked'}` or a typed `{type: redaction_status, stage: 'blocked', reason: '<class>'}`. Latter is more uniform with the rest of D-88 status events. Planner picks.
- **Title-gen mode for de-anon** — D-96 specifies `mode='none'` (Pass-1-only). If profiling shows fuzzy de-anon helps title quality, Phase 6 may revisit.

### Folded Todos

(None — `gsd-sdk query todo.match-phase 5` returned 0 matches.)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source PRD (authoritative for v1.0 milestone)
- `docs/PRD-PII-Redaction-System-v1.1.md` §3.1 (Core Principle), §3.3 (Chat / Main Agent flow — buffering at step 6, store de-anon at step 9), §3.4 (Tool Calls — symmetric anon-input/de-anon-output table), §3.5 (Sub-Agents — share redaction-service instance, suppress reasoning when redaction active, revert to streaming when off), §3.6 (Auxiliary LLM Calls — local vs cloud invariants per operation), §4.FR-6.1 (full buffering), §4.FR-6.2 (anonymizing/deanonymizing status events), §4.FR-6.3 (sub-agent reasoning suppression), §4.FR-7.1 (system-prompt verbatim guidance — already shipped Phase 4), §4.FR-9 (LLM configuration — provider plumbing already shipped Phase 3), §5.NFR-2 (Security — egress filter required defense-in-depth), §5.NFR-3 (Reliability — graceful degradation, never crash, never leak), §5.NFR-4 (Observability — log provider per call + egress results), §7.3 (Why Buffer-and-De-anonymize — latency offset by status events), §7.6 / §11 (Threat model — egress filter as primary control)

### Project + Milestone Plan
- `.planning/PROJECT.md` "Current Milestone" + "Key Decisions" — v1.0 scope; "Out of Scope (deferred)" line excludes per-thread / per-user redaction toggles
- `.planning/REQUIREMENTS.md` "v1 Requirements" — BUFFER-01..03, TOOL-01..04 are Phase 5's REQ-IDs
- `.planning/ROADMAP.md` "Phase 5: Chat-Loop Integration (Buffering, SSE Status, Tool/Sub-Agent Coverage)" — goal, dependencies (Phases 1-4), 5 success criteria

### Phase 1–4 CONTEXT (locked decisions Phase 5 builds on)
- `.planning/phases/01-detection-anonymization-foundation/01-CONTEXT.md` — D-13/D-14 (`redact_text(text, registry=None)` signature), D-04 (UUID filter — basis for D-91 walker skip rule), D-16 (`@traced` decorator), D-18 / B4 (never log raw PII — basis for D-90 logging contract), D-20 (Faker `seed_instance` for tests)
- `.planning/phases/02-conversation-scoped-registry-and-round-trip/02-CONTEXT.md` — D-21..D-24 (entity_registry table + UNIQUE constraint + hard-redact exclusion), D-25 (service-role-only RLS — registry writes), D-27/D-28 (ConversationRegistry / EntityMapping API), D-29/D-30 (per-thread asyncio.Lock + critical-section scope), D-31 (advisory-lock FUTURE-WORK Phase 6), D-32 (eager INSERT-ON-CONFLICT-DO-NOTHING — basis for D-92 batch upsert idempotence), D-33 (per-turn lazy load — basis for D-86), D-34 (Pass-1-only de-anon algorithm — basis for D-90 fallback), D-37 (cross-turn forbidden tokens, PERSON-only), D-39/D-40/D-41 (service composition + tracing span attributes — basis for D-90 span tags)
- `.planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md` — D-45/D-48 (Union-Find clustering + sub-surrogate variant rows), D-49 (LLMProviderClient `feature` Literal includes `title_gen` — basis for D-96), D-51 (per-feature provider override resolution — inherited by D-96 title_gen), D-52 (`LLM_PROVIDER_FALLBACK_ENABLED` knob), D-53..D-56 (pre-flight egress filter — basis for D-94 main chat path egress), D-57 (system_settings columns shipped: `title_gen_llm_provider` already in place — basis for D-96 zero-migration migration), D-58 (`CLOUD_LLM_API_KEY` env-only)
- `.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md` — D-71 (`de_anonymize_text(text, registry, mode=...)` 3-phase signature — basis for D-87 final response de-anon and D-90 fallback), D-72 (mode dispatch + LLM call via LLMProviderClient — basis for fuzzy LLM mode being available to Phase 5), D-74 (hard-redact survival inherited from REG-05), D-75 (auto-chain missed-scan inside redact_text — composes with D-93 batch), D-78 (soft-fail pattern — direct precedent for D-90), D-79 (centralized prompt-guidance helper module — already wired in chat.py:218 + agent_service.py L13/L30/L65/L85), D-80 (conditional injection on `redaction_enabled` — Phase 5 D-83 retires the per-thread aspiration, keeps the import-time evaluation correct under D-83's static-process-lifetime contract)

### Codebase Map (existing patterns to follow / reuse)
- `.planning/codebase/ARCHITECTURE.md` — "Flow 1 — Chat with tool-calling and SSE streaming" — full trace of current `POST /chat/stream` (steps 1-17); identifies the SSE event sequence Phase 5 extends
- `.planning/codebase/CONVENTIONS.md` — service-module shape, `@traced` decorator usage, Pydantic models, audit conventions
- `.planning/codebase/STRUCTURE.md` "Where to Add New Code" → "New backend service" — Phase 5's `tool_redaction.py` follows this directory pattern
- `.planning/codebase/STACK.md` — confirms `openai` SDK already in `requirements.txt` (LLMProviderClient + OpenRouterService both use `AsyncOpenAI`)
- `.planning/codebase/INTEGRATIONS.md` — Supabase + Railway env-var patterns (PII_REDACTION_ENABLED env defaults)

### Concrete code to read before editing (Phase 5 will modify or wrap these)
- `backend/app/routers/chat.py` (291 lines) — Primary Phase 5 surface. Top-level branch (D-84), registry load + history batch anon (D-86, D-93), three OpenRouterService call-site wrappings (D-94), tool-loop walker invocations (D-91), buffering logic (D-87), `redaction_status` SSE event emits (D-88), tool event skeleton mode (D-89), de-anon-fail degrade (D-90), title-gen migration (D-96).
- `backend/app/services/agent_service.py` (166 lines) — Retire the import-time `_PII_GUIDANCE` binding pattern (Phase 4 D-79 used it; Phase 5 D-83 makes the env-static-at-import semantics correct, but retire the per-thread TODO comment at line 12-15). Anonymize-input + pre-flight egress wrapper around `classify_intent`'s `complete_with_tools` call.
- `backend/app/services/redaction_service.py` (1049 lines) — Implement the early-return gate at `redaction_service.py:388-393` (the existing TODO; D-84). Add the new `redact_text_batch(texts, registry)` public method (D-92). Span-tag updates on `de_anonymize_text` for D-90 graceful-degrade.
- `backend/app/services/tool_service.py` (697 lines) — Signature change: `execute_tool(name, args, user_id, ctx, *, registry=None)`. NO per-tool wiring inside the dispatch switch (D-91 walker is centralized).
- `backend/app/services/openrouter_service.py` — Reference only. NOT modified in Phase 5 (per D-94 decision; refactor is Phase 6+ deferred). Phase 5's pre-flight egress wrapping happens at the call site in chat.py.
- `backend/app/services/llm_provider.py` — Reference only. Phase 5 reuses `LLMProviderClient.call(feature='title_gen', ...)` per D-96 — zero changes to LLMProviderClient itself.
- `backend/app/services/redaction/prompt_guidance.py` — Reference only. Phase 4 D-79's import-time call still correct under D-83.
- `backend/app/services/redaction/registry.py` — Reference only. `ConversationRegistry.load(thread_id)` is the entry point per D-86; no changes.
- `backend/app/services/redaction/__init__.py` — Add re-export for the new `tool_redaction` helpers (D-91): `deanonymize_tool_args`, `anonymize_tool_output`. Continue the Phase 2-4 pattern.
- `backend/app/config.py` — `pii_redaction_enabled` already at line 77 (Phase 1). NO new env vars added in Phase 5; D-83 lock keeps it global env-only.
- `frontend/src/lib/api.ts` (or wherever SSEEvent type union lives) — Extend the discriminated union with `{type: 'redaction_status', stage: 'anonymizing' | 'deanonymizing' | 'blocked'}`.
- `frontend/src/hooks/useChatState.ts:138-183` — Dispatch case for the new event; renders a subtle status spinner. Existing `delta` accumulator path unchanged.
- `frontend/src/components/ChatMessage.tsx` (or equivalent) — Optional: visual indicator for the spinner. i18n strings via `I18nProvider`.

### External docs (planner will fetch via context7 / web)
- OpenAI Python SDK `AsyncOpenAI` streaming behavior — confirm that buffer-and-de-anon doesn't break the SDK's connection-keepalive contract on long-buffered turns.
- FastAPI `StreamingResponse` flushing semantics — confirm `X-Accel-Buffering: no` (already set at chat.py:290) is sufficient with single-batch deltas.
- React 19 Suspense / `useTransition` patterns for spinner-during-buffered-stream — frontend skill TBD; Phase 5 minimum is plain conditional rendering.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`get_redaction_service()` (`backend/app/services/redaction_service.py:1041`)**: Module-level `@lru_cache` singleton. PRD §3.5's "share parent's redaction-service instance" is automatic — every call site gets the same instance for free. No Phase 5 work needed for this invariant.
- **`ConversationRegistry.load(thread_id)` (Phase 2 `registry.py`)**: Per-turn lazy-load entry point. D-86 calls this once per turn at the top of `event_generator()`. Returns the in-memory wrapper Phase 5 threads through every redaction call site.
- **`RedactionService.redact_text(text, registry)` (`redaction_service.py:348`)**: Phase 1-3 single-call entry. Phase 5 adds the early-return gate at `:388-393` (existing TODO) and adds the new batch primitive (D-92).
- **`RedactionService.de_anonymize_text(text, registry, mode)` (Phase 4 D-71)**: Phase 5's final-response de-anon step. D-90 wraps it with try/except for graceful degrade.
- **`egress_filter(payload, registry, provisional)` (Phase 3 D-49 / `llm_provider.py`)**: Pre-flight scan helper. Phase 5 D-94 reuses unchanged at three new chat.py call sites.
- **`LLMProviderClient.call(feature='title_gen', messages, registry)` (Phase 3 D-49)**: Title-gen migration target per D-96. `title_gen` already in the Literal enum; `title_gen_llm_provider` system_settings column already shipped (Phase 3 D-57). Egress filter inherited.
- **`get_pii_guidance_block(redaction_enabled)` (Phase 4 D-79 / `prompt_guidance.py`)**: Already wired in `chat.py:218` and `agent_service.py:L13/L30/L65/L85`. Phase 5 D-83 retires the per-thread TODO comments only — module behavior unchanged.
- **`@traced(name=...)` decorator (`tracing_service.py`, Phase 1 D-16)**: Phase 5's new functions (`redact_text_batch`, `deanonymize_tool_args`, `anonymize_tool_output`) wrap with this for span coverage.
- **Phase 2 D-30 per-thread asyncio.Lock**: Phase 5's new `redact_text_batch` acquires the same lock once per call (instead of once per string). Phase 6 D-31 advisory-lock upgrade still applies.
- **Phase 2 D-32 INSERT-ON-CONFLICT-DO-NOTHING upsert path**: D-92 batch upsert idempotence relies on this. D-93 history re-anonymization across turns is correct because re-runs find existing rows and skip.
- **`get_system_settings()` 60s TTL cache (Phase 2 D-21)**: D-87's `de_anonymize_text(..., mode=settings.fuzzy_deanon_mode)` reads through this; admin-UI changes propagate within the TTL window.
- **`@lru_cache` singleton + lazy load pattern (Phase 1 D-15)**: All redaction primitives (Presidio, Faker, gender detector) are warm-loaded once at startup. Phase 5 adds zero new singletons.
- **Phase 1 D-04 UUID filter inside `detect_entities`**: Defense-in-depth complement to D-91's UUID skip rule in the walker — UUIDs short-circuited at both layers.

### Established Patterns

- **SSE event encoding**: `f"data: {json.dumps(payload)}\n\n"` — standard chat.py emit shape. Phase 5's new `redaction_status` events follow the same form.
- **`event_generator()` async generator**: Phase 5's buffering work happens INSIDE this generator (the `stream_response` chunks accumulate locally before any user-visible emit). Existing try/except wrapper (chat.py:244-246) preserved.
- **Branch-aware history loading**: Phase 5's history batch (D-93) operates on the result of either branch-mode walk (chat.py:57-75) or flat-mode load (chat.py:77-85). One uniform input shape downstream.
- **Tool-call record persistence (`ToolCallSummary`, `ToolCallRecord`)**: Phase 5 stores anonymized-form tool args/results in the `tool_calls` JSONB column? — DECISION: store DE-ANONYMIZED form (real values) consistent with D-85's persist-real-form contract. Re-anonymized fresh on each turn that displays the message history.
- **`OpenRouterService.complete_with_tools(messages, tools, model)` non-streaming + `stream_response(messages, model)` streaming**: Phase 5 wraps both with pre-flight egress filter (D-94) but does NOT change the OpenRouterService API.
- **Auto-title generation (chat.py:269-283)**: Phase 5 migrates this to LLMProviderClient (D-96) — same trigger condition (`thread.title == "New Thread"` and `full_response is non-empty`), same emission shape (`thread_title` SSE event), but the LLM call routes through Phase 3's provider abstraction.
- **Pydantic `BaseModel` + `frozen=True` for service I/O**: Phase 5's new walker functions return `dict[str, Any]` (recursive shape; not Pydantic-modeled — too dynamic for the structures tools return).
- **Service-role-only RLS for system-level tables**: `entity_registry` (Phase 2 D-25) — Phase 5's batch upsert uses `get_supabase_client()` (service role) per the established pattern.

### Integration Points

- **NEW `backend/app/services/redaction/tool_redaction.py`**: `deanonymize_tool_args(args, registry, redaction_service)` + `anonymize_tool_output(output, registry, redaction_service)` recursive walkers + UUID/length skip rules + `@traced` span wrappers (D-91).
- **MODIFY `backend/app/routers/chat.py`**: Top-level branch (D-84), registry load (D-86), batch history anon (D-93), three pre-flight egress wrappers (D-94), tool-loop walker invocations (D-91), buffering of stream_response (D-87), `redaction_status` SSE event emits (D-88), tool event skeleton mode (D-89), graceful-degrade wrapper around final de-anon (D-90), title-gen migration to LLMProviderClient (D-96), `body.message` anonymization for classify_intent (D-96).
- **MODIFY `backend/app/services/agent_service.py`**: `classify_intent` signature accepts already-anonymized message + history (D-96); internal pre-flight egress wrapper around `complete_with_tools`. Retire per-thread TODO comments at L12-15.
- **MODIFY `backend/app/services/redaction_service.py`**: Implement the early-return gate at `:388-393` (D-84). Add `redact_text_batch(texts, registry)` public method (D-92). Span tags + try/except in `de_anonymize_text` for D-90 graceful degrade.
- **MODIFY `backend/app/services/tool_service.py`**: Signature change: `execute_tool(name, args, user_id, ctx, *, registry=None)`. NO per-tool wiring inside the switch (D-91 is centralized).
- **MODIFY `backend/app/services/redaction/__init__.py`**: Re-export `deanonymize_tool_args`, `anonymize_tool_output` (continues Phase 2-4 pattern).
- **MODIFY `frontend/src/lib/api.ts` (or SSEEvent type-union home)**: Extend discriminated union with `redaction_status` variant.
- **MODIFY `frontend/src/hooks/useChatState.ts`**: Dispatch case for `redaction_status`; render a subtle status spinner in the streaming bubble. No changes to existing `delta` / `tool_*` / `agent_*` handlers when redaction is OFF.
- **MODIFY `frontend/src/i18n/*.ts`**: New strings for "Anonymizing…" / "Restoring names…" / "Egress blocked" (Indonesian default + English).
- **NEW `backend/tests/api/test_phase5_integration.py`**: 7 test classes per D-97. Live Supabase + mocked AsyncOpenAI + caplog + `@traced` mock.
- **NOT modified in Phase 5**: `backend/app/services/openrouter_service.py` (D-94 wraps at call site, no API change), `backend/app/services/llm_provider.py` (D-96 reuses unchanged), `backend/app/services/document_tool_service.py` (D-95 deferred), `backend/app/services/metadata_service.py` (D-95 deferred), `backend/app/main.py` lifespan (no new warm-up — all primitives already lazy-loaded), `supabase/migrations/` (zero new migrations).

</code_context>

<specifics>
## Specific Ideas

- **The privacy invariant lives or dies at the chat-loop boundary.** Phases 1-4 built the primitives; Phase 5 is where they actually compose into a defensible product. SC#1's invariant assertion (`for entry in registry.entries(): assert entry.real_value not in payload`) is the single most important test in this phase — every other SC is downstream of "did the LLM see surrogates only".
- **Single chokepoint for tool I/O is the right architectural call.** Per-tool wrappers compound to N edits-per-new-tool; the centralized walker keeps `tool_service.py` unaware that redaction even exists. The walker's correctness invariants (UUID skip + len<3 skip + recursive descent) are simple enough to fully test in isolation.
- **D-94's pre-flight egress filter on OpenRouter calls is non-optional.** Without it, a Phase 1 NER miss in history anonymization leaks raw PII to OpenRouter unchecked. NFR-2 is explicit: defense-in-depth is required, not optional. The ~10-50ms per-call cost is acceptable.
- **D-93's batch anon is the perf design point.** Per-message redact_text in a loop is N lock acquisitions + N upsert hops. Phase 5 either ships D-93 or ships a turn that takes seconds on history-heavy threads.
- **D-90's graceful degrade is the operability design point.** Without it, a transient fuzzy-LLM failure crashes the chat turn the user was waiting through — an unacceptable UX regression vs the pre-milestone baseline. PERF-04 + Phase 4 D-78 set the pattern; D-90 inherits.
- **D-83 / D-95 are scope-locking decisions.** Per-thread flags and document_tool_service coverage are both "would be nice for v1.0" but neither is on the milestone REQ-IDs. Phase 5 ships chat-loop only; v1.1 picks them up. Do NOT reopen these without an explicit milestone-scope amendment.
- **D-87's single-batch delivery is the FR-6.3 contract.** Frontend renders the same on a single 4KB delta as on 100 × 40-byte deltas. Don't fake-stream for "progressive UX" — it lies in LangSmith spans and contradicts FR-6.3 verbatim.
- **The 4 chat-loop sub-agents are TOOL-04 covered automatically.** Don't write any Phase-5-specific sub-agent wiring; D-86 (registry threading) + D-91 (walker) + D-94 (egress) cover them. If a 5th agent is ever added to `agent_service.py`, it gets coverage for free.
- **The `_run_tool_loop` closure may need lifting.** Its capture set grows in Phase 5 (registry, redaction_service, settings.pii_redaction_enabled gating). Planner can decide to lift to a module-level helper if the diff size justifies it.

</specifics>

<deferred>
## Deferred Ideas

- **Per-thread `threads.redaction_enabled` column + admin UI toggle** — Phase 6+ enhancement. Migration 032 adds the column with `default true`; admin UI gains a toggle on the thread settings panel; chat.py reads `thread.redaction_enabled` instead of `settings.pii_redaction_enabled`. Out of v1.0 scope per D-83.
- **`messages.anonymized_content` sibling-column cache for history re-anonymization** — Phase 6 PERF-02 may revisit if profiling shows history-anonymization dominates per-turn latency. Avoids re-running NER on every prior message every turn. Costs: 1 migration + cache-invalidation logic when registry mutations or fuzzy modes change + double the messages-row size.
- **Module-level LRU cache of `ConversationRegistry` instances keyed by thread_id** — Phase 6 perf hardening (Phase 2 'Deferred' list noted this). Multi-instance Railway deploys eventually need cross-process cache invalidation — same advisory-lock concern as Phase 2 D-31.
- **Fake-stream chunked delivery of buffered de-anon output** — Phase 6+ if user feedback warrants progressive-feel UX. Splits the de-anon buffer into ~50-char slices with `await asyncio.sleep(0.02)` between. Violates FR-6.3 verbatim today; revisit only if UX research shows the single-batch UX is unacceptable.
- **`OpenRouterService` refactor to delegate through `LLMProviderClient`** — Phase 6+ unification. Removes the duplicate egress-filter call at chat.py call sites; provides cloud/local switching of the chat LLM as a side benefit. Cost: streaming support in LLMProviderClient + `chat_completion` in the Literal feature enum + touches title-gen, classify_intent, document_tool_service.
- **Presidio-level batch NER in `redact_text_batch`** — Phase 6 PERF-02 optimization. If profiling shows the per-string Presidio passes dominate per-turn latency, Phase 6 adds a Presidio batching adapter. v1.0 is functional-correct; latency target is Phase 6's concern.
- **`document_tool_service` (create / compare / compliance / analyze) auxiliary LLM coverage** — v1.1 / future-phase backlog item per D-95. NOT chat-loop. Likely needs a `document_registry` scope (those tools are document-scoped, not conversation-scoped). Open question: 1 registry per document, or per-document-per-user, or session-scoped ephemeral?
- **`metadata_service` document-metadata extraction PII coverage** — same rationale as `document_tool_service`. v1.1 / future-phase backlog.
- **Post-stream output-side filter on cloud LLM responses** — PRD does not require it; carries forward Phase 3's deferral. If a future leak is discovered (LLM emits a real value that wasn't in the pre-anonymized payload), revisit.
- **Frontend redesign of streaming UX for buffered mode** — minimum-viable integration ships a subtle spinner in the streaming bubble; full UX polish (skeleton chat bubble, animated dots, progress indicators) is a follow-up.
- **Latency-budget regression test (anonymization < 500ms, full chat round-trip < 5s)** — Phase 6 PERF-02 owns this.
- **Egress-trip alerting / rate limit / kill-switch** — Phase 6 hardening. If the same registry pattern keeps tripping the filter on the same thread, indicates a deeper bug; ops should get notified. Not v1.0.
- **`tool_calls` JSONB column anonymization for stored tool records** — D-85 stores in real form for consistency with `messages.content`; if that decision changes (e.g., compliance audit asks for surrogate-form audit-log), revisit.
- **Re-key the asyncio.Lock from `thread_id` to `(thread_id, user_id)` for shared-thread future support** — out of v1.0 scope; threads are user-scoped today.
- **`redact_text_batch` lock-release-between-strings micro-optimization** — Phase 6 perf if measured contention warrants. Releases the lock between per-string NER passes, allowing concurrent same-thread turns to interleave (with serializability still enforced by Phase 2 D-23 unique constraint).

### Reviewed Todos (not folded)

(None — `gsd-sdk query todo.match-phase 5` returned 0 matches.)

</deferred>

---

*Phase: 05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co*
*Context gathered: 2026-04-27*
