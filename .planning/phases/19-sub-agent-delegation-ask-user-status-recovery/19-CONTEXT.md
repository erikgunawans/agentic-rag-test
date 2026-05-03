# Phase 19: Sub-Agent Delegation + Ask User + Status & Recovery - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the three placeholder stubs in `backend/app/services/deep_mode_prompt.py` (Phase 17 D-09) into real capabilities, plus the surrounding status / recovery / persistence machinery:

1. **`task(description, context_files)` LLM tool** — spawns a sub-loop with isolated context (system prompt + sub-agent's own message history starting with the description and pre-loaded `context_files`), capped at `MAX_SUB_AGENT_ROUNDS=15` (already in `config.py`), inheriting parent tools minus `task` (no recursion) and minus `write_todos`/`read_todos`. Sub-agent runs under the parent's user JWT — the Phase 18 workspace is shared automatically via thread-scoped RLS. Returns the sub-agent's last assistant message text as the parent's tool result; failures return as structured tool-error results (never crash the parent loop).
2. **`ask_user(question)` LLM tool** — pauses the loop. Backend persists pending state to a new `agent_runs` table, emits `ask_user` SSE event with `agent_status="waiting_for_user"`, then closes the SSE stream cleanly. User's next `/chat` POST is detected as the resume; backend rebuilds `loop_messages` from history + injects the answer as the `ask_user` tool result, then continues from the recorded `last_round_index`.
3. **Status indicators + append-only error model** — header chip (`working` / `waiting_for_user` / `complete` / `error`), failed tool calls persisted as `tool_result` rows with `output={"error": "...", "code": "..."}` JSON so the LLM can learn and recover, no automatic retries (LLM-driven recovery via STATUS-03 / success criterion #5), sub-agent failures isolated to the parent.
4. **Persistent state for paused/resumable sessions** — new `agent_runs` table (migration 040): one active row per thread (UNIQUE constraint), columns for status, pending_question, last_round_index, RLS thread-scoped. Foundation that Phase 20 `harness_runs` can mirror without confusion.
5. **Sub-agent SSE event taxonomy** — `task_start` / `task_complete` / `task_error` (with `task_id` for nesting). Sub-agent's internal `tool_start`/`tool_result` events bubble up through the parent's SSE stream tagged with `task_id` so the frontend can render the agent → tool → tool tree.
6. **Resume-after-pause UX** — header chip `🟣 Agent waiting for your reply`. The `ask_user` question rendered as the last assistant bubble with a distinct `?` icon. Input box stays normal; server-side detection of `agent_runs.status='waiting_for_user'` routes the next message body as the `ask_user` tool result.

**Strict scope guardrail (carried from ROADMAP.md):**
- Harness engine, gatekeeper LLM, post-harness LLM, file upload, locked Plan Panel — Phase 20.
- Batched parallel sub-agents (`llm_batch_agents`), human-in-the-loop (`llm_human_input`) phase types — Phase 21.
- Contract Review domain harness, DOCX deliverable — Phase 22.
- Existing v1.0 multi-agent classifier sub-agents (`research`, `data_analyst`, `general`, `explorer`) remain UNCHANGED. TASK-06 is satisfied additively — the new `task` tool does NOT replace or affect `agent_service.classify_intent()` and the existing multi-agent path in `chat.py` (lines 1208–1416). They coexist.

</domain>

<decisions>
## Implementation Decisions

### Pause/Resume Protocol (Area 1)

- **D-01 (Close-and-resume protocol):** When the LLM calls `ask_user(question)`, the deep-mode loop:
  1. Persists the pending state to `agent_runs` (status='waiting_for_user', pending_question=question, last_round_index=current round).
  2. Emits SSE events: `agent_status` (status='waiting_for_user') + `ask_user` (with the question).
  3. Yields `done` and **returns from the generator** — the SSE stream closes cleanly.
  4. Frontend renders the question as the last assistant bubble + header chip.
  5. User's next `POST /chat` is detected by the resume-detection branch (see D-03). The body's `message` field becomes the `ask_user` tool result string. Server reads `agent_runs` for the thread, rebuilds `loop_messages` from history + tool_calls JSONB, injects the tool result, and resumes the loop from the recorded `last_round_index`.
  - **Rationale:** matches FastAPI's request-scoped model, survives client disconnects/reloads, debuggable via DB state, mirrors Phase 17's mid-flight interrupt pattern (committed state + follow-up to resume). Reject long-poll (Railway proxy may kill long-held connections, asyncio events are process-local). Reject special POST endpoint (two frontend code paths, more API surface).

- **D-02 (No mid-stream resume — full reconstruction on resume):** The resumed `/chat` request reconstructs `loop_messages` from scratch by loading the thread's history (messages + tool_calls JSONB) and re-anonymizing through the egress filter. Cost: more DB roundtrips on resume; benefit: zero in-memory state assumptions (works across worker restarts, deploys, and HTTP layer kills).

### Persistent State (Area 1 — continued)

- **D-03 (`agent_runs` table — migration 040):** New migration `supabase/migrations/040_agent_runs.sql`. Sequencing: 038 was Phase 17 (`agent_todos`), 039 was Phase 18 (`workspace_files`), 040 is unblocked.
  - Schema:
    | Column | Type | Notes |
    |---|---|---|
    | `id` | `uuid PRIMARY KEY DEFAULT gen_random_uuid()` | |
    | `thread_id` | `uuid NOT NULL REFERENCES public.threads(id) ON DELETE CASCADE` | RLS anchor |
    | `user_id` | `uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE` | defense-in-depth |
    | `status` | `text NOT NULL CHECK (status IN ('working','waiting_for_user','complete','error'))` | the four PRD states |
    | `pending_question` | `text` | NULL unless status='waiting_for_user' |
    | `last_round_index` | `integer NOT NULL DEFAULT 0` | restart anchor |
    | `error_detail` | `text` | NULL unless status='error' |
    | `created_at` | `timestamptz NOT NULL DEFAULT now()` | |
    | `updated_at` | `timestamptz NOT NULL DEFAULT now()` | trigger-maintained |
  - Constraints:
    - `UNIQUE (thread_id) WHERE status IN ('working','waiting_for_user')` — partial unique index ensures **at most one active run per thread**. Completed/error rows accumulate as a history.
    - `CHECK ((status='waiting_for_user') = (pending_question IS NOT NULL))` — invariant.
  - RLS: thread-ownership scoped (mirrors `agent_todos` D-03 / `workspace_files` D-03):
    - `SELECT/INSERT/UPDATE/DELETE`: `EXISTS (SELECT 1 FROM threads WHERE threads.id = agent_runs.thread_id AND threads.user_id = auth.uid())` OR super_admin.
  - Indexes: `idx_agent_runs_thread_active (thread_id) WHERE status IN ('working','waiting_for_user')` for the resume-detection lookup; `idx_agent_runs_user_created (user_id, created_at DESC)` for admin auditing.

- **D-04 (Resume detection branch in `/chat`):** At the entry of `stream_chat` (in `chat.py`), BEFORE building the loop, check `agent_runs` for `(thread_id, status='waiting_for_user')`. If found:
  - Body's `message` field becomes the `ask_user` tool result string.
  - Body's `deep_mode` flag is ignored — resume follows the original run's mode.
  - Server transitions `agent_runs.status` to 'working', clears `pending_question`, increments `last_round_index`.
  - Loop continues from the recorded round (re-runs round N by injecting the tool result; the LLM sees a complete tool_call → tool_result pair and decides the next move).
  - Resume detection is gated behind `SUB_AGENT_ENABLED` flag (D-13); when off, `ask_user` is not registered, so this branch never triggers.

### Sub-Agent SSE Event Taxonomy (Area 2)

- **D-05 (Event names: `task_start` / `task_complete` / `task_error`):** Each event includes a `task_id` UUID for the frontend to nest descendants. Format:
  ```
  data: {"type":"task_start","task_id":"<uuid>","description":"...","context_files":[...]}\n\n
  data: {"type":"task_complete","task_id":"<uuid>","result":"...","rounds":N}\n\n
  data: {"type":"task_error","task_id":"<uuid>","error":"...","code":"..."}\n\n
  ```
  - **Coexistence:** `agent_start` (the v1.0 multi-agent classifier event) is UNCHANGED. The new `task_*` family is distinct. Frontend reducer dispatches independently.
  - **Naming rationale:** mirrors the LLM tool name `task` exactly; self-documenting.

- **D-06 (Nested tool events bubble up tagged with `task_id`):** Sub-agent's internal `tool_start` / `tool_result` events emit through the parent's SSE generator with an added `task_id` field referencing the parent `task_start`. Frontend reducer indents these under the sub-agent panel.
  ```
  parent: task_start(task_id=A)
  parent:   tool_start(task_id=A, tool=read_file)
  parent:   tool_result(task_id=A, tool=read_file)
  parent:   tool_start(task_id=A, tool=search_documents)
  parent:   tool_result(task_id=A, tool=search_documents)
  parent: task_complete(task_id=A, result='...')
  ```
  - **Implementation:** the sub-agent's loop is an inner async generator; the parent's SSE generator forwards every yield, applying the `task_id` tag at the wrapper boundary. The redaction-aware buffering wrapper in `chat.py` continues to apply.

- **D-07 (No nested `agent_status` events):** Only the OUTERMOST loop emits `agent_status` events. Sub-agents do not have their own status chip — they are visualized via `task_start` (active card) → `task_complete`/`task_error` (terminal state badge on that card). Avoids surface confusion.

### `task` Tool Semantics (Area 3)

- **D-08 (`context_files` pre-loads CONTENT into sub-agent's first user message):** Sub-agent's first message is shaped:
  ```
  <task>
  {description}
  </task>

  <context_file path="notes/research.md">
  {full content}
  </context_file>

  <context_file path="data/clauses.csv">
  {full content}
  </context_file>
  ```
  - Each path goes through `validate_workspace_path` (Phase 18 D-05); missing files surface as a structured tool error returned to the parent (no crash).
  - 1 MB cap per file (matches Phase 18 D-06). Combined-files cap: hard ceiling of 5 MB total to protect MAX_SUB_AGENT_ROUNDS context budget.
  - Binary files in `context_files` → structured error: `{"error": "binary_file_not_inlinable", "file_path": "..."}`. The LLM is told via the tool description to use `list_files`/`read_file` for binary content discovery.
  - Sub-agent ALWAYS retains `read_file` / `list_files` / `write_file` / `edit_file` (workspace tools), so it can fetch more if needed. Workspace is shared via thread-scoped RLS — the sub-agent runs under the parent user's JWT.

- **D-09 (Sub-agent tool inheritance):** Sub-agent receives parent's tool list MINUS:
  - `task` itself (no recursion — strict TASK-02 enforcement).
  - `write_todos` / `read_todos` (TASK-02 — todos are parent-scoped).
  - **NOT removed:** `ask_user` (sub-agent CAN escalate to the user — Phase 19's PRD doesn't forbid it; if the parent loop is paused while a sub-agent is running, the same close-and-resume flow applies). However, given the loop-cap of 15 rounds for sub-agents, this is rare. Plan-phase may decide to forbid sub-agent `ask_user` for simplicity in v1.3 — flagged for plan-phase.
  - All other tools inherited as-is, including web_search, search_documents, query_database, sandbox, MCP, skills, workspace tools.

- **D-10 (Sub-agent persistence):** Sub-agent rounds ARE persisted to the `messages` table with a parent-link. New nullable column `messages.parent_task_id UUID NULL` (added by migration 040 ALTER) so the message tree can be reconstructed on thread reload. The parent's `tool_result` row for the `task` call references the final sub-agent message via this chain. LangSmith tracing emits a sub-span per sub-agent.

- **D-11 (Sub-agent loop-cap fallback):** At `MAX_SUB_AGENT_ROUNDS=15`, if the sub-agent still emits tool_calls, the loop forces a final summary turn (mirrors Phase 17 D-12 — empty tool list + system message "summarize and deliver"). The summarized text becomes the `task` tool result. Avoids "ran out of rounds, no answer" failures.

- **D-12 (Sub-agent failure isolation — TASK-05 / STATUS-04):** Any uncaught exception inside the sub-agent loop is caught at the wrapper, converted to a structured `task_error` SSE event, and returned to the parent as the tool result: `{"error": "sub_agent_failed", "code": "...", "detail": "..."}`. Parent loop continues. Sub-agent crash NEVER propagates upward.

### Resume-After-Pause UX (Area 4)

- **D-13 (Header chip + question-as-bubble):** Chat header shows a status chip:
  - `🟣 Agent working` (status='working') — pulsing purple
  - `🟣 Agent waiting for your reply` (status='waiting_for_user') — solid purple with question-mark icon
  - `✓ Complete` (status='complete') — green check, fades after 3s
  - `⚠ Error` (status='error') — red, with retry affordance (re-send the original message)

- **D-14 (Question rendered as last assistant bubble):** The `ask_user` question is rendered as the last visible assistant message bubble, but with a distinct `?` icon (e.g. `MessageCircleQuestion` from lucide-react) and a subtle border-left accent so users see it's a question, not a normal assistant turn. Implementation extends `MessageView.tsx` with an `isAskUserQuestion` flag derived from the message's `tool_calls` JSONB (presence of an `ask_user` call without a matching tool_result row).

- **D-15 (Off-topic reply behavior — STATUS-03 honored):** If the user types a message that doesn't answer the pending question, the message body is passed through verbatim as the `ask_user` tool result string. The LLM sees it in the next round and decides:
  - If it's a valid answer → continue the plan.
  - If irrelevant → may call `ask_user` again to re-ask.
  - If a course-correction → adjust the plan (write_todos rewrites).
  - **Rationale:** matches success criterion #5 ("every recovery decision is LLM-driven and visible in the conversation transcript"). Trusts the model; mitigation = strong `ask_user` tool description guidance ("only call this when you genuinely need user clarification; user replies are passed through verbatim").

### Status Indicator & Feature Flag (Claude's Discretion)

- **D-16 (`agent_status` SSE event):** New event type `data: {"type":"agent_status","status":"working|waiting_for_user|complete|error","detail":"..."}\n\n`. Emitted at:
  - Loop start: `working`.
  - On `ask_user` tool call: `waiting_for_user` (with question in `detail`).
  - On final assistant text + `done` yield: `complete`.
  - On uncaught exception in parent loop (rare; tool errors are structured results, NOT exceptions): `error` with sanitized detail.
  - Frontend reducer maintains a `agentStatus` slice in `useChatState`; chip in chat header reads it.

- **D-17 (Single feature flag `SUB_AGENT_ENABLED`):** Mirrors `WORKSPACE_ENABLED` (Phase 18 D-08) and `SANDBOX_ENABLED` precedent. Pydantic Settings field in `config.py`, default `False`. When OFF:
  - `task` and `ask_user` tools NOT registered.
  - `agent_runs` table is unused.
  - Resume-detection branch in `/chat` short-circuits (returns immediately without DB lookup).
  - SSE event types `task_*` / `agent_status` not emitted.
  - Codebase is byte-identical to pre-Phase-19 when the flag is off.
  - Gated behind `DEEP_MODE_ENABLED` at the loop entry (the deep-mode loop is the only consumer; standard tool-calling loop is unaffected).
  - **Single flag rationale:** the three sub-features (task tool, ask_user, status indicators) are tightly coupled — `task_error` events depend on the status taxonomy, ask_user pauses depend on `agent_runs`. Splitting the flag would create matrix-of-states test pain with no real benefit.

### Append-Only Error Contract (Claude's Discretion)

- **D-18 (Tool-result error JSON shape):** Failed tool calls persist as `tool_result` rows with `output={"error": "<error_code>", "code": "<machine_code>", "detail": "<human-readable>"}`. The LLM sees this in the next round (append-only, no exception, no automatic retry). Examples:
  - Path validator: `{"error": "invalid_path", "code": "WS_INVALID_PATH", "detail": "Path contains '..' segment"}`
  - Sub-agent failure: `{"error": "sub_agent_failed", "code": "TASK_LOOP_CRASH", "detail": "<sanitized message>"}`
  - File too large: `{"error": "text_content_too_large", "code": "WS_LIMIT_EXCEEDED", "limit_bytes": 1048576, "actual_bytes": N}`
- **D-19 (No stack traces in tool results):** Stack traces are logged server-side (LangSmith + Python logger) but NOT included in the tool result payload. The LLM only sees a sanitized `detail` field. Privacy + payload-size protection. Internal traces stay in observability tooling.
- **D-20 (No automatic retries — STATUS-03 hard rule):** No catch-and-retry anywhere in the loop. Every recovery decision (retry, alternative path, ask_user escalation) is LLM-driven and visible in the conversation transcript. The deep-mode system prompt is updated (replacing the Phase 17 stub) to instruct: "When a tool fails, read the error result, decide whether to retry with different inputs, try an alternative tool, or use ask_user to escalate."

### Privacy & Security

- **D-21 (Egress filter coverage — SEC-04 carried):** All sub-agent LLM payloads (system prompt + first user message with context_files content + per-round messages + tool_calls) MUST route through the existing `redaction/egress.py` egress filter. The sub-agent loop reuses the same `_pii_safe_request()` wrapper as the parent. Privacy invariant preserved: real PII never reaches cloud LLM payloads, including via the `<context_file>` pre-load mechanism.
- **D-22 (Sub-agent runs under parent user's JWT):** Sub-agent inherits the parent's auth context — same `token`, same `user_id`, same RLS scope. Workspace sharing is automatic. NO privilege escalation: a sub-agent cannot access another user's data.
- **D-23 (Audit logging):** `task` and `ask_user` tool calls log via `audit_service.log_action(...)` with `resource_type='agent_runs'`, `resource_id=thread_id`. Sub-agent tool calls inside the inner loop ALSO log (they appear as parent's audit entries with the same user_id; no separate sub-agent identity).

### Frontend (Status, Sub-Agent Panel, Question Rendering)

- **D-24 (`useChatState` extensions):**
  - New slice: `agentStatus: 'working'|'waiting_for_user'|'complete'|'error'|null` (null = no active run).
  - New slice: `tasks: Record<task_id, TaskState>` where `TaskState = { description, contextFiles, toolCalls: ToolCallEvent[], status: 'running'|'complete'|'error', result?: string, error?: ErrorObj }`.
  - New action types: `AGENT_STATUS_UPDATED`, `TASK_START`, `TASK_TOOL_START`, `TASK_TOOL_RESULT`, `TASK_COMPLETE`, `TASK_ERROR`.

- **D-25 (Sub-Agent Panel — reuse SubAgentPanel.tsx pattern):** New top-level panel `frontend/src/components/chat/TaskPanel.tsx` (or extend the existing `SubAgentPanel.tsx` if the v1.0 multi-agent panel pattern fits cleanly — plan-phase decides). Renders a card per `task_id`: description, context_files chips, nested tool calls (indented), running spinner / complete checkmark / error icon. Tests in `TaskPanel.test.tsx` (Vitest 3.2 pattern from v1.2 D-P16-02).
  - **Visibility rule:** panel renders whenever `tasks` slice has entries for the current thread. Decoupled from Deep Mode toggle (matches Phase 18 Workspace Panel D-12 visibility rule).
  - **Glass rule (CLAUDE.md):** persistent panel — NO `backdrop-blur`. Solid `bg-card` / `bg-zinc-900`.

- **D-26 (Header status chip):** New component `frontend/src/components/chat/AgentStatusChip.tsx`. Reads `agentStatus` from `useChatState`. Visual:
  - `working` → zinc-100 bg, purple-400 dot pulsing, "Agent working"
  - `waiting_for_user` → purple-100 bg, purple-600 question-mark icon, "Agent waiting for your reply"
  - `complete` → green-100 bg, green-600 check, "Complete" (auto-fade after 3s)
  - `error` → red-100 bg, red-600 alert, "Error — retry?"
  - Rendered in `AppLayout.tsx` chat header slot (not in MessageView).
  - i18n: ID + EN strings via `I18nProvider`.

- **D-27 (Question-as-bubble in MessageView):** Extend `MessageView.tsx` to detect `tool_calls` containing an `ask_user` invocation without a matching tool_result; render that as a special "question bubble" (distinct icon, border-left accent). The user's reply (next message) renders normally — the linkage is invisible to the user but tracked server-side via the `agent_runs` resume detection.

### Tool Schema & Registration

- **D-28 (`task` tool schema):**
  ```python
  {
      "name": "task",
      "description": "Delegate focused work to a sub-agent with isolated context. The sub-agent shares the workspace (read+write) but has its own message history and tool list (cannot recursively call task, write_todos, read_todos). Returns the sub-agent's last assistant message text. Use for: scoped research, single-pass analysis, or when isolating context would clarify the work. context_files pre-loads file contents into the sub-agent's first message — pass file paths the sub-agent should already know about. Failures return as structured tool errors; the parent loop continues.",
      "parameters": {
          "type": "object",
          "properties": {
              "description": {"type": "string", "description": "What the sub-agent should do (clear, complete instruction)."},
              "context_files": {"type": "array", "items": {"type": "string"}, "description": "Workspace file paths to pre-load into the sub-agent's first message. Optional. Each file ≤ 1 MB; total ≤ 5 MB. Binary files cannot be inlined — use list_files/read_file inside the sub-agent."}
          },
          "required": ["description"]
      }
  }
  ```

- **D-29 (`ask_user` tool schema):**
  ```python
  {
      "name": "ask_user",
      "description": "Pause execution to ask the user a clarifying question. The loop pauses; the user's next message is delivered as this tool's result. Use ONLY when you genuinely need user clarification to proceed — do not use for status updates or rhetorical pauses. The user's reply is passed through verbatim; if it doesn't directly answer the question, you may call ask_user again or proceed with what they said.",
      "parameters": {
          "type": "object",
          "properties": {
              "question": {"type": "string", "description": "The question to ask the user. Be specific and actionable."}
          },
          "required": ["question"]
      }
  }
  ```

- **D-30 (Tool registry integration):** Both tools register through the unified `ToolRegistry` (Phase 13 D-P13-01) with `source="native"`, `loading="immediate"`. They appear in `deep_tools` only when `settings.sub_agent_enabled and settings.deep_mode_enabled`. They are NEVER registered for the standard tool-calling loop (non-deep-mode requests). Adapter-wrap invariant — no edits to `tool_service.py` lines 1-1283.

### Plan Structure (Planner Anchor)

- **D-31 (Suggested atomic plan breakdown for `gsd-plan-phase`):**
  1. **19-01** Migration `040_agent_runs.sql` + `messages.parent_task_id` ALTER — table, RLS, indexes, partial unique constraint, `handle_updated_at` trigger reuse. (TASK-04 / ASK-04 / STATUS-05 / MIG bundling)
  2. **19-02** `agent_runs_service.py` — CRUD helpers (start_run, transition_status, set_pending_question, complete, error), resume detection (`get_active_run(thread_id)`), tests against test Supabase.
  3. **19-03** `sub_agent_loop.py` (NEW) — extracted inner loop generator that mirrors `run_deep_mode_loop` minus `task`/`write_todos`/`read_todos`, capped at MAX_SUB_AGENT_ROUNDS=15, summary fallback at cap (D-11), structured-error wrapper (D-12). Reuses egress filter, audit logging, redaction registry.
  4. **19-04** `task` tool implementation in `tool_service.py` — wires `sub_agent_loop`, validates context_files via `workspace_service.validate_workspace_path` + `read_file` for content pre-load, emits `task_start`/`task_complete`/`task_error` SSE through callback queue (mirrors sandbox SSE queue pattern from chat.py L455+).
  5. **19-05** `ask_user` tool implementation + resume-detection branch in `chat.py` `stream_chat` entry — pause-and-yield logic, agent_runs persistence, SSE event emission, `done` yield + return.
  6. **19-06** `agent_status` SSE event emission throughout `run_deep_mode_loop` — working at start, waiting_for_user before ask_user yield, complete on final assistant text, error on uncaught exception. Append-only error contract integration (D-18..D-20).
  7. **19-07** Frontend: `useChatState` slice extensions (D-24) + `AgentStatusChip.tsx` (D-26) + `TaskPanel.tsx` (D-25) + question-bubble rendering in `MessageView.tsx` (D-27) + i18n strings (ID + EN).
  8. **19-08** Deep-mode system prompt update — replace the Phase 17 sub-agent and ask-user STUBS in `deep_mode_prompt.py` with real guidance (when to call task, when to call ask_user, how errors work, no-retry rule). Tests assert the deterministic-string property still holds.
  9. **19-09** End-to-end pytest covering: task tool happy path (sub-agent runs and returns), task with context_files pre-load, sub-agent failure isolation (TASK-05), ask_user pause-and-resume via REST flow, RLS isolation on agent_runs, sub-agent inherits parent JWT (workspace sharing), status indicator transitions, append-only error roundtrip (LLM sees tool error and recovers without retry helper code).
  10. **19-10** Frontend Vitest: `TaskPanel.test.tsx`, `AgentStatusChip.test.tsx`, `MessageView` question-bubble variant.

  - **Order:** 19-01 → 19-02 → (19-03 ‖ 19-07-frontend-skeleton) → 19-04 → 19-05 → 19-06 → 19-08 → (19-09 ‖ 19-10).
  - Plan-phase confirms wave layout. Plans 19-03 (sub-agent loop) and 19-07 frontend skeleton are independent of each other after 19-02 (service layer) lands.

### Testing Strategy

- **D-32 (TDD-first per CLAUDE.md):** Each plan writes a failing test first. Layers:
  - Migration: applied schema matches expected columns, partial unique constraint, RLS policies (Supabase migration verification).
  - Service-level unit: `agent_runs_service` CRUD, resume-detection lookup, status transitions; `sub_agent_loop` happy path + cap fallback + failure isolation.
  - Tool dispatch: `tests/tool/test_task_tool.py` and `tests/tool/test_ask_user_tool.py` with mocked Supabase + real validators + a stub LLM that returns deterministic tool calls.
  - Router integration: `POST /chat` deep-mode + sub-agent flow, ask_user pause/resume two-request sequence (first request emits ask_user + closes; second request resumes with tool result), RLS isolation between two users on `agent_runs`.
  - Frontend Vitest: status chip variants, TaskPanel rendering states (running, complete, error, with nested tool calls), question-bubble in MessageView.
  - Byte-identical fallback: `SUB_AGENT_ENABLED=False` → tools not registered, resume detection short-circuits, no agent_runs writes occur, no task_*/agent_status SSE events emitted.
  - Privacy: write a file containing PII via parent agent, call `task` with `context_files=['file.md']`, capture LLM-bound payload to the sub-agent's first user message, assert PII has been anonymized by the egress filter (mirrors Phase 18 D-15 invariant test).

- **D-33 (Hooks-driven CI):** Existing PostToolUse hook runs pytest on `.py` edits and ESLint+tsc on `.ts/.tsx` edits — relied on for fast feedback. No new CI infrastructure.

### Atomic Commits

- **D-34 (One commit per plan, migration ships first):** Per CLAUDE.md Git Workflow rule. `040_agent_runs.sql` lands in plan 19-01 BEFORE any code that depends on it (19-02..N). After commit, operator runs `supabase db push` against the production project (`qedhulpfezucnfadlfiz`). PreToolUse hook will then block edits to migration 040.

### Claude's Discretion

- **Sub-agent `ask_user` permission:** Whether to forbid sub-agents from calling `ask_user` (cleaner v1.3 surface) or allow it (matches PRD's tool-inheritance default minus `task`/`write_todos`/`read_todos`). Plan-phase decides; default: **allow**, with a strong tool-description nudge ("sub-agents should rarely need to ask the user; complete the task or surface a question via the final assistant message").
- **Reuse `SubAgentPanel.tsx` vs new `TaskPanel.tsx`:** the v1.0 panel was for the multi-agent classifier (one agent per turn). The new `task` tool can spawn N sub-agents per round, each with nested tool calls. Plan-phase confirms whether the existing panel can be extended cleanly or a new one is warranted.
- **Exact `agent_status` chip wording + i18n labels:** Plan-phase / executor finalizes ID + EN strings. Constraint: short (chip-fit), unambiguous, friendly tone consistent with existing chat strings.
- **`task_id` UUID generation site:** server-side (in `task` tool dispatcher) or LLM-controlled (passed in tool call). Plan-phase chooses; default: server-side (LLM has no need to control the ID).
- **Auto-fade duration for `complete` chip:** 3 seconds (default suggestion); plan-phase or design-review can revise.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Primary PRD & Roadmap
- `docs/PRD-Agent-Harness.md` §Feature 1.4 (lines 118–137) — Sub-agent delegation, task tool definition, tool inheritance rules, shared workspace, result propagation, failure isolation.
- `docs/PRD-Agent-Harness.md` §Feature 1.5 (lines 142–151) — Ask user mechanics, four-step pause/resume sequence.
- `docs/PRD-Agent-Harness.md` §Feature 1.6 (lines 153–161) — Status indicators, append-only errors, LLM-driven recovery, sub-agent failure isolation, loop exhaustion, interruption safety.
- `docs/PRD-Agent-Harness.md` §Feature 1.7 (lines 162–172) — Session persistence model.
- `docs/PRD-Agent-Harness.md` §Tool surface (lines 432–438) — official tool name table.
- `docs/PRD-Agent-Harness.md` §MAX_SUB_AGENT_ROUNDS (line 465) — confirms 15 default.
- `.planning/ROADMAP.md` §Phase 19 — Goal, depends_on (Phase 17, Phase 18), requirements (TASK-01..07, ASK-01..04, STATUS-01..06), Success Criteria (5 items).
- `.planning/REQUIREMENTS.md` §"TASK-*", §"ASK-*", §"STATUS-*" (lines 50–72) — full requirement text for Phase 19's 17 reqs.
- `.planning/PROJECT.md` §"Current Milestone: v1.3", §"Key Decisions" — invariants and prior milestone decisions still in force.
- `.planning/STATE.md` §"Roadmap Snapshot (v1.3)", §"v1.3 contract / invariants" — wave structure, no auto retries, no frontend loop, raw SDK only.

### Phase 17 (deep-mode foundation) — direct ancestor
- `.planning/phases/17-deep-mode-foundation-planning-todos-plan-panel/17-CONTEXT.md` — D-08 hand-coded loop, D-09 extended system prompt assembly, D-12 loop-cap fallback (Phase 19 D-11 mirrors this for sub-agents), D-14 env-driven loop caps (`MAX_SUB_AGENT_ROUNDS=15` already lives in `config.py:165`), D-16 dark-launch flag pattern, D-17 SSE event format precedent, D-31 tool registry adapter-wrap invariant, D-32 egress filter coverage (extended to sub-agents in Phase 19 D-21), D-37/D-38 atomic-commits + migration discipline.
- `backend/app/services/deep_mode_prompt.py` — Phase 17 STUBS for sub-agent and ask-user (lines 28–36); Phase 19 plan 19-08 REPLACES these with real guidance.
- `backend/app/routers/chat.py` lines 1545–~1900 — `run_deep_mode_loop` async generator; Phase 19 wraps the inner loop, adds resume-detection at entry, emits `agent_status` and `task_*` events.
- `backend/app/config.py` lines 159–172 — `max_sub_agent_rounds: int = 15`, `deep_mode_enabled` precedent (Phase 19 adds `sub_agent_enabled`).

### Phase 18 (workspace) — sub-agents share via RLS
- `.planning/phases/18-workspace-virtual-filesystem/18-CONTEXT.md` — D-03 RLS thread-ownership pattern (Phase 19 `agent_runs` mirrors), D-05 path validator (reused by `task` context_files), D-06 1 MB cap (matched by Phase 19 D-08), D-07 tool registry adapter-wrap, D-15 privacy invariant test pattern.
- `backend/app/services/workspace_service.py` — `validate_workspace_path`, `read_file` (used by `task` to load context_files content), `WorkspaceService.list_files`. Sub-agent inherits these tools as-is.

### Codebase patterns to mirror
- `backend/app/routers/chat.py` lines 373–700, 1208–1416 — existing tool-calling loop pattern; structured tool-error result handling; per-round persistence with `tool_calls` JSONB; SSE event ordering and the executor-emitted-event queue-drain pattern (chat.py:455+) — Phase 19 reuses for sub-agent SSE forwarding.
- `backend/app/services/tool_service.py` — tool dispatch, `execute_tool()` signature, RLS-scoped token plumbing.
- `backend/app/services/tool_registry.py` (v1.2) — `ToolRegistry.register()` adapter-wrap invariant for the new `task` and `ask_user` tools.
- `backend/app/services/agent_service.py` — v1.0 multi-agent classifier (research/data_analyst/general/explorer); UNCHANGED by Phase 19, coexists.
- `backend/app/services/redaction/egress.py` — egress filter wrapper used by the deep-mode branch (Phase 19 sub-agent loop reuses identically).
- `backend/app/services/audit_service.py` — `log_action(...)` helper for `task` / `ask_user` audit (D-23).
- `backend/app/services/agent_todos_service.py` — Phase 17 service-layer pattern for `agent_runs_service.py` to mirror.

### Frontend patterns to mirror
- `frontend/src/components/chat/SubAgentPanel.tsx` — v1.0 multi-agent panel; pattern reference (and possibly extension target — D-25 discretion item) for Phase 19 `TaskPanel.tsx`.
- `frontend/src/components/chat/CodeExecutionPanel.tsx` — collapsible panel + signed-URL download + glass-rule compliance pattern.
- `frontend/src/components/chat/PlanPanel.tsx` (Phase 17) — sidebar slot, reducer integration, history reconstruction; same wiring approach for Task Panel.
- `frontend/src/components/chat/WorkspacePanel.tsx` (Phase 18) — visibility-rule pattern (panel renders when slice has entries).
- `frontend/src/components/chat/MessageView.tsx` — assistant message rendering; Phase 19 D-27 extends with question-bubble variant.
- `frontend/src/components/chat/AppLayout.tsx` — chat header slot for `AgentStatusChip` (D-26).
- `frontend/src/hooks/useChatState.{ts,tsx}` — reducer + slice patterns; Phase 19 D-24 adds `agentStatus` and `tasks` slices.
- `frontend/src/i18n/` — Indonesian + English label conventions.
- `frontend/src/components/chat/CodeExecutionPanel.test.tsx` — Vitest 3.2 component test precedent (v1.2 D-P16-02).

### Migration reference
- `supabase/migrations/038_agent_todos_and_deep_mode.sql` — Phase 17's table-with-RLS migration (closest analog template).
- `supabase/migrations/039_workspace_files.sql` — Phase 18's table+bucket migration (most recent pattern).
- `supabase/migrations/036_code_executions_and_sandbox_outputs.sql` — partial unique constraint precedent / RLS pattern.
- `supabase/migrations/001_initial_schema.sql` lines 7–80 — `threads` and `messages` tables; FK targets for `agent_runs.thread_id` and the `messages.parent_task_id` ALTER (D-03, D-10).

### Project conventions
- `CLAUDE.md` — TDD rule, atomic commits via `gsd-sdk query commit`, RLS on every new table, no LangChain/LangGraph, Pydantic for structured LLM outputs, base-ui `asChild` shim conventions, glass-only-on-overlays rule, form duplication for mobile/desktop, `/create-migration` skill for next sequential migration.
- `.planning/codebase/STACK.md`, `STRUCTURE.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `TESTING.md`, `INTEGRATIONS.md`, `CONCERNS.md` — codebase living docs.

### Prior milestone artifacts (decisions still in force)
- `.planning/milestones/v1.0-ROADMAP.md`, `v1.0-REQUIREMENTS.md` — privacy invariant, egress filter coverage, audit log convention, async-lock D-31 deferral.
- `.planning/milestones/v1.1-ROADMAP.md`, `v1.1-REQUIREMENTS.md` — code execution sandbox, `tool_calls` JSONB persistence pattern.
- `.planning/milestones/v1.2-ROADMAP.md`, `v1.2-REQUIREMENTS.md` — `ToolRegistry` adapter-wrap invariant, `tool_search` meta-tool, MCP integration, Vitest 3.2 frontend tests.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`run_deep_mode_loop`** (`chat.py:1545+`) — battle-tested pattern for deep-mode entry; Phase 19 wraps with resume-detection and emits `agent_status` events without restructuring the inner loop. The sub-agent loop (`sub_agent_loop.py`) is a near-clone with reduced tool list and lower round cap.
- **`tool_registry.register()`** (`tool_service.py` initialization) — `task` and `ask_user` register here when the feature flag is on. First-write-wins prevents accidental shadowing.
- **`get_supabase_authed_client(token)`** — `agent_runs_service` and resume-detection branch reuse identically for RLS-scoped queries.
- **PII redaction egress filter** (`backend/app/services/redaction/egress.py`) — already wraps every LLM payload in `run_deep_mode_loop`; sub-agent loop reuses the same wrapper. Privacy invariant covered with zero new code.
- **Audit logging** (`audit_service.log_action(...)`) — used for `task` / `ask_user` tool audit (D-23) without changes to audit service.
- **System-prompt assembly** (`build_deep_mode_system_prompt` in `deep_mode_prompt.py`) — Phase 19 plan 19-08 SWAPS the stub strings for real guidance; the function signature is unchanged (KV-cache stable).
- **Per-round persistence** in chat.py — already commits messages + tool_calls JSONB after each round; Phase 19 piggybacks on this for STATUS-05 (loop-iteration-state persisted to DB after each round, reconnection-safe).
- **Executor-emitted SSE event queue** (`chat.py:455+`) — sandbox emits via callback into a queue, chat-loop drains between events. Phase 19's sub-agent SSE forwarding reuses the same queue/drain pattern.
- **`handle_updated_at` trigger** — defined in `001_initial_schema.sql`; reused by `agent_runs` migration without redefinition.
- **Vitest 3.2** — frontend test framework bootstrapped in v1.2; `TaskPanel.test.tsx` and `AgentStatusChip.test.tsx` follow `CodeExecutionPanel.test.tsx` co-located convention.
- **`useChatState` reducer** — already accumulates SSE events into slices; Phase 19 adds `agentStatus` and `tasks` slices following the same pattern (no architectural change).
- **`PlanPanel.tsx` / `WorkspacePanel.tsx`** — closest analogs for `TaskPanel.tsx` (sidebar slot, history reconstruction, visibility rule).
- **Phase 17 `agent_todos_service.py`** — service-layer template for `agent_runs_service.py`.
- **Existing structured tool-error pattern** — workspace tools (Phase 18 D-05) already return `{"error": "...", "code": "..."}` instead of raising; Phase 19 D-18 extends the same pattern across all loop boundaries.

### Established Patterns
- **Numbered sequential migrations:** Next is `040`. PreToolUse hook blocks edits to applied migrations 001-037; Phase 17 (038) and Phase 18 (039) are now also blocked. 040 is unblocked.
- **Feature flags via Pydantic Settings:** `TOOL_REGISTRY_ENABLED`, `SANDBOX_ENABLED`, `WORKSPACE_ENABLED`, `DEEP_MODE_ENABLED` — `SUB_AGENT_ENABLED` follows. Default `False` for v1.3 dark launch.
- **SSE event format:** `data: {"type": "<event_name>", ...}\n\n`; `task_start` / `task_complete` / `task_error` / `agent_status` follow.
- **Atomic per-plan commits:** Each PLAN.md = one `gsd-sdk query commit` invocation.
- **Pydantic structured output:** Tool schemas validated via Pydantic before reaching the LLM dispatcher.
- **Form duplication rule (CLAUDE.md):** N/A for Phase 19 (no form fields added).
- **Glass / panel rule (CLAUDE.md):** TaskPanel + AgentStatusChip are persistent surfaces — NO `backdrop-blur`. Solid panel surface only.
- **Indonesian-default i18n:** All status chip labels and panel labels routed through `I18nProvider`; supply ID + EN strings.
- **Tool-result structured errors (NOT exceptions):** D-18 codifies and extends Phase 18's pattern across the entire loop boundary.

### Integration Points
- **`backend/app/routers/chat.py`:**
  - `stream_chat` entry: add resume-detection branch (D-04) before existing deep-mode dispatch.
  - `run_deep_mode_loop`: emit `agent_status` events at start / before ask_user / on complete / on error (D-16).
  - `run_deep_mode_loop`: detect `task` tool calls in tool-dispatch and route to `sub_agent_loop`; forward sub-agent SSE events through the parent's generator with `task_id` tagging (D-06).
  - `run_deep_mode_loop`: detect `ask_user` tool calls; persist `agent_runs.status='waiting_for_user'`, emit `ask_user` SSE event, yield `done`, return.
- **`backend/app/services/sub_agent_loop.py`:** NEW file. Inner async generator that mirrors `run_deep_mode_loop` minus `task`/`write_todos`/`read_todos`, capped at MAX_SUB_AGENT_ROUNDS=15 with summary fallback at cap.
- **`backend/app/services/agent_runs_service.py`:** NEW file. CRUD helpers + resume detection.
- **`backend/app/services/tool_service.py`:** register `task` and `ask_user` via the unified registry's adapter wrap (NO edits to lines 1-1283; v1.2 D-P13-01 invariant).
- **`backend/app/services/deep_mode_prompt.py`:** plan 19-08 replaces the Phase 17 stubs (lines 28–36) with real guidance.
- **`backend/app/config.py`:** add `sub_agent_enabled: bool = False` Pydantic Settings field.
- **`frontend/src/components/chat/AgentStatusChip.tsx`:** NEW component; rendered in chat header (`AppLayout.tsx`).
- **`frontend/src/components/chat/TaskPanel.tsx`:** NEW component (or extension of `SubAgentPanel.tsx` — plan-phase decides per D-25).
- **`frontend/src/components/chat/MessageView.tsx`:** add question-bubble variant (D-27).
- **`frontend/src/hooks/useChatState.{ts,tsx}`:** add `agentStatus` and `tasks` slices + reducer cases (D-24).
- **`frontend/src/i18n/`:** add status chip + Task Panel + question-bubble strings (ID + EN).
- **`supabase/migrations/040_agent_runs.sql`:** NEW migration — `agent_runs` table + RLS + partial unique index + `messages.parent_task_id` ALTER (D-03, D-10).

</code_context>

<specifics>
## Specific Ideas

- **Migration 040 file name:** `supabase/migrations/040_agent_runs.sql` — bundles the `agent_runs` table + `messages.parent_task_id` ALTER in one file (one migration per phase, mirrors Phase 17's bundled 038).
- **`SUB_AGENT_ENABLED=False` default:** Dark launch convention (matches v1.2 `TOOL_REGISTRY_ENABLED`, `SANDBOX_ENABLED`, Phase 17 `DEEP_MODE_ENABLED`, Phase 18 `WORKSPACE_ENABLED`).
- **Resume detection at the very top of `stream_chat`:** before deep-mode dispatch, before any history load — fastest short-circuit when there's no active run.
- **Header chip wording suggestions (plan-phase finalizes ID + EN):**
  - EN: "Agent working" / "Agent waiting for your reply" / "Complete" / "Error — retry?"
  - ID: "Agen sedang bekerja" / "Agen menunggu balasan Anda" / "Selesai" / "Error — ulangi?"
- **`?` icon for question bubble:** `MessageCircleQuestion` from lucide-react (already in dependency tree from existing chat surfaces).
- **`task_id` UUID generation:** server-side, generated at `task` tool dispatch (LLM has no need to control it).
- **Sub-agent context_file inline format:** `<context_file path="...">CONTENT</context_file>` XML-ish wrapping. Sub-agent's system prompt instructs it to treat `<context_file>` blocks as workspace content that's already loaded.
- **Combined-files cap:** 5 MB across all `context_files` in a single `task` call (1 MB per file already from Phase 18 D-06); plan-phase confirms exact number.
- **Auto-fade duration for `complete` chip:** 3 seconds.
- **`agent_runs` history preservation:** Completed/error rows are NOT deleted — they accumulate per thread. Useful for admin auditing and post-hoc replay. The partial unique index ensures only ONE active run per thread at any time.

</specifics>

<deferred>
## Deferred Ideas

(All ideas surfaced during analysis are in-scope for Phase 19 or already explicitly deferred to later phases by the v1.3 ROADMAP.)

- **Harness engine, gatekeeper LLM, post-harness LLM, file upload, locked Plan Panel variant** — Phase 20.
- **Batched parallel sub-agents (`llm_batch_agents`), human-in-the-loop (`llm_human_input`)** — Phase 21.
- **Contract Review domain harness, DOCX deliverable** — Phase 22.
- **Forbid sub-agent `ask_user` calls** — Claude's discretion item; default = allow with strong tool-description nudge. Plan-phase / executor decides.
- **Reuse `SubAgentPanel.tsx` vs new `TaskPanel.tsx`** — Claude's discretion item; plan-phase decides per code-shape.
- **Cross-process advisory lock for ask_user resume race conditions** — same async-lock D-31 carryover from v1.0; deferred. Risk: two simultaneous `/chat` POSTs after a pause could both transition `agent_runs.status='working'`. Mitigation: partial unique index + transactional UPDATE WHERE status='waiting_for_user' is sufficient for v1.3 single-worker; multi-worker hardening deferred.
- **Auto-resume from `error` state** — explicitly out of scope per success criterion #5 (LLM-driven recovery only); errored runs stay errored until the user re-engages.
- **Mid-flight SSE reconnection with automatic loop resumption** — Phase 17 PRD-flagged post-MVP; Phase 19 inherits this stance. Mid-stream interrupt = lose in-progress round, persisted state = recoverable on follow-up.
- **Per-user `SUB_AGENT_ENABLED` preference** — env-var only in v1.3; per-user surface deferred to Phase 20's broader admin-settings work.
- **Sub-agent observability deepening:** separate LangSmith trace tree, per-sub-agent token accounting, sub-agent retry budget — beyond Phase 19's MVP scope.
- **`delete_run` admin endpoint** — `agent_runs` rows accumulate; cleanup via SQL or a post-MVP admin tool.

### Reviewed Todos (not folded)

(No pre-existing `.planning/todos/` matches surfaced by the discuss-phase scout. Phase 19 scope is clean from the v1.3 ROADMAP.)

</deferred>

---

*Phase: 19-sub-agent-delegation-ask-user-status-recovery*
*Context gathered: 2026-05-03*
