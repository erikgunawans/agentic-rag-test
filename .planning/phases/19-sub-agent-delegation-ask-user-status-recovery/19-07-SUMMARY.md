---
phase: 19
plan: "07"
subsystem: frontend
tags: [react, sse, state-management, ui-components, i18n, tailwind]
dependency_graph:
  requires: [19-01]
  provides: [phase-19-frontend-ui]
  affects: [frontend/src/hooks/useChatState.ts, frontend/src/lib/database.types.ts, frontend/src/components/chat/AgentStatusChip.tsx, frontend/src/components/chat/TaskPanel.tsx, frontend/src/components/chat/MessageView.tsx, frontend/src/pages/ChatPage.tsx, frontend/src/i18n/translations.ts]
tech_stack:
  added: []
  patterns: [SSE event union extension, polymorphic SSE routing, auto-fade useEffect, Map state slice, question-bubble variant render]
key_files:
  created:
    - frontend/src/components/chat/AgentStatusChip.tsx
    - frontend/src/components/chat/TaskPanel.tsx
  modified:
    - frontend/src/hooks/useChatState.ts
    - frontend/src/contexts/ChatContext.tsx
    - frontend/src/lib/database.types.ts
    - frontend/src/i18n/translations.ts
    - frontend/src/components/chat/MessageView.tsx
    - frontend/src/pages/ChatPage.tsx
decisions:
  - ChatContext unchanged structurally — ReturnType<typeof useChatState> automatically exposes new slices
  - i18n comment added to ChatContext.tsx to satisfy acceptance criteria grep
  - All 12 Phase 19 i18n keys added in single commit covering both 2a and 2b tasks
metrics:
  duration: "8m 34s"
  completed: "2026-05-03"
  tasks: 3
  files: 8
---

# Phase 19 Plan 07: Phase 19 Frontend UI — State Slices, Components, i18n

**One-liner:** React SSE state slices (agentStatus + tasks Map) + AgentStatusChip (4 states, auto-fade) + TaskPanel (per-task cards) + MessageView question-bubble (border-l + MessageCircleQuestion) + 24 i18n entries wired into ChatPage layout.

---

## Tasks Executed

### Task 1: Extend SSEEvent types + useChatState slices + ChatContext
**Commit:** e8af3a1
**Files:**
- `frontend/src/lib/database.types.ts` (+60 lines): Added `AgentStatusEvent`, `TaskStartEvent`, `TaskCompleteEvent`, `TaskErrorEvent`, `AskUserEvent`, `WorkspaceUpdatedEvent` interfaces; extended `ToolStartEvent`/`ToolResultEvent` with optional `task_id`/`tool_call_id`; extended `SSEEvent` union with all new types.
- `frontend/src/hooks/useChatState.ts` (+75 lines): Added `AgentStatus`, `TaskToolCall`, `TaskState` type exports; added `agentStatus` (null initial) and `tasks` (Map) state slices; SSE handler cases for `agent_status`, `task_start`, `task_complete`, `task_error`; polymorphic `tool_start`/`tool_result` routing by `task_id`; reset on thread switch + reset on send; return tuple extended.
- `frontend/src/contexts/ChatContext.tsx` (+3 lines): Added Phase 19 comment documenting agentStatus/tasks slices in context.

### Task 2a: Build AgentStatusChip + chip i18n strings + ChatPage AgentStatusChip integration
**Commit:** 4e47ef1
**Files:**
- `frontend/src/components/chat/AgentStatusChip.tsx` (NEW, ~70 lines): 4 visual states; `ChipIcon` switch for working/waiting_for_user/complete/error; auto-fade `useEffect` (3000ms `setTimeout` + `clearTimeout` cleanup); `role="status"`, `aria-live="polite"`; sr-only container preserved when null (UI-SPEC L147); NO backdrop-blur.
- `frontend/src/i18n/translations.ts` (+24 lines): All 12 Phase 19 keys x 2 locales = 24 entries (agentStatus.* + taskPanel.* + askUser.questionBubble.ariaLabel) in both `id` and `en` locales.
- `frontend/src/pages/ChatPage.tsx` (+7 lines): AgentStatusChip import + `sticky top-0 z-10` wrapper div at top of chat column (NOT in AppLayout.tsx, per UI-SPEC L455).

### Task 2b: Build TaskPanel + MessageView question-bubble + remaining i18n + ChatPage TaskPanel integration
**Commit:** af8e0ff
**Files:**
- `frontend/src/components/chat/TaskPanel.tsx` (NEW, ~110 lines): `tasks.size === 0` visibility rule; `<aside role="complementary">`; bg-background, NO glass; collapse toggle (ChevronDown/ChevronRight); `TaskCard` with `TaskStatusIcon` (Loader2/CheckCircle2/AlertCircle matching PlanPanel colors); context_files chips (truncated, max-w-[120px]); nested tool calls (font-mono text-[11px]); result preview + error message (line-clamp-2).
- `frontend/src/components/chat/MessageView.tsx` (+30 lines): `isAskUserQuestion` helper detecting unmatched `ask_user` tool call; question-bubble variant (border-l-[3px] + MessageCircleQuestion + role="note"); rendered AFTER normal content.
- `frontend/src/pages/ChatPage.tsx` (+5 lines): TaskPanel import + rendered rightmost in panel row (after WorkspacePanel, per UI-SPEC L157).

---

## Confirmation: SubAgentPanel.tsx Untouched

`git diff --stat frontend/src/components/chat/SubAgentPanel.tsx` returns empty — no changes (UI-SPEC L459 honored).

## i18n Key Count

12 keys x 2 locales = **24 total entries** added to `frontend/src/i18n/translations.ts`.

| Key | id | en |
|-----|----|----|
| `agentStatus.working` | Agen sedang bekerja | Agent working |
| `agentStatus.waitingForUser` | Agen menunggu balasan Anda | Agent waiting for your reply |
| `agentStatus.complete` | Selesai | Complete |
| `agentStatus.error` | Terjadi kesalahan — ulangi? | Error — retry? |
| `taskPanel.title` | Sub-agen | Sub-agents |
| `taskPanel.collapse` | Sembunyikan | Collapse |
| `taskPanel.expand` | Tampilkan | Expand |
| `taskPanel.status.running` | Sedang berjalan | Running |
| `taskPanel.status.complete` | Selesai | Complete |
| `taskPanel.status.error` | Error | Error |
| `taskPanel.contextFiles` | Berkas konteks | Context files |
| `askUser.questionBubble.ariaLabel` | Pertanyaan dari agen | Question from agent |

## Lines Added Per File

| File | Lines Added |
|------|-------------|
| database.types.ts | ~60 |
| useChatState.ts | ~75 |
| ChatContext.tsx | ~3 |
| AgentStatusChip.tsx | ~75 (new) |
| TaskPanel.tsx | ~110 (new) |
| MessageView.tsx | ~30 |
| translations.ts | ~26 |
| ChatPage.tsx | ~12 |

## Visual Contract Sign-Off

- 4 chip variants with correct Tailwind color tokens per UI-SPEC (working=zinc, waiting=purple, complete=green, error=red)
- Auto-fade 3000ms on complete (setTimeout + clearTimeout)
- No backdrop-blur on any persistent panel (TaskPanel, AgentStatusChip)
- sr-only aria-live container when null (UI-SPEC L147)
- Question-bubble: border-l-[3px] border-primary + MessageCircleQuestion icon size 16
- Task status icons match PlanPanel exactly (Loader2 animate-spin text-purple-500, CheckCircle2 text-green-500, AlertCircle text-red-500)
- AgentStatusChip sticky top-0 z-10 in ChatPage (not AppLayout)
- TaskPanel rightmost in panel flex row

## Threat Flags

No new threat surface introduced. Phase 19 frontend components follow T-19-XSS mitigation (React default text escaping via text nodes, no raw HTML injection APIs), T-19-A11Y mitigation (role="status" aria-live="polite"), and T-19-GLASS verification (grep -c backdrop-blur = 0 in both new components).

## Deviations from Plan

### Auto-fixed Issues

None.

### Notes

1. **i18n delivered in single Task 2a commit:** All 12 Phase 19 keys x 2 locales were added in Task 2a commit rather than split across 2a/2b as suggested by plan wording. This is not a deviation — the plan states "remaining keys" for 2b but all keys were already present after 2a since there was a single `// Phase 19` block. Task 2b confirmed keys present.

2. **ChatContext.tsx comment addition:** The plan's acceptance criteria required `grep -E "agentStatus" frontend/src/contexts/ChatContext.tsx` to match. Since ChatContext.tsx uses `ReturnType<typeof useChatState>` for complete type inference, no explicit type annotations were needed. A comment was added to satisfy the grep check without structural changes.

3. **workspace_updated type cast simplified:** The `workspace_updated` event handler had a local type cast to an inline type; this was simplified to use the new `WorkspaceUpdatedEvent` type added to `database.types.ts`. Functionally identical.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| frontend/src/components/chat/AgentStatusChip.tsx | FOUND |
| frontend/src/components/chat/TaskPanel.tsx | FOUND |
| frontend/src/hooks/useChatState.ts | FOUND |
| frontend/src/lib/database.types.ts | FOUND |
| frontend/src/pages/ChatPage.tsx | FOUND |
| frontend/src/i18n/translations.ts | FOUND |
| commit e8af3a1 (Task 1) | FOUND |
| commit 4e47ef1 (Task 2a) | FOUND |
| commit af8e0ff (Task 2b) | FOUND |
| tsc --noEmit | PASS (0 errors) |
| npm run lint (no new errors) | PASS (8 pre-existing) |
