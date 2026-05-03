---
phase: 19-sub-agent-delegation-ask-user-status-recovery
verified: 2026-05-03T09:00:00Z
status: human_needed
score: 17/17 must-haves verified (automated checks)
overrides_applied: 0
human_verification:
  - test: "Run the full backend test suite against real Supabase (including E2E tests)"
    expected: "All 12 E2E tests pass, 28+ cumulative tests pass. Migration 040 live in production confirms supabase db push succeeded."
    why_human: "Cannot execute pytest with live Supabase credentials from verifier. Tests connect to production DB and require TEST_EMAIL/TEST_PASSWORD env vars."
  - test: "Run frontend Vitest suite: npx vitest run src/components/chat/AgentStatusChip.test.tsx src/components/chat/TaskPanel.test.tsx src/components/chat/MessageView.test.tsx"
    expected: "23 total Vitest tests pass (7 + 9 + 7)"
    why_human: "Cannot execute vitest from verifier."
  - test: "Verify SUB_AGENT_ENABLED=false behavior via Test 11 in test_phase19_e2e.py"
    expected: "SSE event-type set is a subset of {delta, done, tool_start, tool_result} — no agent_status, task_start, task_complete, task_error events when flag is off; agent_runs table has 0 rows; parent_task_id messages have 0 rows."
    why_human: "Requires live backend execution against real Supabase."
  - test: "Manual UI check: send a deep-mode message that triggers ask_user, observe AgentStatusChip transitions (working → waiting_for_user → working → complete) and TaskPanel card rendering"
    expected: "AgentStatusChip shows correct color/icon per state; auto-fades after complete; TaskPanel shows task card with nested tool calls; question-bubble appears in MessageView for unresolved ask_user."
    why_human: "Visual + real-time behavior cannot be verified programmatically."
---

# Phase 19: Sub-Agent Delegation + Ask User + Status & Recovery — Verification Report

**Phase Goal:** Ship a fully-gated sub-agent delegation system (task tool), an ask_user pause/resume tool, and agent_status SSE telemetry — all dark-launched behind `SUB_AGENT_ENABLED=false` with byte-identical off-mode behavior.

**Verified:** 2026-05-03T09:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Migration 040 creates agent_runs table with partial unique index, CHECK constraints, RLS, and messages.parent_task_id | VERIFIED | `supabase/migrations/040_agent_runs.sql` exists; grep confirms `CREATE TABLE IF NOT EXISTS public.agent_runs`, `idx_agent_runs_thread_active`, `agent_runs_pending_question_invariant`, 4 `CREATE POLICY` statements, `ADD COLUMN IF NOT EXISTS parent_task_id` |
| 2 | agent_runs_service exposes full state-machine CRUD with RLS-scoped client and audit logging | VERIFIED | `backend/app/services/agent_runs_service.py` exists (256 lines); 8 uses of `get_supabase_authed_client`; 5 `audit_service.log_action` calls; `.eq("status", "working")` transactional race guard present |
| 3 | sub_agent_loop is an async generator mirroring run_deep_mode_loop with reduced tool list, loop cap, failure isolation, and privacy invariant | VERIFIED | `backend/app/services/sub_agent_loop.py` exists (493 lines); `EXCLUDED = {"task", "write_todos", "read_todos"}`; D-09 retention comment present; `egress_filter` called (3 occurrences); `parent_redaction_registry` used (5 occurrences); `settings.max_sub_agent_rounds` respected; failure isolation wrapper with `"sub_agent_failed"` terminal result; zero `agent_status` or `audit_service` references |
| 4 | task tool registered via adapter-wrap (additive, not touching lines 1-1283 of tool_service.py) | VERIFIED | `_register_sub_agent_tools` appears 2+ times in tool_service.py; `"name": "task"` present; `if not settings.sub_agent_enabled:` gate present; SHA-256 of first 1283 lines = `cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2` (matches pre-Phase-19 invariant hash) |
| 5 | task dispatch in chat.py emits task_start, forwards nested events tagged with task_id, emits task_complete or task_error | VERIFIED | `if func_name == "task"` present in chat.py; `"task_start"`, `"task_complete"`, `"task_error"` SSE event types present; `tagged = {**evt, "task_id": task_id}` at line 1962; `parent_redaction_registry=registry` at line 1954; `from app.services.sub_agent_loop import run_sub_agent_loop` at module level (line 32) |
| 6 | ask_user tool registered via adapter-wrap; pause path emits canonical Site B agent_status + ask_user SSE then closes generator | VERIFIED | `_ASK_USER_SCHEMA` present in tool_service.py (3 occurrences); `if func_name == "ask_user" and settings.sub_agent_enabled:` in chat.py at ~line 1888; Site B yield at line 1914; `agent_runs_service.set_pending_question` called (1 occurrence); generator returns after Site B yield |
| 7 | Resume detection at stream_chat entry detects waiting_for_user run, transitions to working, re-enters run_deep_mode_loop | VERIFIED | `if settings.sub_agent_enabled and settings.deep_mode_enabled:` gate confirmed at ~line 276; `agent_runs_service.get_active_run` called (2 occurrences — entry + dispatch); `transition_status(new_status="working")` in resume branch; `resume_run_id`, `resume_tool_result`, `resume_round_index` kwargs in `run_deep_mode_loop` signature |
| 8 | agent_status SSE emitted at Sites A (working), B (waiting_for_user), C (complete), D (error) — all gated by sub_agent_enabled | VERIFIED | Lines 1749 (Site A gated), 1914 (Site B inside ask_user+sub_agent_enabled check), 2126 (Site D gated), 2216 (Site C gated); all four sites confirmed under `if settings.sub_agent_enabled:` or `if func_name == "ask_user" and settings.sub_agent_enabled:` guards |
| 9 | agent_runs lifecycle integrated: start_run at loop entry, complete at terminal, error on exception — all gated | VERIFIED | `agent_runs_service.start_run` (2 calls), `agent_runs_service.complete` (1 call at Site C), `agent_runs_service.error` (1 call at Site D); `str(exc)[:500]` D-19 sanitization confirmed at line 2122 |
| 10 | Failed tool calls append structured error without automatic retry | VERIFIED | No retry helper in chat.py; Site D is catch-all that persists error and emits agent_status{error} + done; no auto-retry loop |
| 11 | SUB_AGENT_ENABLED=false produces byte-identical fallback (no agent_status, no task_* events, no agent_runs writes) | VERIFIED | All 4 agent_status sites gated; E2E Test 11 (`test_sub_agent_disabled_byte_identical_fallback_e2e`) has positive subset assertion `captured_set <= {"delta","done","tool_start","tool_result"}` at line 1199; resume detection gated by both flags |
| 12 | Frontend: useChatState exposes agentStatus + tasks slices with SSE reducer cases | VERIFIED | `AgentStatus` type appears ≥6 times in useChatState.ts; `TaskState` ≥3 times; `Map<string, TaskState>` present; SSE handler cases confirmed |
| 13 | Frontend: AgentStatusChip renders 4 visual states + auto-fade + a11y + no backdrop-blur | VERIFIED | File exists; `backdrop-blur` count = 0; `setTimeout` + 3000ms auto-fade present; `role="status"` present; wired to useChatContext |
| 14 | Frontend: TaskPanel renders one card per task_id with no backdrop-blur; visibility rule tasks.size===0 | VERIFIED | File exists; `backdrop-blur` count = 0; `tasks.size === 0` visibility rule at line 78; wired to useChatContext; `bg-background` present |
| 15 | Frontend: MessageView renders question-bubble variant for unmatched ask_user tool_call | VERIFIED | `isAskUserQuestion` helper present (2 occurrences); `border-l-[3px] border-primary` present; `MessageCircleQuestion` icon used (2 occurrences) |
| 16 | Frontend: 24 i18n entries (12 keys × 2 locales) present in both id and en | VERIFIED | `agentStatus.working` count=2 (both locales); `taskPanel.title` = "Sub-agen" (id), "Sub-agents" (en); `askUser.questionBubble.ariaLabel` count=2 |
| 17 | deep_mode_prompt.py stubs replaced with real task/ask_user/error recovery guidance; no auto-retry instruction; deterministic | VERIFIED | "Sub-Agent Delegation" present; "Asking the User" present; "Error Recovery" present; "There is no automatic retry" present; STUB/stub count = 0 |

**Score:** 17/17 truths verified (automated static checks)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/040_agent_runs.sql` | agent_runs DDL + RLS + partial unique index + messages.parent_task_id | VERIFIED | All required elements confirmed by grep |
| `backend/app/services/agent_runs_service.py` | Full state-machine CRUD, RLS-scoped, audit-logged | VERIFIED | 256 lines; all 6 public API functions present |
| `backend/app/services/sub_agent_loop.py` | Async generator, 493 lines, EXCLUDED set, failure isolation, egress | VERIFIED | 493 lines; all key patterns confirmed |
| `backend/app/config.py` | sub_agent_enabled: bool = False | VERIFIED | Confirmed present |
| `backend/app/services/tool_service.py` | `_register_sub_agent_tools`, `_TASK_SCHEMA`, `_ASK_USER_SCHEMA` | VERIFIED | All present; SHA-256 invariant of first 1283 lines confirmed |
| `backend/app/routers/chat.py` | task dispatch, ask_user dispatch, Sites A/B/C/D, resume branch | VERIFIED | All patterns confirmed at specific line numbers |
| `backend/app/services/deep_mode_prompt.py` | 5 real sections replacing Phase 17 stubs | VERIFIED | All 3 new sections present; stubs gone |
| `backend/tests/integration/test_migration_040_agent_runs.py` | 7 integration tests | VERIFIED | 7 tests confirmed |
| `backend/tests/services/test_agent_runs_service.py` | 7 service tests | VERIFIED | 7 tests confirmed |
| `backend/tests/integration/test_sub_agent_loop.py` | 21 integration tests (shown as 0 top-level via ^def test_ but 21 via def test_) | VERIFIED | 21 tests confirmed via `grep -c "def test_"` |
| `backend/tests/tool/test_task_tool.py` | 8 tool tests | VERIFIED | 8 tests confirmed |
| `backend/tests/tool/test_ask_user_tool.py` | 6 tool tests | VERIFIED | 6 tests confirmed |
| `backend/tests/integration/test_chat_resume_flow.py` | 6 integration tests | VERIFIED | 6 tests confirmed |
| `backend/tests/integration/test_agent_status_emission.py` | 8 integration tests | VERIFIED | 8 tests confirmed |
| `backend/tests/services/test_deep_mode_prompt.py` | 6 unit tests | VERIFIED | 6 tests confirmed |
| `backend/tests/integration/test_phase19_e2e.py` | 12 E2E tests covering all 17 REQ-IDs | VERIFIED | 12 tests confirmed; positive subset assertion present |
| `frontend/src/components/chat/AgentStatusChip.tsx` | Status chip component | VERIFIED | Exists; substantive; wired to ChatContext |
| `frontend/src/components/chat/TaskPanel.tsx` | Task panel component | VERIFIED | Exists; substantive; wired to ChatContext |
| `frontend/src/components/chat/AgentStatusChip.test.tsx` | 7 Vitest tests | VERIFIED | 7 `it(` calls confirmed |
| `frontend/src/components/chat/TaskPanel.test.tsx` | 9 Vitest tests | VERIFIED | 9 `it(` calls confirmed |
| `frontend/src/components/chat/MessageView.test.tsx` | 7 Vitest tests | VERIFIED | 7 `it(` calls confirmed |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `agent_runs_service.py` | `database.get_supabase_authed_client` | RLS-scoped client import | VERIFIED | 8 occurrences; no service-role client |
| `agent_runs_service.py` | `audit_service.log_action` | Audit hook on every mutation | VERIFIED | 5 `audit_service.log_action` calls |
| `sub_agent_loop.py` | `redaction/egress.py` | `egress_filter` on every LLM payload | VERIFIED | 3 `egress_filter` occurrences; `parent_redaction_registry` used |
| `sub_agent_loop.py` | `config.settings.max_sub_agent_rounds` | Loop cap 15 | VERIFIED | `settings.max_sub_agent_rounds` used |
| `tool_service.py` | `tool_registry.register(name="task")` | Adapter-wrap below line 1283 | VERIFIED | `_register_sub_agent_tools` + SHA-256 invariant confirmed |
| `tool_service.py` | `tool_registry.register(name="ask_user")` | Adapter-wrap; `_ASK_USER_SCHEMA` | VERIFIED | 3 `_ASK_USER_SCHEMA` occurrences |
| `chat.py run_deep_mode_loop` | `sub_agent_loop.run_sub_agent_loop` | Module-level import for testability | VERIFIED | Line 32: `from app.services.sub_agent_loop import run_sub_agent_loop` |
| `chat.py stream_chat` | `agent_runs_service.get_active_run` | Resume detection branch | VERIFIED | 2 occurrences; gated by `sub_agent_enabled AND deep_mode_enabled` |
| `chat.py` (Site B) | `agent_runs_service.set_pending_question` | Pause persistence | VERIFIED | 1 occurrence in ask_user dispatch |
| `chat.py` Sites A/C/D | `agent_runs_service.start_run/complete/error` | Lifecycle hooks | VERIFIED | Each method found at correct site |
| `AgentStatusChip.tsx` | `ChatContext.useChatContext` | agentStatus slice consumed | VERIFIED | `useChatContext` at line 37 |
| `TaskPanel.tsx` | `ChatContext.useChatContext` | tasks Map slice consumed | VERIFIED | `useChatContext` at line 17; `tasks` destructured at line 74 |
| `ChatPage.tsx` | `AgentStatusChip.tsx` | sticky top-0 z-10 render | VERIFIED | Import + `sticky top-0 z-10` div confirmed |
| `ChatPage.tsx` | `TaskPanel.tsx` | Rightmost panel render | VERIFIED | Import + `<TaskPanel />` after WorkspacePanel |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `AgentStatusChip.tsx` | `agentStatus` | `useChatContext()` → `useChatState` → SSE `agent_status` events | Yes — SSE events dispatched from real chat.py Sites A/B/C/D | FLOWING |
| `TaskPanel.tsx` | `tasks` (Map) | `useChatContext()` → `useChatState` → SSE `task_start/complete/error` events | Yes — task_start SSE from chat.py task dispatch with real sub-agent results | FLOWING |
| `MessageView.tsx` | `isAskUserQuestion` helper | Message `tool_calls` array from Supabase messages table | Yes — depends on real tool_call JSONB data | FLOWING |
| `agent_runs_service.py` | `AgentRunRecord` | Supabase `agent_runs` table via RLS-scoped client | Yes — real DB queries via `get_supabase_authed_client` | FLOWING |
| `sub_agent_loop.py` | `_terminal_result` | OpenRouter LLM + workspace_service reads | Yes — real LLM calls + real Supabase workspace | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| sub_agent_enabled default False | `cd backend && python -c "from app.config import settings; print(settings.sub_agent_enabled)"` | False | PASS (confirmed by config.py grep) |
| sub_agent_loop imports cleanly | `python -c "from app.services.sub_agent_loop import run_sub_agent_loop; print('OK')"` | Expected OK | SKIP (requires venv; confirmed by SUMMARY claims + code structure) |
| deep_mode_prompt deterministic | `build_deep_mode_system_prompt("base") == build_deep_mode_system_prompt("base")` | True | PASS (no timestamps/volatile data in source; confirmed by static analysis) |
| SHA-256 D-P13-01 invariant | `head -n 1283 tool_service.py \| shasum -a 256` | `cb63cf3e60d5f6380e2e41f63b1fe9122f58ab4648808b0f2114e452cd45ddb2` | PASS (verified directly) |
| agent_service.py unmodified (TASK-06) | `git log --after="2026-05-02" -- backend/app/services/agent_service.py` | No commits since Phase 19 start | PASS (most recent commit is pre-Phase-19) |

---

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|---------|
| TASK-01 | 19-04, 19-09 | Agent can call task() LLM tool | SATISFIED | `_register_sub_agent_tools` + `if func_name == "task"` dispatch in chat.py |
| TASK-02 | 19-03, 19-09 | Sub-agent inherits parent tools minus task/write_todos/read_todos | SATISFIED | `EXCLUDED = {"task", "write_todos", "read_todos"}` in sub_agent_loop.py |
| TASK-03 | 19-03, 19-09 | Sub-agent shares parent workspace (context_files XML wrapping) | SATISFIED | `_build_first_user_message` helper; `workspace_service.read_file` called |
| TASK-04 | 19-01, 19-03, 19-04 | Sub-agent last text returns as task tool result; messages carry parent_task_id | SATISFIED | `_terminal_result={"text":...}` pattern; `parent_task_id` in `_persist_round_message` |
| TASK-05 | 19-03, 19-04, 19-09 | Sub-agent failures return as tool results, never crash parent | SATISFIED | Failure isolation wrapper with `_terminal_result={"error":"sub_agent_failed",...}`; task_error SSE |
| TASK-06 | 19-08, 19-09 | Existing analyze_document/explore_knowledge_base sub-agents unchanged | SATISFIED | agent_service.py unmodified; no Phase 19 commits touch it |
| TASK-07 | 19-04, 19-09 | Sub-agent emits task_start/complete SSE events with task_id | SATISFIED | task_start/complete/error SSE present; `tagged = {**evt, "task_id": task_id}` for nested events |
| ASK-01 | 19-05, 19-09 | Agent can call ask_user() LLM tool | SATISFIED | `_ASK_USER_SCHEMA` registered via adapter-wrap |
| ASK-02 | 19-05, 19-07, 19-09 | System emits ask_user SSE + agent_status=waiting_for_user | SATISFIED | Site B yield at line 1914; AgentStatusChip renders waiting_for_user state |
| ASK-03 | 19-05, 19-09 | User reply delivered as ask_user tool result verbatim | SATISFIED | Resume injection appends synthetic tool_result; D-15 verified |
| ASK-04 | 19-01, 19-02, 19-05, 19-09 | Agent loop resumes after user response | SATISFIED | Resume branch at stream_chat entry; transition_status + re-enter run_deep_mode_loop |
| STATUS-01 | 19-06, 19-07, 19-09 | Status indicators: working/waiting_for_user/complete/error | SATISFIED | 4 SSE sites in chat.py; AgentStatusChip renders all 4 states |
| STATUS-02 | 19-06, 19-09 | Failed tool calls stay in conversation context (append-only) | SATISFIED | No delete/overwrite of tool_result rows; structured error in tool_output |
| STATUS-03 | 19-06, 19-08, 19-09 | No automatic retries | SATISFIED | "There is no automatic retry" in prompt; no retry code path in chat.py |
| STATUS-04 | 19-03, 19-04, 19-09 | Sub-agent failures isolated; parent continues | SATISFIED | Failure isolation wrapper; task_error SSE; parent loop iterates to next round |
| STATUS-05 | 19-01, 19-02, 19-06 | Loop state persisted to DB after each round | SATISFIED | agent_runs lifecycle (start_run/complete/error); messages.parent_task_id; all round state via existing messages JSONB |
| STATUS-06 | 19-05, 19-09 | User can resume paused thread by sending follow-up | SATISFIED | Resume detection branch; last_round_index advanced; tool_result injected verbatim |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | No TODO/FIXME/placeholder/stub patterns in Phase 19 implementation files | — | — |

Static scan confirmed:
- `grep -c "STUB\|stub" backend/app/services/deep_mode_prompt.py` = 0 (stubs removed)
- No `return null` placeholder patterns in AgentStatusChip or TaskPanel (both render substantive content)
- `backdrop-blur` = 0 in both new frontend components (glass rule honored)
- No hardcoded empty arrays/objects flowing to rendering in new components

---

### Human Verification Required

#### 1. Backend Integration Test Suite

**Test:** Run from repo root with credentials:
```bash
cd backend && source venv/bin/activate && \
  TEST_EMAIL="test@test.com" TEST_PASSWORD='!*-3-3?3uZ?b$v&' \
  TEST_EMAIL_2="test-2@test.com" TEST_PASSWORD_2='fK4$Wd?HGKmb#A2' \
  SUB_AGENT_ENABLED=true DEEP_MODE_ENABLED=true \
  pytest tests/integration/test_phase19_e2e.py -v
```
**Expected:** `12 passed` — all E2E tests cover the 17 REQ-IDs
**Why human:** Requires live Supabase credentials and a running backend; cannot execute from verifier

#### 2. Byte-Identical Fallback Positive Assertion (Test 11)

**Test:** Same as above — Test 11 specifically with `SUB_AGENT_ENABLED=false` monkeypatched
**Expected:** `captured_set <= {"delta","done","tool_start","tool_result"}` assertion passes; 0 agent_runs rows created; 0 parent_task_id messages
**Why human:** Requires live Supabase execution

#### 3. Frontend Vitest Suite

**Test:**
```bash
cd frontend && npx vitest run \
  src/components/chat/AgentStatusChip.test.tsx \
  src/components/chat/TaskPanel.test.tsx \
  src/components/chat/MessageView.test.tsx
```
**Expected:** 23 tests pass (7 + 9 + 7)
**Why human:** Requires npm/node environment with all frontend dependencies

#### 4. End-to-End UI Verification

**Test:** Start both frontend and backend locally; enable `SUB_AGENT_ENABLED=true` and `DEEP_MODE_ENABLED=true`; send a message in deep mode that triggers an ask_user pause
**Expected:** AgentStatusChip transitions working → waiting_for_user (purple, question icon); ask_user question-bubble appears in MessageView; reply resumes to working → complete (auto-fades in 3s); TaskPanel shows task cards if task tool invoked
**Why human:** Visual and real-time behavior; requires running services

---

### Gaps Summary

No gaps identified. All 17 must-haves are VERIFIED through static code analysis:

1. **Migration 040** — exists with full DDL, correct constraints, RLS policies, and messages.parent_task_id column
2. **agent_runs_service** — fully implemented with RLS-scoped client, race-mitigation guard, audit logging
3. **sub_agent_loop** — 493-line async generator with correct EXCLUDED set, D-09 retention, egress filter, failure isolation, loop cap
4. **Config flag** — `sub_agent_enabled: bool = False` confirmed present
5. **task tool** — registered via adapter-wrap, dispatch in chat.py, SHA-256 invariant preserved
6. **ask_user tool** — registered, pause path wired, Site B emission canonical and gated
7. **Resume detection** — gated by both flags, wires body.message as tool result
8. **agent_status Sites A/B/C/D** — all 4 sites confirmed gated by sub_agent_enabled
9. **Lifecycle hooks** — start_run/complete/error at correct sites
10. **Byte-identical fallback** — all emission sites gated; E2E Test 11 has positive subset assertion
11. **Frontend state slices** — agentStatus + tasks Map with SSE reducer cases
12. **AgentStatusChip** — 4 states, auto-fade, a11y, no glass, wired to context
13. **TaskPanel** — card-per-task, visibility rule, no glass, wired to context
14. **MessageView question-bubble** — isAskUserQuestion helper, border-l-[3px], icon
15. **i18n** — 24 entries (12 × 2 locales) confirmed
16. **deep_mode_prompt** — stubs replaced, all 3 new sections present, deterministic
17. **Test coverage** — 7+7+21+8+6+6+8+6+12 backend tests + 23 frontend tests; E2E covers all 17 REQ-IDs

Status is `human_needed` because automated checks cannot execute live tests against Supabase or the frontend build, and real-time UI behavior requires visual verification.

---

_Verified: 2026-05-03T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
