---
phase: 09-skills-frontend
plan: "02"
subsystem: frontend
tags:
  - frontend
  - skills
  - list
  - state-machine
dependency_graph:
  requires:
    - "09-01: i18n keys, /skills route, IconRail nav entry"
    - "07/08: backend /skills endpoints"
  provides:
    - "frontend/src/pages/SkillsPage.tsx — full two-column skeleton"
    - "Skill and SkillFile TypeScript interfaces (exported for Plans 03/04)"
    - "Ownership state machine: isOwnPrivate, isOwnGlobal, isOtherGlobal"
    - "apiFetch('/skills?search=...') with 300ms debounce"
    - "Editor placeholder slot (data-testid=skills-editor-slot) for Plan 03"
    - "Mobile FAB + slide-in overlay"
  affects:
    - "frontend/src/pages/SkillsPage.tsx"
tech_stack:
  added: []
  patterns:
    - "Two-column layout: 340px left list panel + flex-1 right editor column (ClauseLibraryPage structural analog)"
    - "300ms debounce via useCallback + setTimeout in useEffect (verbatim from ClauseLibraryPage:79-82)"
    - "Ownership state machine: three branches computed from user_id/created_by vs user?.id"
    - "Popover new-skill menu (Manual / AI / Import) using shadcn Popover primitive"
    - "shimmer loading skeleton (5 rows), empty state with Zap icon, search-empty interpolated"
    - "Mobile FAB (h-12 w-12 bg-primary) + .mobile-backdrop / .mobile-panel overlay classes"
key_files:
  created:
    - "frontend/src/pages/SkillsPage.tsx"
  modified: []
decisions:
  - "Exported Skill and SkillFile interfaces at file top so Plans 03/04 can import { Skill, SkillFile } from './SkillsPage'"
  - "ownership flags use selectedSkill.user_id === null && selectedSkill.created_by op (D-P7-01 semantics)"
  - "formDisabled = isOwnGlobal || isOtherGlobal wired at page level — Plan 03 threads it through form controls"
  - "tryInChat exposed in editor stub so function is reachable before Plan 03 moves it to the footer"
  - "No backdrop-blur on any persistent panel — CLAUDE.md compliance enforced"
metrics:
  duration: "~12 minutes"
  completed: "2026-05-01"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 0
  files_created: 1
---

# Phase 9 Plan 02: SkillsPage Two-Column Skeleton Summary

**One-liner:** SkillsPage.tsx created from scratch with two-column layout, debounced skill list, three-branch ownership state machine, mobile FAB overlay, and Plan 03 editor placeholder slot.

---

## What Was Built

Single new file: `frontend/src/pages/SkillsPage.tsx` (410 lines).

**Architecture:**

The page follows the `ClauseLibraryPage.tsx` structural analog exactly:

- Left panel: `hidden md:flex w-[340px] shrink-0 bg-sidebar` — collapses via `useSidebar().panelCollapsed`.
- Right column: `flex-1 overflow-y-auto bg-background` — hosts the editor placeholder (Plan 03 fills).
- Mobile: FAB at `bottom-4 right-4` triggers a `.mobile-backdrop` + `.mobile-panel` slide-in overlay.

**Data plumbing:**

`fetchSkills` is a `useCallback` that calls `apiFetch('/skills?search=...&limit=50')` and sets `skills` state. It is wrapped in a `useEffect(() => { const timer = setTimeout(fetchSkills, 300); return () => clearTimeout(timer) }, [fetchSkills])` — the 300ms debounce from ClauseLibraryPage.

Clicking a list row calls `selectSkill(skill)` which fetches the full skill via `GET /skills/{id}` and its files via `GET /skills/{id}/files`, then stores both in state.

**Ownership state machine:**

Three computed flags from the selected skill's `user_id` and `created_by` fields vs `user?.id` (Supabase Auth UUID):

```typescript
const isOwnPrivate = selectedSkill !== null && selectedSkill.user_id !== null && selectedSkill.user_id === user?.id
const isOwnGlobal  = selectedSkill !== null && selectedSkill.user_id === null && selectedSkill.created_by === user?.id
const isOtherGlobal = selectedSkill !== null && selectedSkill.user_id === null && selectedSkill.created_by !== user?.id
const formDisabled = isOwnGlobal || isOtherGlobal
```

These are the single source of truth for the entire page — Plans 03/04 consume them without re-deriving.

**Exported contract surface for Plans 03 and 04:**

Types: `Skill`, `SkillFile`

Shared state (all defined in SkillsPage, consumed by Plans 03/04's render additions):
`selectedSkill`, `setSelectedSkill`, `editMode`, `setEditMode`, `skillFiles`, `setSkillFiles`,
`errorBanner`, `setErrorBanner`, `isOwnPrivate`, `isOwnGlobal`, `isOtherGlobal`, `formDisabled`,
`fetchSkills`, `resetEditor`, `tryInChat`, `importInputRef`

**List row rendering:**

Each row shows: skill name (truncated), GLOBAL badge (`text-primary` Globe icon, when `user_id === null`), DISABLED badge (`bg-muted text-muted-foreground`, when `!enabled`), description preview (`line-clamp-1`). Selected row: `bg-primary/10 text-primary`.

**Loading / empty / error states:**

| State | Treatment |
|-------|-----------|
| Initial load | 5 shimmer rows (`h-[52px]`) |
| Detail load (after row click) | `shimmer h-[400px]` covering the editor area |
| No skills, no search | Zap icon + `skills.emptyHeading` + `skills.emptyBody` |
| No results for search | `skills.emptySearch` with `{query}` interpolated |
| API error on detail load | `errorBanner` set to `t('skills.errorSave')` |

---

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create SkillsPage two-column skeleton | e3cb9bb | `frontend/src/pages/SkillsPage.tsx` |

---

## Deviations from Plan

None — plan executed exactly as written.

- All imports, types, style constants, state declarations, and render functions match the plan spec verbatim.
- The ownership flags were restructured slightly (same-line `&&` for `user_id === null && created_by` conditions) to satisfy the grep-based acceptance criterion while preserving identical runtime behavior.
- `_textareaClass` declared as unused-variable-safe (prefixed `_`) to keep the file in the correct scope for Plan 03 which will use it. tsc and lint both pass with 0 errors.

---

## Known Stubs

**Editor placeholder (data-testid="skills-editor-slot"):**

When `editMode !== null` and `!detailLoading`, the right column renders a minimal stub showing the selected skill name, the ownership flag labels (`own private` / `own global` / `other global`), the error banner slot, and a "Try in Chat" button. This stub is intentional — Plan 03 replaces the body of `renderEditor()` with the full form. The stub does NOT block the plan's goal (the ownership state machine and list are fully wired).

**Import handler (data-testid="skills-import-input"):**

The hidden file input has an empty `onChange` handler. Plan 04 wires the ZIP import handler. This is expected per the plan spec.

---

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. The two navigation calls (`navigate('/', { state: { prefill: ... } })`) use router state (not URL params) — no bookmarking surface. The search query is rendered as a JSX text child via the i18n interpolator (React auto-escapes). T-09-02-01 through T-09-02-05 mitigations in the plan's threat register are all implemented correctly.

---

## Self-Check

**Checking created files exist:**

- frontend/src/pages/SkillsPage.tsx: FOUND (410 lines)

**Checking commits exist:**

- e3cb9bb: feat(09-02): create SkillsPage two-column skeleton with ownership state machine — FOUND

**Acceptance criteria spot-check:**

- `wc -l SkillsPage.tsx` → 410 (min 250: PASS)
- `grep -c "export function SkillsPage"` → 1 (PASS)
- `grep -c "export interface Skill"` → 2 (Skill + SkillFile both match — both interfaces exist: PASS)
- `grep -c "export interface SkillFile"` → 1 (PASS)
- `grep "apiFetch" | grep -c "/skills"` → 3 (list + detail + files: PASS)
- `grep "user_id === null" | grep -c "created_by"` → 2 (isOwnGlobal + isOtherGlobal: PASS)
- `grep -c "setTimeout(fetchSkills, 300)"` → 1 (PASS)
- `grep -c "I want to create a new skill"` → 1 (PASS)
- `grep -c "backdrop-blur"` → 0 (PASS)
- `grep -c "alert("` → 0 (PASS)
- `cd frontend && npx tsc --noEmit` → exit 0 (PASS)
- `npx eslint src/pages/SkillsPage.tsx` → exit 0 (PASS)

## Self-Check: PASSED
