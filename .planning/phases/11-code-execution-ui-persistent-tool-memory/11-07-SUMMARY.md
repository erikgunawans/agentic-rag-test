---
phase: 11-code-execution-ui-persistent-tool-memory
plan: 07
subsystem: chat-ui
tags: [frontend, sandbox, integration, react, sse-routing]
requires: [11-04, 11-05, 11-06]
provides: [code-execution-panel-routing, sandbox-streams-prop-drill]
affects: [chat-message-rendering, tool-call-list]
tech-stack:
  added: []
  patterns:
    - "Prop-drill from useChatState → ChatPage → MessageView → ToolCallList (matches existing pattern for activeTools, toolResults, activeAgent, redactionStage)"
    - "Two-section render: sandboxCalls partition (flex flex-col gap-6) + otherCalls partition (space-y-0.5) inside ToolCallList, segregated by tool === 'execute_code' && tool_call_id"
key-files:
  created: []
  modified:
    - frontend/src/components/chat/ToolCallCard.tsx
    - frontend/src/components/chat/MessageView.tsx
    - frontend/src/pages/ChatPage.tsx
key-decisions:
  - "Pass sandboxStreams unconditionally to ToolCallList (not gated on per-message streamingMessageId) because MessageView does not currently track a streaming-message-id flag — the streaming UI is rendered in a separate block below messages.map. Stale Map entries cannot collide with persisted panels because tool_call_id keys are UUIDs and CodeExecutionPanel only consults Map entries it knows about (D-P11-05)."
  - "Use canonical out.execution_id key (no `?? out.id` fallback) per backend/app/services/sandbox_service.py L284 — the sandbox tool_output dict has no `id` key."
  - "Add ChatPage.tsx as a third modified file (not in original plan <files>) because the prop-drill pattern requires ChatPage to destructure sandboxStreams from useChatContext() and pass it to MessageView."
requirements-completed: [SANDBOX-07]
duration: 14 min (auto tasks); +overnight to UAT approval
completed: 2026-05-02 (UAT approved by user)
---

# Phase 11 Plan 07: ToolCallList Routing + sandboxStreams Plumbing Summary

`ToolCallList` becomes a router: `execute_code` calls with `tool_call_id` render via `CodeExecutionPanel`; everything else (including legacy execute_code calls without `tool_call_id`) keeps the existing `ToolCallCard`. `MessageView` plumbs `sandboxStreams` from `useChatState` (Plan 11-05's hook output) through `ChatPage` to `ToolCallList` so live SSE buffers reach the panel during streaming, and the panel falls back to persisted `msg.tool_calls.calls[N].output` after the post-stream refetch clears the Map.

## Execution Snapshot

| Field | Value |
|-------|-------|
| Plan | 11-07 |
| Tasks completed (auto) | 3 / 4 (Task 4 = blocking checkpoint awaiting human UAT) |
| Duration | 14 min |
| Start | 2026-05-01T13:46:00Z |
| End | 2026-05-01T14:00:03Z |
| Commits | 2 task commits (`64b17da`, `8f1f715`) — one per task; Task 3 is verification-only and ships no code changes |
| Files modified | 3 (`ToolCallCard.tsx`, `MessageView.tsx`, `ChatPage.tsx`) |

## What Was Built

### Task 1: ToolCallList router switch (commit `64b17da`)

`frontend/src/components/chat/ToolCallCard.tsx` — three splices:

1. **Imports** — added `Terminal` to the lucide barrel import; added `import { CodeExecutionPanel } from './CodeExecutionPanel'`.
2. **TOOL_CONFIG** — added `execute_code: { icon: Terminal, label: 'Code Execution' }` so legacy calls without `tool_call_id` (D-P11-03 fallback) render via the generic `ToolCallCard` with a sensible icon + label.
3. **`ToolCallListProps` widening** — added optional `sandboxStreams?: Map<string, { stdout: string[]; stderr: string[] }>` prop. Body rewritten to partition `toolCalls` into `sandboxCalls` (where `tc.tool === 'execute_code' && tc.tool_call_id`) vs `otherCalls`. Sandbox calls render in a `flex flex-col gap-6 mb-2` wrapper (24px vertical rhythm per UI-SPEC §Vertical Stack Layout); other calls keep the existing `space-y-0.5` rhythm.
4. **Live → persisted resolution** — for each sandbox call:
   - `live = sandboxStreams?.get(tcid)` — Plan 11-05's per-call buffer.
   - `persistedStdout = out.stdout_lines ?? (typeof out.stdout === 'string' ? split('\n') : [])` — defensive fallback for either persistence shape.
   - `stdoutLines = live?.stdout ?? persistedStdout ?? []` — live buffer takes precedence; persisted output fills the post-refetch state; empty array as final fallback.
   - `status` = `'running'` when live buffer exists, else `tc.status ?? 'success'`.
   - `executionId = out.execution_id` (no `?? out.id` fallback — backend's tool_output dict has no `id` key per `backend/app/services/sandbox_service.py` L284).
   - `executionMs`, `errorType`, `files` resolved from persisted output.
   - `code = (tc.input as { code?: string }).code ?? ''`.
5. **React key** — `key={tcid}` on each `CodeExecutionPanel` (D-P11-05 stable-identity) versus `key={i}` for generic `ToolCallCard` (legacy).

### Task 2: sandboxStreams plumbing (commit `8f1f715`)

`frontend/src/components/chat/MessageView.tsx`:
- Added `sandboxStreams?: Map<string, { stdout: string[]; stderr: string[] }>` to `MessageViewProps` (matching the optional-prop style of `activeTools`, `toolResults`, `activeAgent`, `redactionStage`).
- Destructured in the function signature (no default).
- Passed unconditionally at the existing `<ToolCallList toolCalls={msg.tool_calls.calls} />` call site.

`frontend/src/pages/ChatPage.tsx`:
- Added `sandboxStreams` to the `useChatContext()` destructure (`ChatContextValue = ReturnType<typeof useChatState>` already exposes it from Plan 11-05).
- Passed `sandboxStreams={sandboxStreams}` to the `<MessageView />` JSX.

**Branch chosen for Sub-change B: unconditional pass-through.** Rationale (per plan §Sub-change B fallback guidance): MessageView does not currently differentiate streaming vs persisted at the message level — the streaming UI is rendered as a separate block at L135 below `messages.map`, not as part of the per-message `ToolCallList` render. There is no `streamingMessageId` variable to gate on. Stale Map entries are not a correctness risk because (a) the Map is reset in 3 lifecycle sites by Plan 11-05 (`handleSelectThread` L68, `sendMessageToThread` enter L148, `sendMessageToThread` finally L264), and (b) `CodeExecutionPanel` only consults `sandboxStreams.get(toolCallId)` for keys it knows about — entries for prior messages do not collide with current panels because `tool_call_id` is a UUID.

### Task 3: Quality gate (no commit — verification only)

| Gate | Result |
|------|--------|
| `cd frontend && npx tsc --noEmit` | EXIT 0 |
| `cd frontend && npm run lint` | EXIT 1 globally; 0 errors in any of the 5 files in plan's `<files>` block (or in `ChatPage.tsx`). Pre-existing errors live in `DocumentsPage.tsx` (3× `react-hooks/set-state-in-effect`) and `ThemeContext.tsx` (1× `react-refresh/only-export-components`) — out of scope per orchestrator prompt's Plan 11-02 precedent. |
| `pytest tests/routers/test_chat_sandbox_streaming.py` | 8 passed (154 s) |
| `pytest tests/routers/test_chat_history_reconstruction.py` | 13 passed (153 s) |
| `pytest tests/models/test_tool_call_record.py` | 11 passed (2 s) |
| `python -c "from app.main import app; print('OK')"` | OK (EXIT 0) |

Anti-grep guards (per plan's verify gates):

| Guard | Result |
|-------|--------|
| `grep -q "import { CodeExecutionPanel }" src/components/chat/ToolCallCard.tsx` | PASS |
| `grep -q "Terminal, label: 'Code Execution'" src/components/chat/ToolCallCard.tsx` | PASS |
| `grep -q "tc.tool_call_id" src/components/chat/ToolCallCard.tsx` | PASS |
| `grep -q "sandboxStreams" src/components/chat/ToolCallCard.tsx` | PASS |
| `grep -q "flex flex-col gap-6" src/components/chat/ToolCallCard.tsx` | PASS |
| `grep -q "out.execution_id" src/components/chat/ToolCallCard.tsx` | PASS |
| `! grep -q "out.id as string" src/components/chat/ToolCallCard.tsx` | PASS (no `?? out.id` fallback reintroduced) |
| `grep -q "sandboxStreams" src/components/chat/MessageView.tsx` | PASS |
| `grep -q "ToolCallList" src/components/chat/MessageView.tsx` | PASS |

## Deviations from Plan

### 1. [Rule 3 — Blocker] Worktree branched from stale master (b6f14c5 not present)

- **Found during:** pre-Task-1 setup
- **Issue:** This worktree's branch (`worktree-agent-af84eb7edff01ed3c`) was created from a stale base — HEAD `7541fed` predates Phase 11 entirely. Per executor agent worktree_branch_check protocol (Claude Code EnterWorktree bug — branches from main instead of feature HEAD), this is a known issue that requires a hard reset to the correct base before starting work.
- **Fix:** `git reset --hard master` to align with `b6f14c5` (the Phase 11-06 completion HEAD on master per orchestrator prompt). Working tree was clean after reset; no prior worktree changes lost.
- **Files modified:** none (pre-task setup)
- **Verification:** `git rev-parse HEAD` returned `b6f14c5`; `ls .planning/phases/11-code-execution-ui-persistent-tool-memory/` showed all 6 prior plans + their summaries + 11-07-PLAN.md.
- **Commit:** none — pre-task setup

### 2. [Rule 3 — Blocker] Frontend node_modules missing in worktree

- **Found during:** Task 1 verification (`npx tsc --noEmit` failed with "This is not the tsc command you are looking for")
- **Issue:** Worktree `frontend/node_modules` does not exist; `npx tsc` resolved to a global empty package.
- **Fix:** `cd frontend && npm install` — installed 219 packages (4 vulnerabilities flagged but irrelevant to this plan).
- **Files modified:** none (transient — `node_modules/` is gitignored)
- **Verification:** subsequent `npx tsc --noEmit` and `npm run lint` ran from the local install.
- **Commit:** none — transient install

### 3. [Rule 2 — Missing wiring] ChatPage.tsx not in plan's `<files>` block

- **Found during:** Task 2 implementation
- **Issue:** Plan's `<files>` block listed only `ToolCallCard.tsx` and `MessageView.tsx`, but the existing prop-drill pattern (matching `activeTools`, `toolResults`, `activeAgent`, `redactionStage`) requires `ChatPage` to destructure `sandboxStreams` from `useChatContext()` and pass it to `MessageView`. Without the ChatPage edit, MessageView would receive `sandboxStreams={undefined}` and the live SSE buffer would never reach `ToolCallList`.
- **Fix:** Add `sandboxStreams` to the `useChatContext()` destructure in `frontend/src/pages/ChatPage.tsx` (L25 ish) and pass `sandboxStreams={sandboxStreams}` to `<MessageView />` (L62 ish).
- **Files modified:** `frontend/src/pages/ChatPage.tsx`
- **Verification:** tsc + lint pass; no errors introduced in ChatPage.
- **Commit:** `8f1f715` (rolled into Task 2 commit since it's part of the same plumbing change).

**Total deviations:** 3 — 2 worktree-environment blockers (Rule 3), 1 missing-file-from-plan wiring (Rule 2). **Impact:** Three Rule 3 blockers resolved without behavior change; 1 wiring file added to make the plumbing actually reach `MessageView`. No architectural changes; no Rule 4 escalations.

## Task 4 Checkpoint Handoff

**Status:** APPROVED 2026-05-02 — user replied `approved` after the orchestrator presented the 12-step UAT script in the running browser session (frontend `:5174`, backend `:8000` `/health = ok`).

All 12 verification steps passed. SANDBOX-07 + MEM-01..03 acceptance criteria are confirmed end-to-end through real execute_code rounds and a page-refresh persistence check.

**Plan 11-07 SUMMARY re-committed with the UAT outcome by the orchestrator.**

### Prereqs for the orchestrator to verify before driving UAT

1. **Backend running on `:8000`** —
   ```bash
   cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000
   ```
   Verify with `curl -s http://localhost:8000/health`.

2. **Frontend running on `:5173`** —
   ```bash
   cd frontend && npm run dev
   ```
   Verify with `curl -s http://localhost:5173/` returns the Vite-served HTML.

3. **Test account `test@test.com`** with password `!*-3-3?3uZ?b$v&` (per CLAUDE.md). Verify `super_admin` role on `user_profiles`.

4. **Sandbox / code-execution availability** — Phase 10 sandbox infrastructure must be deployable in the local env (Docker daemon up, sandbox container image built). If this is unavailable locally, the orchestrator should drive UAT against the production backend (`https://api-production-cde1.up.railway.app`) instead.

### 12-Step UAT Script (verbatim from 11-07-PLAN.md `<task type="checkpoint:human-verify">` `<action>` block)

1. Start backend: `cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:5173`, log in as test@test.com.
4. Send a chat message that triggers `execute_code` — example: "Write Python code to compute the first 20 Fibonacci numbers and save them as fib.csv."
5. Verify during streaming: a Code Execution Panel appears with the Python badge, a spinner status indicator, a live execution timer counting up, and stdout lines streaming into the dark terminal block in green.
6. Verify after completion: status turns to a green checkmark with "Selesai"/"Completed", timer freezes at the final ms value, the "Tampilkan kode"/"Show code" toggle reveals the executed code on click.
7. Verify file download: if the run produced `fib.csv`, a file card appears with filename + size + Download button. Click it; the file downloads in a new tab.
8. Verify persistence: refresh the page. The same panel re-renders from persisted state — stdout/stderr lines, status, timer, file card, code preview all match the post-completion state.
9. Verify follow-up reference: send a follow-up message like "What was the 15th Fibonacci number you computed?" — the LLM answers from memory without re-running execute_code (open browser devtools → Network tab → confirm no `code_stdout`/`code_stderr` SSE events on the new turn).
10. Verify legacy compatibility: any pre-Phase-11 messages with old `tool_calls` data still render without console errors (legacy fallback path).
11. Verify multi-call stacking: send "Run code A then run code B" — two CodeExecutionPanels appear stacked vertically with 24px gap.
12. Verify error path: send "Run `1/0` in Python" — status turns to a red X with "Gagal"/"Failed", stderr shows the traceback in red, error pill renders below the terminal with "Kesalahan runtime Python"/"Python runtime error".

**Resume signal (per plan):** Type "approved" or describe issues found.

## Authentication Gates

None. All work was code-level — no external auth was required for tsc, lint, or backend regression tests.

## Threat Flags

None. The change preserves existing trust boundaries: persisted `tc.input.code` / `tc.output.*` originate from cloud LLM tool output (already redacted upstream per Phase 5/Phase 10), live SSE Map entries are anonymized in chat.py per Phase 10-05, and all rendering goes through Plan 11-06's React-auto-escaped JSX. The routing layer adds no new XSS or trust surface (T-11-07-3 mitigation preserved).

## Self-Check: PASSED

- `[x] frontend/src/components/chat/ToolCallCard.tsx` modified — verified by `git show 64b17da --stat`.
- `[x] frontend/src/components/chat/MessageView.tsx` modified — verified by `git show 8f1f715 --stat`.
- `[x] frontend/src/pages/ChatPage.tsx` modified — verified by `git show 8f1f715 --stat`.
- `[x] Commit 64b17da` exists in `git log --oneline --all`.
- `[x] Commit 8f1f715` exists in `git log --oneline --all`.
- `[x] All Task 1/2 acceptance criteria pass (grep gates 9/9, anti-grep 1/1).`
- `[x] All Task 3 verification commands pass (tsc, lint plan-files, 32 backend tests, app import).`
- `[ ] Task 4 (human UAT) — AWAITING orchestrator-driven verification with user.`
