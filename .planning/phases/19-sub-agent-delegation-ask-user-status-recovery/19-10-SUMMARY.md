---
phase: 19
plan: 10
subsystem: frontend-tests
tags: [vitest, testing, frontend, phase-19, agent-status, task-panel, ask-user]
dependency_graph:
  requires: [19-07]
  provides: [test-coverage-agent-status-chip, test-coverage-task-panel, test-coverage-message-view-question-bubble]
  affects: []
tech_stack:
  added: []
  patterns: [vitest-3.2-colocation, fake-timers, useChatContext-mock, scrollIntoView-stub]
key_files:
  created:
    - frontend/src/components/chat/AgentStatusChip.test.tsx
    - frontend/src/components/chat/TaskPanel.test.tsx
    - frontend/src/components/chat/MessageView.test.tsx
  modified: []
decisions:
  - "Lucide icon class names differ from their component names: CheckCircle2→lucide-circle-check, AlertCircle→lucide-circle-alert, Loader2→lucide-loader-circle, MessageCircleQuestion→lucide-message-circle-question-mark"
  - "SVG className is SVGAnimatedString in jsdom — use getAttribute('class') for class assertions on SVG elements"
  - "scrollIntoView not implemented in jsdom — stub window.HTMLElement.prototype.scrollIntoView in beforeEach"
  - "I18nProvider reads locale from localStorage (no prop) — use localStorage.setItem('locale', 'en') in beforeEach per WorkspacePanel.test.tsx convention"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-03T08:20:46Z"
  tasks_completed: 3
  files_created: 3
---

# Phase 19 Plan 10: Vitest Component Test Suite Summary

Vitest 3.2 co-located behavioral tests for three Phase 19 frontend components: AgentStatusChip (status chip with auto-fade timer), TaskPanel (sub-agent task progress panel), and MessageView question-bubble variant (D-27 unmatched ask_user detection).

## Test Counts

| File | Tests | Requirement |
|------|-------|-------------|
| `AgentStatusChip.test.tsx` | 7 | STATUS-01 / D-26 |
| `TaskPanel.test.tsx` | 9 | TASK-07 / D-25 |
| `MessageView.test.tsx` | 7 | ASK-02 / D-27 |
| **Total** | **23** | — |

All 23 tests pass (`npx vitest run` across all three files).

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 — AgentStatusChip.test.tsx | `24e23a0` | test(19-10): add AgentStatusChip Vitest 3.2 suite (7 tests) |
| 2 — TaskPanel.test.tsx | `f705351` | test(19-10): add TaskPanel Vitest 3.2 suite (9 tests) |
| 3 — MessageView.test.tsx | `eaebce7` | test(19-10): add MessageView question-bubble Vitest 3.2 suite (7 tests) |

## What Each Suite Covers

### AgentStatusChip (7 tests)
- `null` state: only sr-only aria-live container in DOM, no chip text
- `working` state: pulsing dot (`bg-primary animate-pulse`) + "Agent working" label (EN)
- `working` state bilingual: "Agen sedang bekerja" (ID) via `localStorage.setItem('locale','id')`
- `waiting_for_user`: `lucide-message-circle-question-mark` SVG + "Agent waiting for your reply"
- `complete`: `lucide-circle-check` SVG + fake timers confirm `setAgentStatus(null)` after 3000ms
- `error`: `lucide-circle-alert` SVG + no auto-fade after 5000ms (setAgentStatus not called)
- ARIA: `role=status` + `aria-live=polite` in both null and visible states

### TaskPanel (9 tests)
- Empty map → `null` render (no aside in DOM)
- 3 task entries → 3 description strings rendered
- Running: `lucide-loader-circle` with `animate-spin text-purple-500` via `getAttribute('class')`
- Complete: `lucide-circle-check` + result `line-clamp-2` paragraph
- Error: `lucide-circle-alert` + `text-red-*` error detail text
- context_files: chips with `title` attribute = full path + `truncate` class
- Nested tool calls: `font-mono text-[11px]` span with tool name
- Collapse/expand toggle via `userEvent.click` — content hidden then restored
- ARIA: `role=complementary` + `aria-label` on the aside element

### MessageView (7 tests)
- No tool_calls → no `role=note` rendered
- ask_user with matching tool_result (same `tool` field) → no question-bubble
- ask_user without matching tool_result → question-bubble with question text
- Visual: `border-l-[3px]` + `border-primary` on bubble container
- A11y: `role=note` + `aria-label="Question from agent"` (EN translation)
- Icon: `lucide-message-circle-question-mark` inside bubble
- DOM order: assistant content `compareDocumentPosition` BEFORE question-bubble (UI-SPEC L235)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Lucide icon class names differ from component names**
- **Found during:** Task 1 (AgentStatusChip)
- **Issue:** Initial selectors `svg.lucide-check-circle-2`, `svg.lucide-alert-circle`, `svg.lucide-loader-2` all returned null in jsdom. Lucide renders its icons with a different kebab-case slug than the export name.
- **Fix:** Discovered actual class names by running a temporary diagnostic test: `CheckCircle2→lucide-circle-check`, `AlertCircle→lucide-circle-alert`, `Loader2→lucide-loader-circle`, `MessageCircleQuestion→lucide-message-circle-question-mark`.
- **Files modified:** `AgentStatusChip.test.tsx`, `TaskPanel.test.tsx`
- **Commit:** part of per-task commits

**2. [Rule 1 - Bug] SVGAnimatedString className not a plain string**
- **Found during:** Task 2 (TaskPanel)
- **Issue:** `svgEl?.className.toContain(...)` fails because SVG `className` is `SVGAnimatedString`, not a `string`.
- **Fix:** Changed to `svgEl?.getAttribute('class') ?? ''` for class assertions on SVG elements.
- **Files modified:** `TaskPanel.test.tsx`

**3. [Rule 1 - Bug] scrollIntoView not implemented in jsdom**
- **Found during:** Task 3 (MessageView)
- **Issue:** `bottomRef.current?.scrollIntoView(...)` in MessageView's `useEffect` throws `TypeError: bottomRef.current?.scrollIntoView is not a function` in jsdom.
- **Fix:** Added `window.HTMLElement.prototype.scrollIntoView = vi.fn()` in `beforeEach`, following the same pattern as `vi.stubGlobal('open', vi.fn())` in WorkspacePanel.test.tsx.
- **Files modified:** `MessageView.test.tsx`

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Test files only.

## Phase 19 Frontend Test Aggregate

| Phase 19 Plan | Test Files | Tests |
|---------------|-----------|-------|
| 19-08 (backend) | `test_sub_agent*.py` | ~12 |
| 19-09 (E2E) | `sub_agent_e2e.test.ts` | ~8 |
| 19-10 (frontend) | 3 Vitest suites | 23 |

## Self-Check: PASSED

Files exist:
- `frontend/src/components/chat/AgentStatusChip.test.tsx` — FOUND
- `frontend/src/components/chat/TaskPanel.test.tsx` — FOUND
- `frontend/src/components/chat/MessageView.test.tsx` — FOUND

Commits exist:
- `24e23a0` — FOUND
- `f705351` — FOUND
- `eaebce7` — FOUND
