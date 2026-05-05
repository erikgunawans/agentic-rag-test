---
phase: 22-contract-review-harness-docx-deliverable
plan: 11
subsystem: ui
tags: [react, typescript, vitest, i18n, sse, usechatstate, messageview, workspacepanel]

dependency_graph:
  requires:
    - phase: 22-03
      provides: workspace_updated SSE re-emit from post_execute hook
    - phase: 22-10
      provides: DOCX post_execute writes file with source='harness'; harness_artifact + summary_complete events emitted
  provides:
    - WorkspaceFile.source 'harness' union member (useChatState.ts + database.types.ts)
    - HarnessArtifactEvent + SummaryCompleteEvent + widened WorkspaceUpdatedEvent in SSEEvent union
    - Message.harness_run_id / harness_mode / harness_artifact correlation fields
    - useChatState reducer for summary_complete (was UNHANDLED) + harness_artifact deterministic correlation
    - MessageView DOCX download chip (data-testid=harness-docx-chip) + fallback note (harness-docx-fallback)
    - WorkspacePanel SOURCE_COLORS harness entry (green badge)
    - FLAT i18n keys for harness.docx.* + workspace.source.harness in id+en translation blocks
  affects:
    - ChatPage (reads updated useChatState events)
    - WorkspacePanel (new harness source badge)
    - MessageView (new chip below assistant messages)

tech-stack:
  added: []
  patterns:
    - "REVIEW #8 deterministic correlation: summary_complete tags message with harness_run_id; harness_artifact locates that message"
    - "5-second pendingArtifacts queue for artifact-before-summary_complete event order"
    - "FLAT i18n key style in translations.ts (no locales/*.json files)"
    - "CLAUDE.md Glass rule enforced: no backdrop-blur on persistent download chip"

key-files:
  created:
    - frontend/src/components/chat/__tests__/MessageView.harness-artifact.test.tsx
  modified:
    - frontend/src/lib/database.types.ts
    - frontend/src/hooks/useChatState.ts
    - frontend/src/components/chat/MessageView.tsx
    - frontend/src/components/chat/WorkspacePanel.tsx
    - frontend/src/i18n/translations.ts

key-decisions:
  - "REVIEW #8: summary_complete handler tags message by assistant_message_id; harness_artifact finds it by harness_run_id — no timing heuristics"
  - "pendingArtifacts useRef Map queues artifacts for 5s if summary_complete arrives first (edge case)"
  - "WorkspaceFile.source widened in both useChatState.ts (WorkspaceFile type) and database.types.ts (WorkspaceUpdatedEvent) for consistency"
  - "REVIEW #11: translations.ts is the single source of truth for i18n (FLAT keys); locales/*.json files do not exist and must not be created"
  - "Download chip uses solid border+bg (no backdrop-blur) per CLAUDE.md Glass rule for persistent panels"

requirements-completed: [CR-08, DOCX-08]

duration: ~25min
completed: 2026-05-05
---

# Phase 22 Plan 11: Frontend File Card and Workspace Source Summary

**SSE correlation plumbing wired end-to-end: summary_complete tags the assistant message, harness_artifact attaches the DOCX chip deterministically by harness_run_id, WorkspacePanel badges harness files in green, and all strings have ID+EN parity in translations.ts**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-05T19:00:00Z
- **Completed:** 2026-05-05T19:05:00Z
- **Tasks:** 5
- **Files modified:** 5 (1 created)

## Accomplishments

- Closed REVIEW #8: summary_complete SSE event (previously UNHANDLED) now tags assistant messages with harness_run_id + harness_mode; harness_artifact reducer locates the correct message deterministically
- Closed REVIEW #11: all new strings land in translations.ts FLAT key style (no locales/*.json files created)
- WorkspaceFile.source type widened to include 'harness' across both WorkspaceFile and WorkspaceUpdatedEvent types
- MessageView renders DOCX download chip (rel=noopener noreferrer, no backdrop-blur) and fallback note when DOCX generation fails
- 6 Vitest tests pass covering chip, fallback, a11y, security attrs, and race-condition correlation

## Task Commits

1. **Task 1: SSEEvent + Message + WorkspaceFile type extensions** - `f33bc2c` (feat)
2. **Task 2: useChatState reducer for summary_complete + harness_artifact** - `e870808` (feat)
3. **Task 3: MessageView download chip + fallback note** - `9884d60` (feat)
4. **Task 4: WorkspacePanel SOURCE_COLORS + i18n keys** - `72f1ef0` (feat)
5. **Task 5: Vitest coverage** - `d3ed2cf` (test)

## Files Created/Modified

- `frontend/src/lib/database.types.ts` - Added HarnessArtifactEvent, SummaryCompleteEvent; widened WorkspaceUpdatedEvent.source; extended Message with harness_run_id/harness_mode/harness_artifact fields
- `frontend/src/hooks/useChatState.ts` - Widened WorkspaceFile.source; added pendingArtifacts ref; added summary_complete + harness_artifact reducer cases
- `frontend/src/components/chat/MessageView.tsx` - Added DOCX chip + fallback note IIFE after ask_user block; added FileText, Download, AlertCircle lucide imports
- `frontend/src/components/chat/WorkspacePanel.tsx` - Added harness: 'bg-green-500/20 text-green-300' to SOURCE_COLORS
- `frontend/src/i18n/translations.ts` - Added harness.docx.downloadAriaLabel, fallbackAriaLabel, fallbackDefault and workspace.source.harness in both id + en blocks
- `frontend/src/components/chat/__tests__/MessageView.harness-artifact.test.tsx` - 6 Vitest tests (all passing)

## Decisions Made

- Used `pendingArtifacts.current` (useRef Map) for the arrival-order queue — avoids triggering re-renders and survives thread switch without stale closure issues
- WorkspaceFile.source widened in BOTH useChatState.ts (WorkspaceFile type) AND database.types.ts (WorkspaceUpdatedEvent) for type consistency across all consumers
- Chip uses `<a download>` with `target="_blank" rel="noopener noreferrer"` — browser handles the Supabase signed URL natively; no fetch needed (T-22-11-02 mitigated)
- Download chip has solid border+bg and NO backdrop-blur — persistent UI element, CLAUDE.md Glass rule strictly enforced

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

`DeepModeToggle.test.tsx` (7 tests) was already failing before this plan's work — pre-existing issue unrelated to 22-11 changes. Verified by running the test against the base commit. Not in scope per deviation scope boundary rule.

## Known Stubs

None. The harness DOCX chip renders real Supabase signed URLs from the harness_artifact SSE event payload. The fallback note renders real backend-supplied fallback_message text.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| T-22-11-02 mitigated | MessageView.tsx | rel="noopener noreferrer" prevents window.opener disclosure via signed URL |

## Self-Check: PASSED

- All 5 modified files exist on disk
- Commits f33bc2c, e870808, 9884d60, 72f1ef0, d3ed2cf all present in git log
- `npx tsc --noEmit` exits 0 (no new type errors)
- 6 Vitest tests pass for MessageView.harness-artifact
- `ls frontend/src/i18n/locales/ 2>/dev/null` exits non-zero (no locales dir — REVIEW #11 anti-regression pass)
- `grep -c "harness_artifact" database.types.ts useChatState.ts MessageView.tsx` returns 4+8+1 = 13 total (>= 5: pass)
- `grep -c "summary_complete" useChatState.ts` returns 6 (>= 1: pass)

---
*Phase: 22-contract-review-harness-docx-deliverable*
*Completed: 2026-05-05*
