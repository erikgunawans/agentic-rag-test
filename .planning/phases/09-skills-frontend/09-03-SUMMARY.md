---
phase: 09-skills-frontend
plan: 03
subsystem: ui
tags: [react, skills, editor, ownership-matrix, chat-prefill, crud, form]

# Dependency graph
requires:
  - phase: 09-02
    provides: SkillsPage two-column skeleton with ownership state machine, editMode/selectedSkill state
  - phase: 07-skills-database-api-foundation
    provides: POST/PATCH/DELETE /skills, PATCH /skills/{id}/share, GET /skills/{id}/export backend endpoints

provides:
  - Full editor form in SkillsPage with name, description, instructions, license, compatibility fields
  - Ownership-matrix-driven action buttons (Save, Cancel, Delete, Share, Unshare, Export, Try in Chat)
  - CRUD handlers: handleSave, handleDelete, handleShare(makeGlobal), handleExport
  - Inline error banner with role=alert (no window.alert)
  - Live character counters on name (n/64) and description (n/1024) turning red over limit
  - Save button with Loader2 spinner and saving label during flight
  - Inline role=switch enabled toggle
  - ChatPage.tsx useEffect consuming location.state.prefill once (idempotent)

affects:
  - 09-04 (file upload UI — uses data-testid skills-files-section-slot)
  - 09-05 (import handler — uses importInputRef)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Ownership-matrix button gating via isOwnPrivate/isOwnGlobal/isOtherGlobal computed flags
    - formDisabled wrapper with pointer-events-none + per-button pointerEvents:auto overrides
    - Inline role=switch button (no shadcn Switch — not installed) per PATTERNS.md note 1
    - consumedRef guard on useEffect for idempotent prefill consumption (React Strict Mode safe)
    - navigate(pathname, { replace: true, state: null }) to clear route state after prefill send

key-files:
  created: []
  modified:
    - frontend/src/pages/SkillsPage.tsx
    - frontend/src/pages/ChatPage.tsx

key-decisions:
  - "Inline role=switch button instead of shadcn Switch component (not installed in project per PATTERNS.md note 1, choice b)"
  - "Auto-send pattern in ChatPage: call handleSendMessage(prefill) directly vs prefill-into-input — simpler, no MessageInput prop needed"
  - "SkillsPage full implementation was already present in working tree from Plan 02 (skeleton included full form as uncommitted work); Task 1 committed it as part of this plan"

patterns-established:
  - "Location state prefill consumer: useEffect + consumedRef + navigate(replace+null) prevents double-send on hot reload and refresh"
  - "Ownership matrix: isOwnPrivate = user_id !== null && user_id === me; isOwnGlobal = user_id === null && created_by === me; isOtherGlobal = user_id === null && created_by !== me"

requirements-completed: [SKILL-11]

# Metrics
duration: 18min
completed: 2026-05-01
---

# Phase 9 Plan 03: Skills Editor Form + Chat Prefill Summary

**Full CRUD editor form with ownership-matrix action buttons in SkillsPage, and idempotent location.state.prefill consumer in ChatPage powering Try in Chat and Create with AI flows.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-05-01T04:00:00Z
- **Completed:** 2026-05-01T04:18:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- SkillsPage now renders a fully interactive editor form with name (n/64 counter), description (n/1024 counter), instructions (monospace, 240px min-height), license, and compatibility fields
- Ownership matrix correctly gates action buttons: own-private shows Save/Delete/Share/Export/Try in Chat; own-global shows Unshare/Export/Try in Chat; other-global shows Export/Try in Chat only; create mode shows Save/Cancel
- ChatPage consumes location.state.prefill exactly once via consumedRef + navigate-clear pattern, enabling both SkillsPage "Try in Chat" and "Create with AI" navigation flows

## Task Commits

Each task was committed atomically:

1. **Task 1: Editor form with ownership matrix** - `c19dc6c` (feat)
2. **Task 2: ChatPage prefill useEffect** - `1e4c41e` (feat)

**Plan metadata:** committed as part of final docs commit

## Files Created/Modified

- `frontend/src/pages/SkillsPage.tsx` - Added 398 lines: form state (formName/formDescription/formInstructions/formLicense/formCompatibility/formEnabled/saving/deleting/sharing), textareaClass/instructionsClass constants, hydrate useEffect, validateForm(), handleSave/handleDelete/handleShare/handleExport, full renderEditor() form with ownership-matrix action buttons
- `frontend/src/pages/ChatPage.tsx` - Added useLocation, useNavigate, useEffect, useRef; prefill consumer useEffect with consumedRef guard; clears route state after send

## Decisions Made

- **Inline role=switch instead of shadcn Switch**: The `@/components/ui/switch.tsx` component was not confirmed installed. Used `<button role="switch" aria-checked>` inline per PATTERNS.md note 1 choice (b). No new package install required.
- **Auto-send vs prefill-into-input**: ChatPage calls `handleSendMessage(prefill)` directly rather than setting a prefill prop on MessageInput. Confirmed as the cleaner pattern per PATTERNS.md note 4. No changes to MessageInput.tsx needed.
- **SkillsPage Task 1 scope**: The full implementation was present as uncommitted working tree changes at the 86a7ce0 base. This plan committed those changes atomically as Task 1.

## Deviations from Plan

None — plan executed exactly as written. The SkillsPage implementation was already present in the working tree (Plan 02 working tree included the full form before it was committed); Task 1 staged and committed it under this plan's commit format.

## Issues Encountered

None. TypeScript compiled cleanly (zero errors). ESLint passed on both modified files (pre-existing lint errors in unrelated files — UserAvatar, button.tsx, AuthContext, useToolHistory — are out of scope per deviation scope boundary rules).

## Known Stubs

- `data-testid="skills-files-section-slot"` (SkillsPage.tsx line 564): Intentional — files section placeholder reserved for Plan 04 (building block files upload UI). The plan explicitly documents this slot.

This stub does NOT prevent Plan 03's goal from being achieved (create/edit/delete/share/export/try-in-chat flows are fully functional).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 04 can locate the files section slot via `data-testid="skills-files-section-slot"` and insert file upload UI
- Plan 05 can wire the importInputRef onChange for ZIP import
- All ownership matrix logic (isOwnPrivate/isOwnGlobal/isOtherGlobal/formDisabled) is computed and passed correctly
- ChatPage prefill consumer handles both "Try in Chat" (skill-name prefill) and "Create with AI" (literal string) flows

---
*Phase: 09-skills-frontend*
*Completed: 2026-05-01*
