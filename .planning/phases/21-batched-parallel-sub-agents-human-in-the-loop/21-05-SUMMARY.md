---
phase: 21-batched-parallel-sub-agents-human-in-the-loop
plan: 05
subsystem: frontend / chat-state / harness-banner
tags:
  - frontend
  - i18n
  - sse
  - batch
  - hil
  - phase-21
requirements:
  - BATCH-04
  - BATCH-06
  - HIL-02
dependency_graph:
  requires:
    - "Phase 20 / harnessRun slice in useChatState (existing)"
    - "Phase 20 / HarnessBanner.tsx (existing)"
    - "Phase 20 / 'paused' status reserved in CHECK constraint + ACTIVE_STATUSES (existing)"
  provides:
    - "useChatState.batchProgress slice (read by HarnessBanner)"
    - "harness.banner.batchProgress / harness.banner.paused i18n keys (ID + EN)"
    - "HarnessBanner paused-state title + batch progress suffix"
  affects:
    - "frontend chat session render path during llm_batch_agents and llm_human_input phases"
    - "Wave 1 parallel — backend Plan 21-01 emits the SSE events this plan consumes"
tech-stack:
  added: []
  patterns:
    - "Mirror Phase 20 harnessRun reducer-arm + thread-switch-reset pattern for new batchProgress slice"
    - "ChatContext re-export via ReturnType<typeof useChatState> — no manual context type edit (memory ID 9472)"
    - "Vitest 3.2 SSE-stream-driven hook test (mock fetch returns ReadableStream with `data:` lines)"
    - "Preserve-existing-counter reducer arm for resume-replay safety (WARNING-6)"
key-files:
  created:
    - frontend/src/hooks/__tests__/useChatState.batchProgress.test.ts
    - frontend/src/components/chat/__tests__/HarnessBanner.batchProgress.test.tsx
    - frontend/src/components/chat/__tests__/HarnessBanner.paused.test.tsx
  modified:
    - frontend/src/hooks/useChatState.ts
    - frontend/src/components/chat/HarnessBanner.tsx
    - frontend/src/i18n/translations.ts
decisions:
  - "Resume-replay safety: `completed: prev?.completed ?? 0` arm in harness_batch_item_start preserves progress across HIL/cancel resume replays (WARNING-6)."
  - "Thread-switch reset placed in the existing harnessRun reset useEffect (single source of truth for cross-thread cleanup)."
  - "No manual ChatContext.tsx edit — `ReturnType<typeof useChatState>` propagates the new slice automatically (memory ID 9472)."
  - "Paused state reuses harnessRun.status (no new state slot); HarnessBanner branches the title via `isPaused = harnessRun.status === 'paused'`."
metrics:
  duration_minutes: 8
  tasks_completed: 2
  files_changed: 6
  tests_added: 11
  completed_date: 2026-05-04
---

# Phase 21 Plan 05: Frontend Batch Progress + Paused Banner Summary

Wired the per-item batch progress slice (`batchProgress`) into `useChatState`, extended `HarnessBanner` with the paused-state title and the "Analyzing clause N/M" suffix, and shipped the four supporting i18n strings (ID + EN). Backend independence preserved — works alongside Wave 1 backend plan 21-01 without coordination.

## Result

- **5 hook tests + 6 component tests = 11 Vitest cases**, all passing.
- **Type check (`tsc --noEmit`): clean.**
- **Lint on modified files: clean** (the 9 lint errors reported by `npm run lint` are all pre-existing in unrelated files: `useToolHistory.ts`, `I18nContext.tsx`, `ThemeContext.tsx`, `vitest.config.ts` — out of scope per the SCOPE BOUNDARY rule).
- **Single atomic commit** (`21b2bed`) bundles the slice, the SSE reducer arms, the banner edit, the i18n keys, and all 3 test files.

## What Changed

### useChatState.ts

- New `BatchProgressSlice` type (line 42-area).
- New `batchProgress` / `setBatchProgress` state (line ~152).
- Two new SSE reducer arms (`harness_batch_item_start`, `harness_batch_item_complete`).
- Extended `harness_phase_complete` arm to also `setBatchProgress(null)` at phase boundary.
- Thread-switch reset adds `setBatchProgress(null)` next to the existing `setHarnessRun(null)`.
- Both new fields exported from the hook return object.

### HarnessBanner.tsx

- Destructured `batchProgress` alongside `harnessRun` and `activeThreadId` from `useChatContext()`.
- Title text builder now branches on `isPaused = harnessRun.status === 'paused'`:
  - Active + not paused → existing `harness.banner.running` copy.
  - Active + paused → new `harness.banner.paused` copy ("Awaiting your response — Smoke Echo").
  - Cancelled / failed branches unchanged.
- Title gets a `batchSuffix` appended whenever `batchProgress` is non-null:
  ```
  ' — ' + t('harness.banner.batchProgress', { completed, total })
  ```
- Cancel button gating (`isActive`) unchanged — paused remains in `ACTIVE_STATUSES` so the cancel button is still visible during paused state.

### translations.ts

Added 4 new keys (2 in the ID block at line 728-area, 2 in the EN block at line 1469-area):

| Key | ID | EN |
|---|---|---|
| `harness.banner.batchProgress` | `Menganalisis klausula {completed}/{total}` | `Analyzing clause {completed}/{total}` |
| `harness.banner.paused` | `Menunggu respons Anda — {harnessType}` | `Awaiting your response — {harnessType}` |

### Tests

- `useChatState.batchProgress.test.ts` (5 tests) — drives an SSE ReadableStream through the hook's `handleSendMessage` path. Covers: start seeds total, complete increments, phase_complete clears, thread switch resets, and resume-replay preserves the counter.
- `HarnessBanner.batchProgress.test.tsx` (3 tests) — null/ID/EN suffix rendering.
- `HarnessBanner.paused.test.tsx` (3 tests) — ID/EN paused-state title + cancel-button-still-visible regression guard.

## Deviations from Plan

None — plan executed exactly as written. The two tasks were combined into a single atomic commit per the plan's explicit instruction in Task 2's `<action>` step:

> Atomic commit (combined with Task 1): `gsd-sdk query commit "feat(21-05): batchProgress slice + HarnessBanner paused/batch UI + i18n" --files [list]`

(Used `git commit --no-verify` instead of `gsd-sdk query commit` because this is a parallel-worktree executor and pre-commit hook contention with sibling agents must be avoided per `<parallel_execution>`.)

## Verification

| Acceptance criterion | Result |
|---|---|
| `grep -c BatchProgressSlice src/hooks/useChatState.ts >= 2` | 2 ✓ |
| `grep -c harness_batch_item_start src/hooks/useChatState.ts >= 1` | 3 ✓ |
| `grep -c harness_batch_item_complete src/hooks/useChatState.ts >= 1` | 3 ✓ |
| `grep -c "setBatchProgress(null)" src/hooks/useChatState.ts >= 2` | 2 ✓ |
| `grep -c "prev?.completed ?? 0" src/hooks/useChatState.ts >= 1` (WARNING-6 fix) | 2 ✓ |
| `grep -c "harness.banner.batchProgress" src/i18n/translations.ts >= 2` | 2 ✓ |
| `grep -c "harness.banner.paused" src/i18n/translations.ts >= 2` | 2 ✓ |
| `grep -c "Menganalisis klausula" src/i18n/translations.ts == 1` | 1 ✓ |
| `grep -c "Analyzing clause" src/i18n/translations.ts == 1` | 1 ✓ |
| `grep -c "Menunggu respons Anda" src/i18n/translations.ts == 1` | 1 ✓ |
| `grep -c "Awaiting your response" src/i18n/translations.ts == 1` | 1 ✓ |
| `grep -c batchProgress src/components/chat/HarnessBanner.tsx >= 2` | 7 ✓ |
| `grep -c isPaused src/components/chat/HarnessBanner.tsx >= 1` | 2 ✓ |
| `grep -c "harness.banner.paused" src/components/chat/HarnessBanner.tsx == 1` | 1 ✓ |
| `grep -c "harness.banner.batchProgress" src/components/chat/HarnessBanner.tsx == 1` | 1 ✓ |
| `npm test -- src/hooks/__tests__/useChatState.batchProgress.test.ts --run` | 5/5 pass ✓ |
| `npm test -- src/components/chat/__tests__/HarnessBanner.batchProgress.test.tsx src/components/chat/__tests__/HarnessBanner.paused.test.tsx --run` | 6/6 pass ✓ |
| `npx tsc --noEmit` | exit 0 ✓ |
| `npm run lint` (modified files only) | clean ✓ |

## Threat Flags

None. Plan's `<threat_model>` covered all surface; no new network endpoints, auth paths, or trust-boundary changes were introduced. The `items_total` payload value flows only into display interpolation — no privileged action is gated on it (plan threat T-21-05-01 disposition `accept`).

## Self-Check: PASSED

- Files created/modified all exist on disk:
  - frontend/src/hooks/useChatState.ts ✓
  - frontend/src/components/chat/HarnessBanner.tsx ✓
  - frontend/src/i18n/translations.ts ✓
  - frontend/src/hooks/__tests__/useChatState.batchProgress.test.ts ✓
  - frontend/src/components/chat/__tests__/HarnessBanner.batchProgress.test.tsx ✓
  - frontend/src/components/chat/__tests__/HarnessBanner.paused.test.tsx ✓
- Commit `21b2bed` exists in `git log --oneline`.
