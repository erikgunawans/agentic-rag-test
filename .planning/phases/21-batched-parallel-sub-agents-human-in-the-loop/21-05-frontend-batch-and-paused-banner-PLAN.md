---
phase: 21-batched-parallel-sub-agents-human-in-the-loop
plan: 05
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/hooks/useChatState.ts
  - frontend/src/contexts/ChatContext.tsx
  - frontend/src/components/chat/HarnessBanner.tsx
  - frontend/src/i18n/translations.ts
  - frontend/src/hooks/__tests__/useChatState.batchProgress.test.ts
  - frontend/src/components/chat/__tests__/HarnessBanner.batchProgress.test.tsx
  - frontend/src/components/chat/__tests__/HarnessBanner.paused.test.tsx
autonomous: true
requirements:
  - BATCH-04  # Real-time SSE streaming surfaced to user (frontend half)
  - BATCH-06  # Item-level SSE events drive frontend state
  - HIL-02    # Question streams as chat message; paused state has banner indicator (frontend half)
must_haves:
  truths:
    - "useChatState exposes new `batchProgress: { completed: number; total: number } | null` slice initialized to null."
    - "Reducer arms: `harness_batch_item_start` → seed batchProgress.total from event.items_total (preserve completed if already non-null — protects against resume-replay double-counting); `harness_batch_item_complete` → increment batchProgress.completed; `harness_phase_complete` → reset batchProgress to null."
    - "Thread-switch reset (the existing useEffect that nulls harnessRun) also resets batchProgress to null — mirror the existing pattern."
    - "ChatContext re-exports batchProgress automatically via ReturnType<typeof useChatState> (no manual context type edits needed per memory ID 9472)."
    - "HarnessBanner reads `batchProgress` from useChatContext and appends ' — Analyzing clause N/M' (EN) / ' — Menganalisis klausula N/M' (ID) to the active running title when batchProgress is non-null."
    - "HarnessBanner renders the paused state title 'Awaiting your response — {harnessType}' (EN) / 'Menunggu respons Anda — {harnessType}' (ID) when harnessRun.status === 'paused'."
    - "Cancel button stays visible in paused state (paused IS in ACTIVE_STATUSES) — no behavior change."
    - "i18n keys added: `harness.banner.batchProgress` (interpolating completed/total) and `harness.banner.paused` (interpolating harnessType) — in BOTH ID and EN blocks."
    - "All 14+ Vitest cases pass: 5 useChatState reducer cases (batch_item_start, batch_item_complete, phase_complete clears, thread switch resets, resume-replay preserves completed) + 3 HarnessBanner batch progress cases (null hides, ID renders, EN renders) + 3 HarnessBanner paused cases (ID, EN, cancel button still present)."
  artifacts:
    - path: "frontend/src/hooks/useChatState.ts"
      provides: "batchProgress slice + 3 reducer arms + thread-switch reset"
      contains: "batchProgress"
    - path: "frontend/src/components/chat/HarnessBanner.tsx"
      provides: "batchProgress suffix rendering + paused state title"
      contains: "batchProgress"
    - path: "frontend/src/i18n/translations.ts"
      provides: "harness.banner.batchProgress + harness.banner.paused keys (ID + EN)"
      contains: "harness.banner.batchProgress"
    - path: "frontend/src/components/chat/__tests__/HarnessBanner.batchProgress.test.tsx"
      provides: "3 Vitest cases (null, ID, EN)"
      contains: "harness-banner"
    - path: "frontend/src/components/chat/__tests__/HarnessBanner.paused.test.tsx"
      provides: "3 Vitest cases (ID, EN, cancel button stays)"
      contains: "Awaiting your response"
    - path: "frontend/src/hooks/__tests__/useChatState.batchProgress.test.ts"
      provides: "5 Vitest hook cases (start seeds total, complete increments, phase_complete clears, thread switch resets, resume-replay preserves completed counter)"
      contains: "batchProgress"
  key_links:
    - from: "useChatState SSE handler"
      to: "batchProgress setter"
      via: "harness_batch_item_start / harness_batch_item_complete arms"
      pattern: "harness_batch_item_(start|complete)"
    - from: "HarnessBanner"
      to: "useChatContext.batchProgress"
      via: "title text suffix interpolation"
      pattern: "batchProgress"
    - from: "HarnessBanner"
      to: "harnessRun.status === 'paused'"
      via: "paused-state title selection"
      pattern: "status === 'paused'"
---

<objective>
Add the frontend pieces of Phase 21: a `batchProgress` slice driven by per-item batch SSE events, the HarnessBanner extension that renders the "Analyzing clause N/M" suffix and the paused-state title, and the ID + EN i18n strings that back both. Mirror the Phase 20 `harnessRun` slice / banner pattern verbatim — no new components.

Purpose: Surface BATCH-04/BATCH-06 (real-time per-item progress) and HIL-02 (paused chat-bubble visual cue) to the user. Without this plan, the engine emits the events but the UI silently ignores them.
Output: 3 production file edits + 1 i18n edit + 3 test files (11 cases) — all backend-independent (parallel with Wave 1 backend plan 21-01).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-CONTEXT.md
@.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-PATTERNS.md
@CLAUDE.md
@frontend/src/hooks/useChatState.ts
@frontend/src/contexts/ChatContext.tsx
@frontend/src/components/chat/HarnessBanner.tsx
@frontend/src/i18n/translations.ts
@frontend/src/components/chat/__tests__/PlanPanel.test.tsx

<interfaces>
<!-- Patterns extracted from existing files. -->

From frontend/src/hooks/useChatState.ts:
```typescript
// Lines 24-32 — HarnessRunSlice type (Phase 20)
export type HarnessRunSlice = null | {
  id: string
  harnessType: string
  status: 'pending' | 'running' | 'paused' | 'completed' | 'cancelled' | 'failed'
  currentPhase: number
  phaseCount: number
  phaseName: string
  errorDetail: string | null
}

// Lines ~582-598 — reducer arms for harness_phase_start / harness_phase_complete
} else if (event.type === 'harness_phase_start') {
  setHarnessRun(...)
} else if (event.type === 'harness_phase_complete') {
  setHarnessRun((prev) => prev ? { ...prev, currentPhase: prev.currentPhase + 1 } : prev)
}

// Lines ~233-249 — thread-switch reset useEffect resets harnessRun to null
```

From frontend/src/components/chat/HarnessBanner.tsx (Phase 20):
```typescript
// Lines 67-82 — titleText branching by status
const titleText = isActive
  ? t('harness.banner.running', {
      harnessType: harnessLabel,
      n: String(harnessRun.currentPhase + 1),
      m: String(harnessRun.phaseCount || '?'),
      phaseName: harnessRun.phaseName,
    })
  : isCancelled
  ? t('harness.banner.cancelled', { harnessType: harnessLabel })
  : ...

// Line 29 — ACTIVE_STATUSES includes 'paused'
const ACTIVE_STATUSES: HarnessRunSlice['status'][] = ['pending', 'running', 'paused']
```

From frontend/src/i18n/translations.ts (Phase 20):
```typescript
// Lines 725-735 (ID block):
'harness.banner.running': '{harnessType} berjalan — fase {n} dari {m} ({phaseName})',
'harness.banner.cancelled': '{harnessType} dibatalkan',
'harness.banner.failed': '{harnessType} gagal — {detail}',

// Lines 1466-1477 (EN block):
'harness.banner.running': '{harnessType} running — phase {n} of {m} ({phaseName})',
...
```

From Phase 21 SSE event payloads (engine emits these per Plan 21-03):
```typescript
{ type: 'harness_batch_item_start', harness_run_id, phase_index, phase_name,
  item_index: number, items_total: number, task_id, batch_index }
{ type: 'harness_batch_item_complete', harness_run_id, phase_index, phase_name,
  item_index, items_total, task_id, status: 'ok'|'failed', batch_index }
{ type: 'harness_human_input_required', harness_run_id, question, workspace_output_path }
{ type: 'harness_complete', harness_run_id, status: 'paused' }   // status='paused' is new
```

From frontend/src/components/chat/__tests__/PlanPanel.test.tsx (Phase 17/20 — analog):
- Mock pattern lines 30-50: `vi.mock('@/contexts/ChatContext', () => ({ useChatContext: () => mockChatContext }))`
- Render helper lines 106-111: `<I18nProvider><PlanPanel /></I18nProvider>`
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add batchProgress slice to useChatState + 3 reducer arms + thread-switch reset + 5 hook tests (RED → GREEN)</name>
  <files>frontend/src/hooks/useChatState.ts, frontend/src/hooks/__tests__/useChatState.batchProgress.test.ts</files>
  <read_first>
    - frontend/src/hooks/useChatState.ts — full file. Critical sections: lines 24-32 (HarnessRunSlice type — analog), lines 132 + 788-789 (state declaration + return), lines 233-249 (thread-switch reset useEffect), lines 582-598 (reducer arms for harness_phase_*).
    - frontend/src/contexts/ChatContext.tsx — confirm it uses `ReturnType<typeof useChatState>` for context type (memory ID 9472). If so, NO manual context type edits required.
    - frontend/src/components/chat/__tests__/PlanPanel.test.tsx — Vitest mock pattern + render helper.
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-PATTERNS.md — section "useChatState.ts — `batchProgress` slice (NEW, mirror `harnessRun`)" (lines 444-525) and "useChatState.batchProgress.test.ts" (lines 762-771).
  </read_first>
  <behavior>
    Tests in `frontend/src/hooks/__tests__/useChatState.batchProgress.test.ts`. Use Vitest 3.2; pattern from any existing hook test (e.g. `usePublicSettings.test.ts`).

    - Test 1 `seeds total on harness_batch_item_start`: render hook, dispatch SSE `{type: 'harness_batch_item_start', items_total: 5, item_index: 0}`; assert `result.current.batchProgress?.total === 5` and `completed === 0`.
    - Test 2 `increments completed on harness_batch_item_complete`: dispatch start (total=5), then complete; assert `completed === 1, total === 5`.
    - Test 3 `clears batchProgress on harness_phase_complete`: seed batchProgress, dispatch `{type: 'harness_phase_complete', ...}`; assert `result.current.batchProgress === null`. Verify the existing harnessRun.currentPhase advancement still works (no regression).
    - Test 4 `resets batchProgress on thread switch`: seed batchProgress; change activeThreadId; assert `batchProgress === null` AFTER the effect runs.
    - Test 5 `test_resume_replay_preserves_existing_completed` (WARNING-6 regression): simulate the resume-replay scenario where the SSE stream re-emits batch_item_start during HIL/cancel resume.
      - Sequence: dispatch `harness_batch_item_start{items_total: 15, item_index: 0}` → dispatch 10 successive `harness_batch_item_complete{items_total: 15}` events (so completed reaches 10) → dispatch a SECOND `harness_batch_item_start{items_total: 15, item_index: 10}` (mimics resume replay).
      - Assert: after the second start event, `result.current.batchProgress.completed === 10` (NOT reset to 0) and `result.current.batchProgress.total === 15` (unchanged). This proves the reducer's `completed: prev?.completed ?? 0` logic preserves existing progress when the stream replays.
  </behavior>
  <action>
    Edit `frontend/src/hooks/useChatState.ts`. Three localized blocks:

    **Block 1 — type declaration near line 32 (immediately after `HarnessRunSlice`):**
    ```typescript
    /**
     * Phase 21 / D-09: per-item progress tracking for `llm_batch_agents` phases.
     * Driven by harness_batch_item_start / harness_batch_item_complete SSE events;
     * cleared when harness_phase_complete fires (batch phase finished) or on thread switch.
     */
    export type BatchProgressSlice = null | {
      completed: number
      total: number
    }
    ```

    **Block 2 — useState declaration near line 132 (right after `harnessRun`):**
    ```typescript
    const [batchProgress, setBatchProgress] = useState<BatchProgressSlice>(null)
    ```

    **Block 3 — reducer arms in the SSE event switch.** Locate the `harness_phase_start` / `harness_phase_complete` arms (lines ~582-598). Insert two new arms (BEFORE `harness_phase_complete` so the order is start → complete → phase-boundary):

    ```typescript
    } else if (event.type === 'harness_batch_item_start') {
      setBatchProgress((prev) => ({
        completed: prev?.completed ?? 0,    // WARNING-6 fix: preserve existing
                                            // completed across resume replays
        total: (event.items_total as number) ?? prev?.total ?? 0,
      }))
    } else if (event.type === 'harness_batch_item_complete') {
      setBatchProgress((prev) =>
        prev
          ? { ...prev, completed: prev.completed + 1 }
          : { completed: 1, total: (event.items_total as number) ?? 1 }
      )
    }
    ```

    Extend the existing `harness_phase_complete` arm to also clear batchProgress:
    ```typescript
    } else if (event.type === 'harness_phase_complete') {
      setHarnessRun((prev) => prev ? { ...prev, currentPhase: prev.currentPhase + 1 } : prev)
      setBatchProgress(null)   // Phase 21 D-09: clear batch progress at phase boundary
    }
    ```

    **Block 4 — thread-switch reset.** In the existing useEffect that resets state on `activeThreadId` change (lines 233-249), add:
    ```typescript
    setBatchProgress(null)
    ```
    immediately after the existing `setHarnessRun(null)`.

    **Block 5 — return slot.** Add `batchProgress` and `setBatchProgress` to the hook's return object (lines 788-789 area). The ChatContext already uses `ReturnType<typeof useChatState>` so context type updates automatically (memory ID 9472).

    **Tests** — `frontend/src/hooks/__tests__/useChatState.batchProgress.test.ts`. Pattern: use `renderHook` from `@testing-library/react`, drive SSE events via the same handler that production code uses (likely an exposed `dispatchEvent` or by calling the SSE message handler directly — look at how Phase 19 / Phase 20 hook tests do it).

    For Test 4 (thread switch): use `rerender({ activeThreadId: 'new-id' })` and `waitFor` until the effect ran.

    For Test 5 (WARNING-6 resume-replay regression): drive 12 events in sequence (1 start + 10 complete + 1 start). Assert after the second start that `result.current.batchProgress.completed === 10`.

    Run order:
    1. RED: write tests; `cd frontend && npm test -- src/hooks/__tests__/useChatState.batchProgress.test.ts`. ALL must fail.
    2. GREEN: implement edits. Rerun. ALL must pass.
    3. Confirm no regression: `cd frontend && npm test -- src/hooks/__tests__/useChatState`. (All useChatState tests must pass.)
    4. Type check: `cd frontend && npx tsc --noEmit`. Must exit 0.
  </action>
  <verify>
    <automated>cd frontend && npm test -- src/hooks/__tests__/useChatState.batchProgress.test.ts --run</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "BatchProgressSlice" frontend/src/hooks/useChatState.ts` returns >= 2 (type definition + useState).
    - `grep -c "batchProgress" frontend/src/hooks/useChatState.ts` returns >= 5 (type, state, 2 reducer arms, return, thread-switch reset).
    - `grep -c "harness_batch_item_start" frontend/src/hooks/useChatState.ts` returns >= 1.
    - `grep -c "harness_batch_item_complete" frontend/src/hooks/useChatState.ts` returns >= 1.
    - `grep -c "setBatchProgress(null)" frontend/src/hooks/useChatState.ts` returns >= 2 (phase_complete clear + thread-switch reset).
    - `grep -c "prev?.completed ?? 0" frontend/src/hooks/useChatState.ts` returns >= 1 (WARNING-6 fix — preserves completed counter on resume replay).
    - `cd frontend && npm test -- src/hooks/__tests__/useChatState.batchProgress.test.ts --run` exits 0 with all 5 tests passing (including Test 5 resume-replay regression).
    - `cd frontend && npx tsc --noEmit` exits 0 (no new type errors).
  </acceptance_criteria>
  <done>
    batchProgress slice fully wired into useChatState with reducer arms, phase-boundary clear, thread-switch reset, AND resume-replay preservation of completed counter. 5 tests green; no type errors; no regression on existing useChatState tests.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: HarnessBanner batchProgress suffix + paused state title + i18n keys (ID + EN) + 6 component tests (RED → GREEN)</name>
  <files>frontend/src/components/chat/HarnessBanner.tsx, frontend/src/i18n/translations.ts, frontend/src/components/chat/__tests__/HarnessBanner.batchProgress.test.tsx, frontend/src/components/chat/__tests__/HarnessBanner.paused.test.tsx</files>
  <read_first>
    - frontend/src/components/chat/HarnessBanner.tsx — full file. Critical lines: 29 (ACTIVE_STATUSES), 33 (useChatContext destructure), 67-82 (titleText branching).
    - frontend/src/i18n/translations.ts — find existing `harness.banner.*` keys. Lines 725-735 (ID), 1466-1477 (EN). Match the exact key style and order.
    - frontend/src/components/chat/__tests__/PlanPanel.test.tsx — Vitest mock + render helper analog.
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-PATTERNS.md — sections "HarnessBanner.tsx — extend with batch progress + paused state" (lines 528-577), "i18n/translations.ts — add 3 new keys (ID + EN)" (lines 580-602), "HarnessBanner.batchProgress.test.tsx" (lines 707-749), "HarnessBanner.paused.test.tsx" (lines 753-758).
    - .planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-CONTEXT.md — "Specifics" section bottom, banner text patterns ID/EN.
  </read_first>
  <behavior>
    **`HarnessBanner.batchProgress.test.tsx`** (3 tests):
    - Test 1 `null batchProgress renders no suffix`: `batchProgress=null`, harnessRun running; assert banner contains base running text and does NOT contain "/" character (or any "Analyzing clause" / "Menganalisis klausula" string).
    - Test 2 `batchProgress renders ID-default`: `batchProgress={completed: 3, total: 15}`, harnessRun running; assert banner contains "Menganalisis klausula 3/15".
    - Test 3 `batchProgress renders EN when locale=en`: wrap in `<I18nProvider initialLocale="en">`; assert banner contains "Analyzing clause 3/15".

    **`HarnessBanner.paused.test.tsx`** (3 tests):
    - Test 1 `paused state ID-default`: harnessRun.status='paused', harnessType label rendered; assert banner contains "Menunggu respons Anda — Smoke Echo".
    - Test 2 `paused state EN`: same with locale=en; assert banner contains "Awaiting your response — Smoke Echo".
    - Test 3 `paused keeps cancel button`: paused state; assert `data-testid="harness-banner-cancel"` is in DOM (cancel still visible because 'paused' is in ACTIVE_STATUSES).
  </behavior>
  <action>
    **Edit 1 — i18n/translations.ts.** Add to BOTH locales.

    Indonesian (default) block — near line 727:
    ```typescript
    'harness.banner.batchProgress': 'Menganalisis klausula {completed}/{total}',
    'harness.banner.paused': 'Menunggu respons Anda — {harnessType}',
    ```

    English block — near line 1468:
    ```typescript
    'harness.banner.batchProgress': 'Analyzing clause {completed}/{total}',
    'harness.banner.paused': 'Awaiting your response — {harnessType}',
    ```

    **Edit 2 — HarnessBanner.tsx.**

    Update the destructure to include batchProgress:
    ```typescript
    const { harnessRun, batchProgress, activeThreadId } = useChatContext()
    ```

    Replace the existing `titleText` build with:
    ```typescript
    const isPaused = harnessRun?.status === 'paused'

    const baseTitle = isActive
      ? (isPaused
          ? t('harness.banner.paused', { harnessType: harnessLabel })
          : t('harness.banner.running', {
              harnessType: harnessLabel,
              n: String(harnessRun.currentPhase + 1),
              m: String(harnessRun.phaseCount || '?'),
              phaseName: harnessRun.phaseName,
            }))
      : isCancelled
      ? t('harness.banner.cancelled', { harnessType: harnessLabel })
      : isFailed
      ? t('harness.banner.failed', { harnessType: harnessLabel, detail: harnessRun?.errorDetail ?? '' })
      : ''

    const batchSuffix = batchProgress
      ? ' — ' + t('harness.banner.batchProgress', {
          completed: String(batchProgress.completed),
          total: String(batchProgress.total),
        })
      : ''

    const titleText = baseTitle + batchSuffix
    ```

    The `data-testid="harness-banner"` on the root remains. Cancel button (`data-testid="harness-banner-cancel"`) gating on `isActive` is unchanged — paused IS in ACTIVE_STATUSES so cancel renders correctly.

    **Tests** — create both test files. Mirror PlanPanel.test.tsx mock pattern. The mock context object MUST include `batchProgress` (typed as `BatchProgressSlice` imported from useChatState).

    For Test 3 of paused-banner (cancel still visible), assert `screen.queryByTestId('harness-banner-cancel')` is non-null.

    For locale-en tests, the existing I18nProvider may use a different prop name (`defaultLocale` vs `initialLocale`); match what other tests in the same project use.

    Run order:
    1. RED: write both test files; `cd frontend && npm test -- src/components/chat/__tests__/HarnessBanner --run`. ALL must fail (the new translation keys don't exist yet, paused branch not present).
    2. GREEN: apply translation keys + HarnessBanner edits. Rerun. ALL must pass.
    3. Confirm no regression: `cd frontend && npm test -- src/components/chat/__tests__/HarnessBanner --run`. The pre-existing HarnessBanner.test.tsx (if any) must also still pass.
    4. Type check: `cd frontend && npx tsc --noEmit`.
    5. Lint: `cd frontend && npm run lint`.
    6. Atomic commit (combined with Task 1): `gsd-sdk query commit "feat(21-05): batchProgress slice + HarnessBanner paused/batch UI + i18n" --files frontend/src/hooks/useChatState.ts frontend/src/contexts/ChatContext.tsx frontend/src/components/chat/HarnessBanner.tsx frontend/src/i18n/translations.ts frontend/src/components/chat/__tests__/HarnessBanner.batchProgress.test.tsx frontend/src/components/chat/__tests__/HarnessBanner.paused.test.tsx frontend/src/hooks/__tests__/useChatState.batchProgress.test.ts`.
  </action>
  <verify>
    <automated>cd frontend && npm test -- src/components/chat/__tests__/HarnessBanner.batchProgress.test.tsx src/components/chat/__tests__/HarnessBanner.paused.test.tsx --run</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "harness.banner.batchProgress" frontend/src/i18n/translations.ts` returns >= 2 (one ID, one EN).
    - `grep -c "harness.banner.paused" frontend/src/i18n/translations.ts` returns >= 2 (one ID, one EN).
    - `grep -c "Menganalisis klausula" frontend/src/i18n/translations.ts` returns 1.
    - `grep -c "Analyzing clause" frontend/src/i18n/translations.ts` returns 1.
    - `grep -c "Menunggu respons Anda" frontend/src/i18n/translations.ts` returns 1.
    - `grep -c "Awaiting your response" frontend/src/i18n/translations.ts` returns 1.
    - `grep -c "batchProgress" frontend/src/components/chat/HarnessBanner.tsx` returns >= 2 (destructure + suffix).
    - `grep -c "isPaused" frontend/src/components/chat/HarnessBanner.tsx` returns >= 1.
    - `grep -c "harness.banner.paused" frontend/src/components/chat/HarnessBanner.tsx` returns 1.
    - `grep -c "harness.banner.batchProgress" frontend/src/components/chat/HarnessBanner.tsx` returns 1.
    - `cd frontend && npm test -- src/components/chat/__tests__/HarnessBanner.batchProgress.test.tsx src/components/chat/__tests__/HarnessBanner.paused.test.tsx --run` exits 0 with all 6 tests passing.
    - `cd frontend && npx tsc --noEmit` exits 0.
    - `cd frontend && npm run lint` exits 0.
  </acceptance_criteria>
  <done>
    HarnessBanner displays "Analyzing clause N/M" suffix when batchProgress is active and "Awaiting your response — {harnessType}" title when paused. Both localized in ID and EN. Cancel button stays visible in paused state. 6 component tests + 5 hook tests = 11 frontend tests green. Type check + lint clean.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| SSE event payload → useChatState reducer | trusted same-origin server stream; payload shape validated implicitly via TypeScript |
| translations.ts strings → DOM | static developer-defined strings; no XSS risk via interpolation (numbers + harness type label only) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-21-05-01 | Tampering | malicious item_index / items_total values from forged SSE | accept | SSE stream is same-origin authenticated; backend (Plan 21-03) is the sole producer. items_total / item_index used only for display interpolation; no privileged action gated on them. |
| T-21-05-02 | Information Disclosure | harnessType in paused-banner could leak harness names to non-owners | accept | All UI surfaces are per-thread per-user — only the thread's owner sees the banner; no cross-user exposure. |
| T-21-05-03 | DoS / UI freeze | very large items_total renders giant string | accept | UI shows "N/M" — no rendering complexity scales with M. Backend caps batch sizes via PhaseDefinition.batch_size, not items_total. |
| T-21-05-04 | Tampering | resume replay double-counts completed items | mitigate | Reducer's `completed: prev?.completed ?? 0` preserves existing counter when batch_item_start re-fires during resume. Verified by Test 5. |
</threat_model>

<verification>
- 5 hook tests + 6 component tests = 11 Vitest cases pass.
- `tsc --noEmit` clean.
- `npm run lint` clean.
- ChatContext re-export of batchProgress flows through automatically (memory ID 9472).
- Atomic commit landed.
</verification>

<success_criteria>
Frontend renders real-time batch progress and paused-state banner with full ID/EN i18n, mirroring the Phase 20 pattern. Resume-replay protection verified — replayed batch_item_start does not reset completed counter. No new components introduced. All 11 tests green and type/lint clean.
</success_criteria>

<output>
After completion, create `.planning/phases/21-batched-parallel-sub-agents-human-in-the-loop/21-05-SUMMARY.md`
</output>
</content>
</invoke>