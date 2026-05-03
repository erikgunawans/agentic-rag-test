# Phase 19: Sub-Agent Delegation + Ask User + Status & Recovery - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 19-sub-agent-delegation-ask-user-status-recovery
**Areas discussed:** ask_user pause/resume protocol, Sub-agent SSE event taxonomy & nesting, task context_files semantics, Resume-after-pause UX

---

## ask_user pause/resume protocol

### Q1: Which pause/resume protocol fits your vision for ask_user?

| Option | Description | Selected |
|--------|-------------|----------|
| Close-and-resume | When LLM calls ask_user: backend persists pending state to `agent_runs` table, emits `ask_user` SSE event with `agent_status='waiting_for_user'`, then closes the SSE stream cleanly. Frontend renders the question. User types answer in normal input. POST /chat detects pending run and routes the body as the `ask_user` tool result; backend rebuilds loop_messages from history + injects answer, continues from recorded last_round_index. Matches FastAPI's request-scoped model, survives client disconnects. | ✓ |
| Hold-the-stream-open (long-poll) | SSE stream stays open. Backend awaits an asyncio.Event tied to thread_id; user's POST to a separate endpoint sets the event with the answer. Simpler mental model but long-held connections may be killed by Railway proxy and asyncio events are process-local. | |
| Hybrid: dedicated answer endpoint | Stream closes after ask_user event; user's reply goes to a dedicated POST /threads/{id}/agent_answer endpoint that re-opens an SSE stream with the resumed loop. Two frontend code paths; more API surface. | |

**User's choice:** Close-and-resume (Recommended)
**Notes:** Matches the v1.0–v1.2 idiom and survives client reloads. Mirrors Phase 17's mid-flight interrupt pattern (committed state + follow-up to resume).

### Q2: Where should the paused-loop state be persisted?

| Option | Description | Selected |
|--------|-------------|----------|
| New agent_runs table | Migration 040 creates `agent_runs` (id, thread_id, user_id, status enum, pending_question, last_round_index, error_detail, timestamps), partial UNIQUE active row per thread, RLS thread-scoped. Foundation that Phase 20 harness_runs can mirror. One more migration. | ✓ |
| ALTER threads table | Add columns to threads (agent_status, pending_ask JSONB, paused_at). Simpler but pollutes a heavy table; harder to extend; less typed. | |
| Encode as a special message row | Store pending ask_user as a tool_call without a tool_result yet; loop detects 'orphan tool_call' on resume. Zero schema changes but slow/complex queries; conflates 'in-flight tool call' with 'paused-for-user-input'. | |

**User's choice:** New agent_runs table (Recommended)
**Notes:** Migration 040 (sequential after 038/039). Partial unique index ensures at most one active run per thread; completed/error rows accumulate as history.

---

## Sub-agent SSE event taxonomy & nesting

### Q1: What should the sub-agent SSE events be named?

| Option | Description | Selected |
|--------|-------------|----------|
| task_start / task_complete | Mirrors the LLM tool name exactly. Frontend reducer dispatches on event.type === 'task_start'. Zero collision with the existing 'agent_start' event from the v1.0 multi-agent classifier. Self-documenting. | ✓ |
| sub_agent_start / sub_agent_complete | Uses 'sub_agent' terminology (matches PRD body). Introduces a third agent-related event family alongside `agent_start` and Phase 20's `harness_phase_start` — more vocabulary to learn. | |
| Reuse agent_start | Reuse the existing event name with a task_id discriminator. Heavy backward-compat risk; UI logic that handles `agent_start` would also fire on every sub-agent spawn. | |

**User's choice:** task_start / task_complete (Recommended)

### Q2: Do sub-agent's INTERNAL tool calls bubble up?

| Option | Description | Selected |
|--------|-------------|----------|
| Bubble up tagged with task_id | Sub-agent's tool_start / tool_result events forward through the parent's SSE stream with an added task_id field. Frontend reducer indents them under the sub-agent panel. Matches PRD's 'nested sub-agent UI rendering' language. | ✓ |
| Hide internals | Parent only sees task_start (description) and task_complete (final result). Less SSE bandwidth but zero visibility into sub-agent activity. | |
| Stream sub-agent assistant deltas only | Emit task_start, task_assistant_delta, task_complete. No tool events. Rare middle-ground; users want to see WHICH tools the sub-agent used. | |

**User's choice:** Bubble up, tagged with task_id (Recommended)

---

## task context_files semantics

### Q1: What should context_files do?

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-load CONTENT into sub-agent's first user message | Sub-agent starts with description + appended file contents wrapped in `<context_file path='...'>...</context_file>` tags. Saves at least one round per file. Same path validator + 1 MB cap as Phase 18. Binary files → structured error. Sub-agent retains read_file/list_files for fetching more. | ✓ |
| Hint-only — sub-agent must call read_file | context_files appended as a hint; sub-agent decides what to actually read. Zero token cost upfront but at least one extra round per file (multiplies for batched parallel sub-agents in Phase 21). | |
| Hybrid: pre-load if total < 50KB | Auto-decide based on combined file size. Non-deterministic from the parent agent's perspective; harder to test. | |

**User's choice:** Pre-load CONTENT into sub-agent's first user message (Recommended)
**Notes:** XML-ish `<context_file path="...">...</context_file>` wrapping. 1 MB per file (matches Phase 18 D-06); 5 MB combined cap to protect MAX_SUB_AGENT_ROUNDS context budget.

---

## Resume-after-pause UX

### Q1: What should the chat header + input look like when paused?

| Option | Description | Selected |
|--------|-------------|----------|
| Header chip + question rendered as last assistant turn | Chat header shows status chip 'Agent waiting for your reply'. The ask_user question rendered as the last visible assistant message bubble with a distinct `?` icon. Input box stays normal. Server-side detection routes the next message body as the tool result. | ✓ |
| Dedicated 'Answer agent' input panel + locked normal input | Normal message input disabled; separate panel with question + answer textarea + 'Send answer' button. Visual clarity but more UI surface and two code paths. | |
| Inline answer affordance under the question bubble | Question rendered as last bubble; inline mini-input under it; normal input grayed out. Visually couples answer to question but more component complexity and awkward layout for long answers. | |

**User's choice:** Header chip 'Waiting for you' + question rendered as last assistant turn (Recommended)

### Q2: What if the user types an unrelated message?

| Option | Description | Selected |
|--------|-------------|----------|
| Pass it through verbatim as the tool result | Whatever the user typed becomes the ask_user tool result string. The LLM sees it next round and decides: valid answer / re-ask / course-correct. Matches PRD's LLM-driven recovery principle (success criterion #5). | ✓ |
| Server-side validate then re-prompt | Backend uses a small classifier to detect 'is this an answer to question X'; refuses if no. Extra LLM call per answer; conflicts with LLM-driven-recovery principle. | |
| Cancel the pending ask_user, treat as fresh top-level message | Mark agent_runs.status='cancelled', process as a normal new turn. Hard to detect 'unrelated' reliably; conflicts with PRD ASK-03 (reply must be tool result, not new top-level). | |

**User's choice:** Pass it through verbatim as the tool result (Recommended)

---

## Claude's Discretion (locked as proposed)

User confirmed: "Lock the discretion items as proposed and write CONTEXT.md."

- **Status indicator surface:** Header chip in `AppLayout.tsx` chat slot, color-coded by state (zinc=working, purple=waiting_for_user, green=complete, red=error). Auto-fade complete after 3s.
- **Feature flag:** Single env var `SUB_AGENT_ENABLED` (default `False`, mirrors `WORKSPACE_ENABLED` / `SANDBOX_ENABLED`), gated behind `DEEP_MODE_ENABLED` at the loop entry.
- **Append-only error contract:** Failed tool calls persist as `tool_result` rows with `output={"error": "...", "code": "...", "detail": "..."}` JSON. Stack traces logged server-side (LangSmith + Python logger) but NOT in tool result payload. The LLM sees the structured error and decides recovery.
- **Sub-agent ask_user permission:** default = allow (matches PRD's tool-inheritance default minus task/write_todos/read_todos), with a strong tool-description nudge. Plan-phase / executor may revisit.
- **Reuse SubAgentPanel.tsx vs new TaskPanel.tsx:** plan-phase decides per code-shape.
- **task_id UUID generation site:** server-side, in the `task` tool dispatcher.
- **Auto-fade duration for complete chip:** 3 seconds.

## Deferred Ideas

(All deferrals already captured in CONTEXT.md `<deferred>` section.)

- Harness engine + gatekeeper + post-harness LLM + file upload + locked Plan Panel — Phase 20.
- Batched parallel sub-agents + HIL phase type — Phase 21.
- Contract Review domain harness + DOCX deliverable — Phase 22.
- Cross-process advisory lock for ask_user resume race (D-31 carryover) — post-MVP.
- Auto-resume from error state — explicitly out of scope.
- Mid-flight SSE reconnection with auto-resumption — PRD-flagged post-MVP.
- Per-user SUB_AGENT_ENABLED preference — Phase 20's admin-settings work.
- Deeper sub-agent observability (separate LangSmith trace tree, per-sub-agent token accounting) — post-MVP.
- `delete_run` admin endpoint — post-MVP cleanup tool.
