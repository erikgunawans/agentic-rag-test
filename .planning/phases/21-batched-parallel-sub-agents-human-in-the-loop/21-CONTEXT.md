# Phase 21: Batched Parallel Sub-Agents + Human-in-the-Loop - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement the two harness phase types Phase 20 explicitly stubbed with `PHASE21_PENDING` in `harness_engine.py`:

1. **`llm_batch_agents`** — Reads a JSON array of items from a workspace input file, chunks into batches of `batch_size` (default 5), runs each batch concurrently via `asyncio.gather()` + `asyncio.Queue` fan-in, streams sub-agent events in real-time, appends results to a JSONL output file atomically per item, merges to a clean JSON on completion, and resumes mid-batch from JSONL state on crash/interrupt (BATCH-01..07).

2. **`llm_human_input`** — Dispatches a small LLM call using the phase's `system_prompt_template` + `workspace_inputs` to generate an informed question, streams the question as normal delta events (renders as a chat message bubble), emits `harness_human_input_required` event, transitions `harness_runs.status` to `'paused'`, closes the SSE stream. User's next message triggers a resume branch in `chat.py` that writes the answer to the phase's `workspace_output` file and continues the harness from the next phase (HIL-01..04).

**No new migration.** `harness_runs.status='paused'` is already in migration 042's CHECK constraint and `ACTIVE_STATUSES` tuple. No new tables or columns needed.

**Strict scope guardrail:**
- Contract Review domain harness (8-phase workflow) and DOCX deliverable — Phase 22.
- Phase 20's smoke harness (`smoke_echo.py`) is EXTENDED with `llm_human_input` + `llm_batch_agents` phases for Phase 21 E2E testing. No new harness file needed.

</domain>

<decisions>
## Implementation Decisions

### HIL Resume Flow (HIL-01..04)

- **D-01 (Exclude 'paused' from the 409 block):** Change chat.py D-02's 409 condition from `status IN ('pending','running','paused')` to `status IN ('pending','running')`. When `harness_runs.status='paused'`, the message falls through to a new HIL resume branch. New check order at `stream_chat` entry:
  1. Phase 19 `ask_user` resume detection (existing — `agent_runs.status='waiting_for_user'`)
  2. **NEW** HIL resume detection (`harness_runs.status='paused'`)
  3. Harness active-run 409 block (now only blocks `pending`/`running`)
  4. Gatekeeper eligibility check
  5. Standard/deep dispatch

- **D-02 (HIL resume branch logic):** When `harness_runs.status='paused'` is detected:
  1. Read user's message body as the HIL answer string.
  2. Write answer to the workspace file specified by the current phase's `workspace_output` (e.g., `review-context.md`).
  3. Mark current phase complete in `harness_runs.phase_results[current_phase]` via `harness_runs_service.advance_phase()`.
  4. Call `run_harness_engine(start_phase_index=current_phase + 1, ...)` in a new SSE stream — continues harness from next phase.

- **D-03 (Add `start_phase_index: int = 0` to `run_harness_engine`):** Default 0 preserves backward compatibility for all existing callers. Engine skips phases `0..start_phase_index-1` (already recorded in `phase_results`). HIL resume passes `current_phase + 1`.

- **D-04 (HIL SSE event sequence — HIL-02):** Engine streams the question as follows, in order:
  1. `delta` events — question text streams as a normal assistant message bubble (HIL-02: "not in phase panel").
  2. `harness_human_input_required` event: `{type, question, workspace_output_path, harness_run_id}` — frontend can highlight the question bubble; tells frontend which file the answer will land in.
  3. `done: true` — SSE stream closes.
  - `harness_runs.status` transitions to `'paused'` in the DB BEFORE the SSE stream closes (so a concurrent reload sees the paused state immediately).
  - `HarnessBanner` transitions to "Awaiting your response — [harness type]" (EN) / "Menunggu respons Anda — [harness type]" (ID) when `harnessRun.status === 'paused'`.
  - The persisted assistant message for the question gets `messages.harness_mode='contract-review'` (same convention as gatekeeper and post-harness messages).

### Batch Output Format (BATCH-05, BATCH-07)

- **D-05 (JSONL append-only output — the resume artifact):** Each completed sub-agent atomically appends one newline-terminated JSON object to the workspace output file (e.g., `risk-analysis.jsonl`):
  ```
  {"item_index": 0, "result": {...}, "status": "ok"}
  {"item_index": 3, "result": {...}, "status": "ok"}
  {"item_index": 1, "status": "failed", "error": {"error": "sub_agent_failed", "code": "...", "detail": "..."}}
  ```
  Lines are unordered (concurrent appends). The file grows monotonically; no overwrite during a batch run.

- **D-06 (Merge pass after all batches complete — the downstream artifact):** Once all items are done, engine reads the JSONL, sorts by `item_index`, writes a clean `{basename}.json` (e.g., `risk-analysis.json`) as a final `WorkspaceService.write_file` call. This clean JSON is what Phase 22 reads. The JSONL stays as the resume artifact. Two workspace files per batch phase: `{name}.jsonl` (internal) + `{name}.json` (final output).

- **D-07 (BATCH-07 resume logic — computed at phase dispatch start):** At the start of every `llm_batch_agents` phase dispatch:
  1. Read `phase.workspace_output` as the base name (e.g., `risk-analysis`).
  2. Try to read `{base}.jsonl` from workspace. If it doesn't exist → fresh run (all items).
  3. Parse JSONL, collect `done_set = {row["item_index"] for row in rows}` (both `ok` and `failed` are "done").
  4. `remaining_items = [item for item in all_items if item.index not in done_set]`
  5. Re-chunk `remaining_items` into new batches of `batch_size` and run. Failed items are NOT retried — consistent with STATUS-03.

### Batch Streaming UX (BATCH-04, BATCH-06)

- **D-08 (New item-level SSE event types):** Phase 21 implements the Phase 20 reserved constants:
  - `harness_batch_item_start`: `{type, item_index, items_total, phase_name, harness_run_id}` — emitted when a sub-agent starts for a given item.
  - `harness_batch_item_complete`: `{type, item_index, items_total, status: "ok"|"failed", harness_run_id}` — emitted when a sub-agent finishes.
  - Phase-level `harness_batch_start` / `harness_batch_complete` (Phase 20 constants) cover the batch phase lifecycle.

- **D-09 (Extend existing frontend components only — no new component):**
  - Add `batchProgress: { completed: number; total: number } | null` slice to `useChatState`.
  - Reducer: `harness_batch_item_start` → set `batchProgress.total = items_total`; `harness_batch_item_complete` → increment `batchProgress.completed`; `harness_phase_complete` → clear `batchProgress` to null.
  - `HarnessBanner.tsx`: when `batchProgress` is non-null, append "— Analyzing clause {completed}/{total}" (EN) / "— Menganalisis klausula {completed}/{total}" (ID) to the existing banner text.
  - `TaskPanel.tsx`: handles `task_start`/`task_complete`/`task_error` from Phase 19 — no changes needed. Batch sub-agents feed the same task events with `task_id` tags.

- **D-10 (Batch sub-agent SSE tagging):** Each batch item's sub-agent is dispatched as a `run_sub_agent_loop` call with a unique `task_id` (server-generated UUID, matching Phase 19 D-13). The `task_start` event payload includes `batch_index: item_index` so the frontend can correlate which task belongs to which clause.

### Per-Item Failure Handling (STATUS-03 extension)

- **D-11 (Continue with failure marker — STATUS-03 consistent):** When a batch sub-agent fails (D-12 failure isolation from Phase 19 is inherited), the failure is written to JSONL:
  `{"item_index": N, "status": "failed", "error": {"error": "sub_agent_failed", "code": "...", "detail": "..."}}`.
  Batch continues with remaining items. `harness_batch_complete` SSE event includes `{failed_count: N}`. `harness_phase_complete` event includes `{partial: true}` if `failed_count > 0`. Phase 22 harness definitions handle partial `risk-analysis.json` gracefully (skip failed clauses in redline phase).

- **D-12 (Resume skips both 'ok' AND 'failed' items):** On mid-batch resume (D-07), `done_set` includes items with both `status='ok'` and `status='failed'`. Failed items are not re-queued. No implicit retry — user must cancel + re-trigger for a fresh run if retries are needed. Consistent with STATUS-03 and Phase 19 D-20.

### Claude's Discretion

- **asyncio.Queue fan-in multiplexer for batch concurrency:** `llm_batch_agents` dispatcher creates an `asyncio.Queue`, spawns batch items as `asyncio.create_task` coroutines, each putting SSE event dicts into the queue as they arrive. Main generator drains the queue in a `while not all_done` loop, yielding events in arrival order (natural interleaving). Standard Python fan-in pattern — mirrors Phase 19's executor SSE queue at `chat.py:455+`.
- **`item_index` is globally unique (0..N-1 across ALL batches):** Not per-batch. Multi-batch runs (e.g., 15 items at batch_size=5 → 3 batches) use the original item index from the parsed input array. Resume re-chunks remaining indices into fresh batches of `batch_size`.
- **HIL question generation — no new `PhaseDefinition` fields:** The `llm_human_input` dispatcher uses the existing `phase.system_prompt_template` (describes what question to ask) + `phase.workspace_inputs` (prior phase results to inform the question) for the LLM call. Pydantic output schema: `{question: str}` (simple).
- **Smoke harness extension for E2E testing:** `harnesses/smoke_echo.py` gains two new phases: Phase 3 = `llm_human_input` (question: "What test value should we use?", workspace_output = "test-answer.md") + Phase 4 = `llm_batch_agents` (batch_size=2, reads a synthetic 3-item input file, writes `test-batch.jsonl` + `test-batch.json`). `HARNESS_SMOKE_ENABLED` flag already exists.
- **HarnessBanner paused state:** `harnessRun.status === 'paused'` → banner body text changes to "Awaiting your response" (EN) / "Menunggu respons Anda" (ID). Cancel button stays visible. No new banner variant component needed — CSS state via existing conditional text.
- **`harness_human_input_required` event payload structure:** `{type: "harness_human_input_required", question: "...", workspace_output_path: "review-context.md", harness_run_id: "..."}`.
- **i18n strings (ID + EN):** Batch progress: "Analyzing clause N/M" (EN) / "Menganalisis klausula N/M" (ID). HIL paused banner: "Awaiting your response — Contract Review" (EN) / "Menunggu respons Anda — Tinjauan Kontrak" (ID).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary PRD & Roadmap
- `docs/PRD-Agent-Harness.md` §Feature 2.4 (lines 285–298) — `llm_human_input` phase type: question generation, pause/resume sequence, user response capture, workspace write.
- `docs/PRD-Agent-Harness.md` §Feature 2.5 (lines 300–312) — `llm_batch_agents` phase type: item parsing, concurrency via asyncio.gather, real-time Queue streaming, mid-batch resumability.
- `docs/PRD-Agent-Harness.md` §Phase type table (line 191–192) — canonical phase type enum values.
- `.planning/ROADMAP.md` §Phase 21 — Goal, depends_on (Phase 20), 11 requirements, 5 Success Criteria (authoritative scope).
- `.planning/REQUIREMENTS.md` §BATCH-01..07 and §HIL-01..04 — full requirement text for Phase 21's 11 requirements.
- `.planning/PROJECT.md` §"Current Milestone: v1.3" — invariants still in force (no auto-retry, no LangChain, egress filter on all LLM payloads, harness definitions global).
- `.planning/STATE.md` §"v1.3 contract / invariants" — STATUS-03 no-retry rule, privacy invariant, frontend loop stays in backend.

### Phase 20 (harness engine core) — direct predecessor
- `.planning/phases/20-harness-engine-core-gatekeeper-post-harness-file-upload-lock/20-CONTEXT.md` — D-01 `harness_runs` schema (`status='paused'` already reserved), D-02 409 condition (Phase 21 changes this), D-05 gatekeeper eligibility check order (Phase 21 inserts HIL resume BEFORE the 409 block), D-12 defense-in-depth lock enforcement (Phase 21 inherits), D-16 smoke harness (Phase 21 extends).
- `backend/app/services/harness_engine.py` — The Phase 21 implementation target. Lines 83–86: Phase 21 SSE event constants already declared. Lines 692–698: `PHASE21_PENDING` stubs to REPLACE. `run_harness_engine` signature to extend with `start_phase_index: int = 0`.
- `backend/app/services/harness_runs_service.py` — `ACTIVE_STATUSES` includes `'paused'` already. `advance_phase()`, `fail()`, `cancel()`, `get_active_run()` — service layer for HIL resume.
- `backend/app/routers/chat.py` — D-02 409 block (lines ~362–392, Phase 21 changes condition). Check order at `stream_chat` entry for HIL resume insertion point (lines ~362–430).
- `backend/app/harnesses/smoke_echo.py` — Extension target for Phase 21 E2E testing (add phases 3=llm_human_input + 4=llm_batch_agents).
- `backend/app/harnesses/types.py` — `PhaseDefinition` dataclass, `PhaseType` enum, `batch_size` field (already there, "used by Phase 21").

### Phase 19 (sub-agent loop) — batch sub-agent execution pattern
- `.planning/phases/19-sub-agent-delegation-ask-user-status-recovery/19-CONTEXT.md` — D-01 close-and-resume protocol (HIL mirrors this), D-06 nested tool events bubble up with task_id (batch inherits), D-08 context_files pre-load pattern (batch sub-agents use), D-11 sub-agent loop-cap fallback, D-12 failure isolation wrapper, D-13 task_id UUID server-side generation, D-20 no-retry hard rule (STATUS-03 — Phase 21 D-12 extends to batch).
- `backend/app/services/sub_agent_loop.py` — `run_sub_agent_loop()` function (line 412). REUSED VERBATIM by each batch item's sub-agent. Signature: `run_sub_agent_loop(description, context_files, parent_user_id, parent_user_email, parent_token, parent_tool_context, parent_thread_id, parent_user_msg_id, client, sys_settings, web_search_effective, task_id, parent_redaction_registry)`. NOTE: does NOT accept a `tools` parameter — tool curation happens at the phase level via `phase.tools` list, same as `llm_agent` dispatch in Phase 20.
- `backend/app/routers/chat.py` lines ~455+ — executor SSE event queue pattern. Phase 21 `asyncio.Queue` fan-in reuses this identical pattern.

### Phase 18 (workspace) — workspace I/O substrate
- `.planning/phases/18-workspace-virtual-filesystem/18-CONTEXT.md` — D-05 path validator, D-06 1 MB text cap, D-09 workspace REST endpoints.
- `backend/app/services/workspace_service.py` — `write_file()` (used by HIL answer write + batch JSONL append + merge write), `read_file()` (used by batch resume JSONL read + HIL `workspace_inputs` read).

### Phase 17 (deep mode + plan panel) — locked panel paused variant
- `.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-CONTEXT.md` — D-17 SSE event format.
- `frontend/src/components/chat/PlanPanel.tsx` — Phase 20 D-11 already reserves `paused` state in the render switch. Phase 21 confirms the paused lock icon + "Awaiting response" visual treatment.

### Frontend patterns to mirror
- `frontend/src/components/chat/HarnessBanner.tsx` — Phase 20 component. Extension target: add `batchProgress` display + `paused` state text.
- `frontend/src/components/chat/TaskPanel.tsx` — Phase 19 component. No changes needed; batch sub-agents feed existing `task_start`/`task_complete`/`task_error` events with `task_id` tagging.
- `frontend/src/hooks/useChatState.{ts,tsx}` — Phase 20 added `harnessRun` slice. Phase 21 adds `batchProgress` slice following the same pattern.
- `frontend/src/i18n/` — ID + EN strings for batch progress ("Menganalisis klausula N/M") and HIL paused banner ("Menunggu respons Anda").
- Vitest 3.2 — new tests: `HarnessBanner.batchProgress.test.tsx`, `useChatState.batchProgress.test.ts`, `HarnessBanner.paused.test.tsx`.

### Migration reference
- `supabase/migrations/042_harness_runs.sql` — `status CHECK IN ('pending','running','paused','completed','failed','cancelled')` already includes `'paused'`. **No new migration in Phase 21.**

### Project conventions
- `CLAUDE.md` — TDD rule (failing test first), STATUS-03 no-retry, privacy egress invariant, no LangChain/LangGraph, Pydantic structured outputs, glass-only-on-overlays.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`run_sub_agent_loop()`** (`backend/app/services/sub_agent_loop.py:412`) — REUSED VERBATIM for each batch item's sub-agent. No duplication. Failure isolation (D-12, Phase 19) already built in — sub-agent crash returns structured `task_error` event, never raises to caller.
- **`asyncio.Queue` event fan-in pattern** (`chat.py:455+`) — the sandbox SSE event queue pattern. `llm_batch_agents` dispatcher replicates this: shared queue, N `asyncio.create_task` coroutines each putting events into the queue, main generator drains.
- **Phase 20 SSE constants in `harness_engine.py:83-86`** — `EVT_BATCH_START`, `EVT_BATCH_COMPLETE`, `EVT_HUMAN_INPUT_REQUIRED` already declared. Phase 21 implements them.
- **`harness_runs_service.advance_phase()`** — HIL resume branch uses this to mark the current phase complete and write the answer into `phase_results`.
- **`WorkspaceService.write_file()`** — HIL answer write + batch JSONL atomic append + merge pass all use this. For JSONL appends: `WorkspaceService.append_line()` may need to be added (or `write_file` with content = existing + new line — plan-phase verifies).
- **`harness_runs_service.get_active_run()`** — HIL resume detection reads `status='paused'` via this existing service method (same method, different status value).
- **`PlanPanel.tsx` paused case** — Phase 20 D-11 already reserved `case 'paused':` in the render switch with a lock icon + "Awaiting response" stub. Phase 21 confirms/activates this.
- **`useChatState` reducer** — Phase 20 added `harnessRun` slice. Phase 21's `batchProgress` slice follows the identical pattern.

### Established Patterns
- **`PHASE21_PENDING` stubs in `harness_engine.py:692-698`** — two lines to replace with real dispatch logic. The `if phase.phase_type in (PhaseType.LLM_BATCH_AGENTS, PhaseType.LLM_HUMAN_INPUT):` branch is the Phase 21 implementation target.
- **Sub-agent tool curation** — `llm_agent` phase dispatch in Phase 20 builds a curated tool list from `phase.tools: list[str]`. Batch sub-agents use the same pattern (NOT a `tools` parameter on `run_sub_agent_loop` — curation happens before the call).
- **No new feature flag** — `HARNESS_ENABLED` already gates all harness code. `HARNESS_SMOKE_ENABLED` gates the smoke harness. Phase 21 adds no new env vars.
- **Atomic commits per plan** — each PLAN.md = one `gsd-sdk query commit` invocation.
- **SSE event format** — `data: {"type": "...", ...}\n\n` — batch item events follow.
- **Indonesian-default i18n** — all new banner/chip strings supply both ID + EN.

### Integration Points
- **`backend/app/routers/chat.py`:**
  - Lines ~362-392 (D-02 409 block): change `ACTIVE_STATUSES` condition to exclude `'paused'` — or inline the check as `status IN ('pending','running')`.
  - New HIL resume branch (after ask_user resume check, before 409 block): detect `status='paused'` → write answer → advance phase → call `run_harness_engine(start_phase_index=N+1)`.
- **`backend/app/services/harness_engine.py`:**
  - `run_harness_engine` signature: add `start_phase_index: int = 0` parameter.
  - `_run_harness_engine_inner`: skip phases `0..start_phase_index-1`.
  - `dispatch_phase` for `PhaseType.LLM_HUMAN_INPUT`: LLM call → delta events → `harness_human_input_required` event → DB transition to 'paused' → yield done → return.
  - `dispatch_phase` for `PhaseType.LLM_BATCH_AGENTS`: asyncio.Queue fan-in → batch resume logic → JSONL appends → merge pass → batch events.
- **`backend/app/services/workspace_service.py`:** May need `append_line(path, line)` method for atomic JSONL append — plan-phase verifies if `write_file` covers this or a new helper is needed.
- **`frontend/src/hooks/useChatState.{ts,tsx}`:** Add `batchProgress` slice + reducer cases for `harness_batch_item_start`/`harness_batch_item_complete`.
- **`frontend/src/components/chat/HarnessBanner.tsx`:** Add `batchProgress` display + paused state text variant.
- **`backend/app/harnesses/smoke_echo.py`:** Extend from 2-phase to 4-phase smoke harness (add `llm_human_input` + `llm_batch_agents`).

</code_context>

<specifics>
## Specific Ideas

- **JSONL file naming convention:** `{phase.workspace_output stem}.jsonl` alongside the final `{stem}.json`. E.g., for `workspace_output = "risk-analysis.json"`: resume artifact = `risk-analysis.jsonl`, final = `risk-analysis.json`. Plan-phase confirms the naming based on how `PhaseDefinition.workspace_output` is defined in Phase 20.
- **`harness_batch_item_start` event payload:** `{type: "harness_batch_item_start", item_index: 0, items_total: 15, phase_name: "Risk Analysis", harness_run_id: "..."}`.
- **`harness_batch_item_complete` event payload:** `{type: "harness_batch_item_complete", item_index: 0, items_total: 15, status: "ok"|"failed", harness_run_id: "..."}`.
- **`harness_phase_complete` extension for partial batches:** Add `failed_count: 0` field to the existing event payload. Plan-phase ensures this is additive (existing consumers ignore unknown fields).
- **HIL answer persistence:** The user's reply message is persisted to `messages` table with `harness_mode` set (same convention as gatekeeper and post-harness messages). This ensures history reconstruction shows the Q→A exchange.
- **Smoke harness Phase 3 (llm_human_input):** `system_prompt_template = "Generate one short clarifying question: 'What label should we put on the echo result?'"`, `workspace_inputs = ["echo-output.md"]`, `workspace_output = "test-answer.md"`.
- **Smoke harness Phase 4 (llm_batch_agents):** `workspace_inputs = ["test-items.md"]` (engine writes a synthetic 3-item JSON array in Phase 1), `workspace_output = "test-batch.json"`, `batch_size = 2`. Verifies 2-batch run (batch 0 = items 0+1, batch 1 = item 2).
- **Banner text pattern (ID/EN):**
  - Running: "Tinjauan Kontrak berjalan — fase N dari M (Nama Fase)" / "Contract Review running — phase N of M (Phase Name)"
  - Batch: adds " — Menganalisis klausula {N}/{M}" / " — Analyzing clause {N}/{M}"
  - Paused: "Menunggu respons Anda — Tinjauan Kontrak" / "Awaiting your response — Contract Review"

</specifics>

<deferred>
## Deferred Ideas

- **Contract Review domain harness (8-phase workflow)** — Phase 22. Phase 21 only adds the phase type implementations; Phase 22 registers the first real consumer harness.
- **DOCX deliverable** — Phase 22.
- **OCR fallback for scanned PDFs** — Phase 22+ per Phase 20 D-15.
- **`configurable max_failures threshold` in PhaseDefinition** — can be added post-Phase 22 if UAT shows batch phases need tolerance tuning. Phase 21 hard-codes "continue with marker" per D-11.
- **Re-run failed batch items without full harness restart** — would require a targeted resume path that re-runs only `status='failed'` items. Deferred; user can cancel + re-trigger for now.
- **Batch item retry budget in PhaseDefinition** — out of scope for v1.3 per STATUS-03 philosophy.
- **Per-item progress bar in plan panel** — a N-slot grid of clause status badges. Deferred; HarnessBanner N/M text is sufficient for v1.3.
- **Concurrent HIL phases (multiple pauses in one harness run)** — Phase 21 supports sequential HIL phases (each run-engine-resume cycle handles one). Concurrent HIL or nested HIL is not a v1.3 use case.
- **Multi-harness picker** — Phase 20 D-06 explicitly deferred until 2+ user-facing harnesses exist (post-Phase 22).
- **`harness_runs` history admin UI** — accumulated rows cleanup deferred (Phase 20 carryover).

</deferred>

---

*Phase: 21-batched-parallel-sub-agents-human-in-the-loop*
*Context gathered: 2026-05-04*
