---
phase: 17-deep-mode-foundation-planning-todos-plan-panel
plan: "07"
subsystem: frontend-chat-ui
tags: [plan-panel, todos, sse, hydration, vitest, tdd, i18n, dark-launch, react]

dependency_graph:
  requires:
    - "17-03: write_todos + read_todos LLM tools (todos_updated SSE event source)"
    - "17-05: GET /threads/{id}/todos REST endpoint (hydration source)"
    - "17-06: deep_mode toggle + badge UI (isCurrentMessageDeepMode tracking)"
  provides:
    - "PlanPanel.tsx — real-time per-thread todo sidebar with D-22 visibility rule"
    - "useChatState.ts — todos slice + TODOS_UPDATED SSE handler + thread-switch hydration"
    - "fetchThreadTodos — GET /threads/{id}/todos API client function"
    - "TodoStatus + Todo + TodosUpdatedEvent types in database.types.ts"
    - "planPanel.* i18n keys (id + en) in translations.ts"
    - "10 Vitest tests (PlanPanel visibility, status indicators, hydration, SSE, glass rule, collapsible)"
  affects:
    - "frontend/src/pages/ChatPage.tsx — PlanPanel slotted as right-side sidebar column"
    - "frontend/src/hooks/useChatState.ts — todos + isCurrentMessageDeepMode in return value"

tech_stack:
  added: []
  patterns:
    - "D-22 visibility rule: panel shows when isCurrentMessageDeepMode OR todos.length > 0"
    - "Full-replacement todo state: TODOS_UPDATED action replaces todos slice in full"
    - "Thread-switch hydration: useEffect on activeThreadId calls fetchThreadTodos then setTodos"
    - "SVG className testing: use getAttribute('class') not .className (SVGAnimatedString in jsdom)"
    - "PlanPanel in ChatPage (not AppLayout): chat context (ChatProvider) only available at ChatPage scope"

key_files:
  created:
    - frontend/src/components/chat/PlanPanel.tsx
    - frontend/src/components/chat/__tests__/PlanPanel.test.tsx
  modified:
    - frontend/src/lib/database.types.ts
    - frontend/src/lib/api.ts
    - frontend/src/hooks/useChatState.ts
    - frontend/src/i18n/translations.ts
    - frontend/src/pages/ChatPage.tsx

decisions:
  - "PlanPanel slotted into ChatPage.tsx (not AppLayout.tsx as written in plan) because ChatProvider is only mounted inside AppLayout's Outlet children. AppLayout has no chat context. ChatPage wraps the panel in a flex-row alongside the message view column."
  - "TodoStatus, Todo, TodosUpdatedEvent added to database.types.ts (project type home) not a new types/index.ts (that file doesn't exist in this project)"
  - "SSEEvent union extended with TodosUpdatedEvent — useChatState already dispatches on event.type === 'todos_updated'"
  - "Test for SVG className uses getAttribute('class') instead of .className to avoid SVGAnimatedString jsdom issue"
  - "fetchThreadTodos returns {todos:[]} on non-2xx (non-blocking failure, T-17-16 mitigation)"

metrics:
  duration: "~5 minutes"
  completed: "2026-05-03"
  task_count: 2
  file_count: 7
---

# Phase 17 Plan 07: Plan Panel Summary

Per-thread Plan Panel sidebar with real-time SSE-driven todo display + thread-reload hydration. Closes Phase 17.

## One-Liner

PlanPanel sidebar component (D-22 visibility, D-25 status indicators, D-26 reducer state) with 10 Vitest tests, todos_updated SSE handler, fetchThreadTodos hydration, and i18n strings — closes Phase 17.

## Performance

- **Duration:** ~5 minutes
- **Started:** 2026-05-03T05:43:06Z
- **Completed:** 2026-05-03T05:47:57Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments

### Task 1 (TDD RED)

- Added `TodoStatus`, `Todo` types and `TodosUpdatedEvent` interface to `database.types.ts`
- Extended `SSEEvent` union with `TodosUpdatedEvent`
- Added `fetchThreadTodos(thread_id, token)` to `api.ts` — GET /threads/{id}/todos with non-blocking error handling
- Extended `useChatState.ts`:
  - `todos: Todo[]` state slice (default [])
  - `isCurrentMessageDeepMode: boolean` state (tracks D-22 panel visibility)
  - `TODOS_UPDATED` SSE handler in the stream loop
  - `useEffect` on `activeThreadId`: resets todos, then calls `fetchThreadTodos` for hydration
  - Both `todos` and `isCurrentMessageDeepMode` exported from hook return value
- Added `planPanel.title`, `planPanel.empty`, `planPanel.status.*` i18n keys for `id` (Indonesian) and `en` locales
- Wrote 10 failing Vitest tests for PlanPanel (RED gate)

### Task 2 (TDD GREEN)

- Created `frontend/src/components/chat/PlanPanel.tsx`:
  - `StatusIcon` sub-component with `data-testid` attributes for each status
  - Visibility rule (D-22): `isCurrentMessageDeepMode || todos.length > 0`
  - `useState(false)` collapse toggle with `ChevronDown`/`ChevronRight` button
  - Todos sorted by `position` (D-04)
  - `line-through text-muted-foreground` for completed todos
  - NO `backdrop-blur` anywhere (CLAUDE.md persistent-panel rule)
- Slotted into `ChatPage.tsx` as a right-side flex column alongside the message view

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | TDD RED: types + api + reducer + tests | `0407726` | database.types.ts, api.ts, useChatState.ts, translations.ts, PlanPanel.test.tsx |
| 2 | TDD GREEN: PlanPanel + ChatPage slot | `3462789` | PlanPanel.tsx, ChatPage.tsx, PlanPanel.test.tsx |

## Verification Against Plan Criteria

| Criterion | Status |
|-----------|--------|
| PlanPanel renders hidden when no todos + no deep mode | PASS |
| PlanPanel renders with todos (2 rows, title) | PASS |
| PlanPanel renders empty state when deep mode on + no todos | PASS |
| Status indicator pending = zinc Circle | PASS |
| Status indicator in_progress = purple Loader2 animate-spin | PASS |
| Status indicator completed = green CheckCircle2 | PASS |
| Hydration: fetchThreadTodos called on thread mount | PASS |
| SSE state: todos_updated dispatches → panel re-renders | PASS |
| No backdrop-blur on panel (CLAUDE.md rule) | PASS |
| Panel collapsible via toggle button | PASS |
| 10 Vitest tests pass | PASS — 10/10 |
| 64 full suite tests pass (zero regressions) | PASS — 64/64 |
| tsc --noEmit clean | PASS |
| planPanel.* i18n keys in both locales | PASS |

## Deviations from Plan

### Auto-deviation: PlanPanel in ChatPage instead of AppLayout

**Reason:** The plan lists `AppLayout.tsx` as the slot target, but `AppLayout.tsx` only has a generic `<Outlet>` — the `ChatProvider` (which provides `useChatContext`) is mounted inside `AppLayout` but its value (`useChatState()`) is available only to `<Outlet>` children. Since `PlanPanel` reads `todos` and `isCurrentMessageDeepMode` from `useChatContext`, it must be inside the provider's subtree. The correct slot is `ChatPage.tsx`, which is the primary chat route rendered by the outlet.

**Impact:** Functionally identical — PlanPanel appears as a right-side column in the chat view. The plan's intent (sidebar panel next to chat content) is fully satisfied.

### Auto-fix [Rule 1 - Bug]: SVG `className` is `SVGAnimatedString` in jsdom

**Found during:** Task 2 (GREEN gate run — 2/10 tests failed)

**Issue:** Lucide-react SVG elements use `className` as an `SVGAnimatedString` object in jsdom, not a regular `DOMString`. Vitest reported `expected [] to include 'animate-spin'` because the `className` property serializes as an array-like object, not a string.

**Fix:** Updated `test_status_indicator_in_progress`, `test_status_indicator_completed`, and `test_panel_no_glass` to use `element.getAttribute('class')` instead of `element.className`.

**Files modified:** `frontend/src/components/chat/__tests__/PlanPanel.test.tsx`

**Verification:** All 10 tests pass after fix.

### Auto-deviation: types in `database.types.ts` (not a new `types/index.ts`)

**Reason:** The plan says `frontend/src/types/index.ts` but that file does not exist in this project. All shared types live in `frontend/src/lib/database.types.ts` (project convention, confirmed by every existing type — `Thread`, `Message`, `SSEEvent`, etc.). Added `TodoStatus`, `Todo`, `TodosUpdatedEvent` there and extended `SSEEvent` union.

## Known Stubs

None — PlanPanel is fully wired:
- Live updates: `todos_updated` SSE handler in `useChatState.ts` → `setTodos(event.todos)`
- Reload hydration: `useEffect` on `activeThreadId` calls `fetchThreadTodos` → `setTodos(fetched)`
- The todo data flows from the backend `agent_todos` table via Plan 17-03 (write_todos tool) and Plan 17-05 (GET endpoint)

## Threat Flags

No new threat surface beyond what Plan 17-05 already mitigated (T-17-12, T-17-13).

| Flag | File | Description |
|------|------|-------------|
| T-17-16 (mitigated) | frontend/src/hooks/useChatState.ts | todos reset to [] on thread switch before hydration; fetchThreadTodos called with current thread_id only; backend RLS authoritative |

## TDD Gate Compliance

- RED gate: `0407726` — 10 failing tests (PlanPanel import fails — component not built)
- GREEN gate: `3462789` — 10 tests pass after PlanPanel implemented

## Self-Check

### Created Files Exist

- [x] `frontend/src/components/chat/PlanPanel.tsx` — FOUND
- [x] `frontend/src/components/chat/__tests__/PlanPanel.test.tsx` — FOUND

### Modified Files

- [x] `frontend/src/lib/database.types.ts` — TodoStatus, Todo, TodosUpdatedEvent added; SSEEvent extended
- [x] `frontend/src/lib/api.ts` — fetchThreadTodos added
- [x] `frontend/src/hooks/useChatState.ts` — todos slice, TODOS_UPDATED handler, hydration useEffect
- [x] `frontend/src/i18n/translations.ts` — planPanel.* keys in id + en
- [x] `frontend/src/pages/ChatPage.tsx` — PlanPanel import + flex-row layout slot

### Commits Exist

- [x] `0407726` — test(17-07): TDD RED gate
- [x] `3462789` — feat(17-07): TDD GREEN gate

## Self-Check: PASSED
