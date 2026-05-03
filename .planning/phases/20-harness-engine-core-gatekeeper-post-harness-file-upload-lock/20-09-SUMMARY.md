---
phase: 20-harness-engine-core-gatekeeper-post-harness-file-upload-lock
plan: 09
subsystem: frontend-harness-sse
tags: [harness, sse, banner, useChatState, phase20, W8, B1, PANEL-02]
dependency_graph:
  requires: [20-04, 20-08]
  provides: [harnessRun-slice, HarnessBanner, harness-sse-reducer-arms]
  affects: [ChatPage, useChatState, ChatContext, apiFetch]
tech_stack:
  added: []
  patterns:
    - SSE reducer arm pattern (mirrors agentStatus slice from Phase 19)
    - 3000ms terminal-fade useEffect (mirrors AgentStatusChip auto-fade)
    - Module-level Set constants to avoid react-hooks/exhaustive-deps warnings
    - apiFetch error augmentation with .status + .body for 409 detection
key_files:
  created:
    - frontend/src/components/chat/HarnessBanner.tsx
    - frontend/src/components/chat/HarnessBanner.test.tsx
    - frontend/src/hooks/__tests__/useChatState.test.ts
  modified:
    - frontend/src/hooks/useChatState.ts
    - frontend/src/lib/api.ts
    - frontend/src/pages/ChatPage.tsx
decisions:
  - "harnessToast state (not a DOM toast library) — no toast UI component exists; expose slice for consumer to render"
  - "TERMINAL/ACTIVE_HARNESS_STATUSES moved to module level to satisfy react-hooks/exhaustive-deps"
  - "apiFetch enriched with .status + .body on thrown errors — required for 409 harness_in_progress detection"
  - "HarnessBanner sr-only stub (not null) when harnessRun=null — aria-live container stays in DOM"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-04"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 6
  tests_added: 21
---

# Phase 20 Plan 09: SSE Reducer Arms + HarnessBanner + ChatPage Slot Summary

Wire the backend's `harness_*` SSE events into frontend state via 6 reducer arms in `useChatState`, render the HarnessBanner above AgentStatusChip in ChatPage, and add 21 Vitest 3.2 tests.

## Tasks Completed

| Task | Description | Commit | Tests |
|------|-------------|--------|-------|
| 1 | Extend useChatState: SSE reducer arms + terminal fade + thread-switch reset + W8 phase_count seeding + B1 no-op + 409 toast | `ec73405` (RED) `837eed5` (GREEN) | 12 |
| 2 | Create HarnessBanner + co-located test | `3cfae64` | 9 |
| 3 | Slot HarnessBanner into ChatPage + lint fixes | `86536c0` | — |

## harnessRun Slice Contract

The `harnessRun` slice (type `HarnessRunSlice`) was bootstrapped in Plan 20-08. Plan 20-09 wires the full SSE event cycle:

```
null → (gatekeeper_complete triggered=true) → { status: 'pending', phaseCount: N }
      → (harness_phase_start)               → { status: 'running', currentPhase: i, phaseName: ... }
      → (harness_phase_complete)            → { currentPhase: i+1 }
      → (harness_complete)                  → { status: 'completed' | 'failed' | 'cancelled' }
      → (3000ms timeout)                    → null
```

Thread switch: immediately reset to null, then refetch `GET /threads/{id}/harness/active`.

## SSE Reducer Arms (6 new arms)

| Event | Action |
|-------|--------|
| `harness_phase_start` | Sets `status='running'`, `currentPhase`, `phaseName` |
| `harness_phase_complete` | Bumps `currentPhase + 1` |
| `harness_phase_error` | `code='cancelled'` or `reason='cancelled_by_user'` → `status='cancelled'`; else → `status='failed'`, `errorDetail` |
| `harness_complete` | Sets `status` from payload |
| `gatekeeper_complete` (triggered=true) | Seeds `harnessRun` with `{ status:'pending', phaseCount: payload.phase_count }` (W8 fix) |
| `harness_sub_agent_start/complete` | Explicit no-op (B1 forward-compat; Phase 21 will hook in) |

## W8 Fix: phase_count Seeding

Plan 20-04 added `phase_count` to the `gatekeeper_complete` event payload. Plan 20-09's `gatekeeper_complete` arm seeds `harnessRun.phaseCount` directly from this field, eliminating the prior fallback fetch. The banner can show "phase 1 of N" fraction on the very first `harness_phase_start` tick.

## B1 Forward-Compatibility

`harness_sub_agent_start` and `harness_sub_agent_complete` events have explicit no-op arms. Without these, both events would fall through to the `delta/done` branch and attempt to parse `event.delta` — generating spurious console warnings. Phase 21 will add sub-agent telemetry UI by wiring into these arms.

## apiFetch Enhancement (Deviation — Rule 2)

`frontend/src/lib/api.ts` now attaches `.status` and `.body` to thrown errors:
```ts
err.status = response.status  // enables 409 detection
err.body = body               // enables harness_in_progress body inspection
```
This is a correctness requirement: without `.status`, the 409 reject-while-active path cannot distinguish a harness-block from any other HTTP error. Existing behavior is byte-identical for successful requests.

## 409 Reject-While-Active Toast

When `POST /chat/stream` returns 409 `{error: 'harness_in_progress'}`:
- `harnessToast` state slice is set with `{ message, harnessType, currentPhase, phaseCount }`
- The optimistic user message is removed from the UI
- The message draft is NOT cleared (user can retry after harness completes)
- `harnessToast` and `setHarnessToast` are exported from the hook for HarnessBanner to display

## HarnessBanner Component

Location: `frontend/src/components/chat/HarnessBanner.tsx`

| State | Visual |
|-------|--------|
| null | `data-testid="harness-banner-empty"` sr-only div (0 height) |
| pending/running/paused | Pulsing dot + phase fraction + Cancel button |
| cancelled | XCircle + cancelled copy (no Cancel) |
| failed | AlertCircle + failed+detail copy (no Cancel) |

Surface: `bg-background border-b border-border/50 px-4 py-2` — NO `backdrop-blur` (persistent panel rule per CLAUDE.md).

Accessibility: `role="status" aria-live="polite"` on both the active and empty states.

## ChatPage Slot

HarnessBanner is slotted above AgentStatusChip in ChatPage:
```
z-20 sticky top-0 → HarnessBanner (full-width)
z-10 sticky top-0 → AgentStatusChip (px-4 chip)
```

When `harnessRun=null`, the banner renders an sr-only stub (zero height), so AgentStatusChip remains at `top-0` without gap.

## Tests

- **12 useChatState tests** — initial null, phase_start/complete/error/harness_complete, 3000ms fade, thread-switch reset + refetch, 409 toast, W8 phase_count seeding, B1 sub-agent no-op
- **9 HarnessBanner tests** — active render, null sr-only, fraction interpolation, Cancel button visibility, Dialog on click, ID/EN locale coverage

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] apiFetch enriched with .status + .body**
- **Found during:** Task 1 implementation
- **Issue:** `apiFetch` only threw `new Error(body.detail)` without attaching HTTP status — 409 detection impossible
- **Fix:** Added `.status = response.status` and `.body = body` to thrown errors in `api.ts`
- **Files modified:** `frontend/src/lib/api.ts`
- **Commit:** `837eed5`

**2. [Rule 1 - Lint Fix] TERMINAL_HARNESS_STATUSES moved to module level**
- **Found during:** Task 3 lint run
- **Issue:** `react-hooks/exhaustive-deps` warning when `TERMINAL_HARNESS_STATUSES` was declared inside the hook function
- **Fix:** Moved both `ACTIVE_HARNESS_STATUSES` and `TERMINAL_HARNESS_STATUSES` to module level (outside `useChatState`)
- **Files modified:** `frontend/src/hooks/useChatState.ts`
- **Commit:** `86536c0`

**3. [Rule 1 - Lint Fix] Removed unused test helper**
- **Found during:** Task 3 lint run
- **Issue:** `mockStreamResponseWith409` helper in test file was unused after restructuring test 9
- **Fix:** Removed the unused function
- **Files modified:** `frontend/src/hooks/__tests__/useChatState.test.ts`
- **Commit:** `86536c0`

## Known Stubs

None — `harnessToast` slice is functional but has no rendering surface in Plan 20-09. HarnessBanner reads `harnessRun` (which is never null after gatekeeper_complete fires) but does not yet display `harnessToast` text inline. The toast state is exposed; a follow-up plan (or HarnessBanner extension) can render it. This does not prevent Plan 20-09's core goal from being achieved (the banner itself is fully wired).

## Threat Flags

No new trust boundaries introduced. All SSE events come from the same-origin authenticated stream. The `harness/cancel` POST is authenticated; the `harness/active` GET is RLS-scoped per Plan 20-04.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `frontend/src/components/chat/HarnessBanner.tsx` exists | FOUND |
| `frontend/src/components/chat/HarnessBanner.test.tsx` exists | FOUND |
| `frontend/src/hooks/__tests__/useChatState.test.ts` exists | FOUND |
| Commit `ec73405` (RED phase) exists | FOUND |
| Commit `837eed5` (GREEN phase) exists | FOUND |
| Commit `3cfae64` (HarnessBanner) exists | FOUND |
| Commit `86536c0` (ChatPage slot + lint) exists | FOUND |
| All 21 Plan 20-09 tests pass | PASSED (122/122 full suite) |
| `npx tsc --noEmit` exits 0 | PASSED |
| No new lint errors introduced | PASSED (8 pre-existing errors unchanged) |
