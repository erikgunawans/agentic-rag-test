---
phase: 09-skills-frontend
plan: "01"
subsystem: frontend
tags:
  - frontend
  - i18n
  - navigation
  - routing
dependency_graph:
  requires:
    - "08-04: skills router and file endpoints (backend)"
  provides:
    - "nav.skills translation key in both id and en locales"
    - "/skills route registered under AuthGuard AppLayout"
    - "Zap icon Skills nav entry in IconRail standaloneItems"
  affects:
    - "frontend/src/i18n/translations.ts (all consumers of t('nav.skills') and t('skills.*'))"
    - "frontend/src/components/layout/IconRail.tsx (nav rendering)"
    - "frontend/src/App.tsx (route tree)"
tech_stack:
  added: []
  patterns:
    - "Flat i18n key appended to both locale maps with section comment separator"
    - "standaloneItems[] array extension for new nav entries"
    - "AppLayout child route registration for new pages"
key_files:
  created: []
  modified:
    - "frontend/src/i18n/translations.ts"
    - "frontend/src/components/layout/IconRail.tsx"
    - "frontend/src/App.tsx"
decisions:
  - "nav.skills translates to 'Skills' (en) and 'Skill' (id) per UI-SPEC Copywriting Contract"
  - "Skills nav entry inserted between Chat (/) and Dashboard in standaloneItems — D-P9-03"
  - "Zap icon used for Skills nav — D-P9-02"
  - "/skills route not wrapped in AdminGuard — any authenticated user can access (T-09-01-03)"
  - "Forward dependency on SkillsPage.tsx (Plan 02) accepted; tsc error expected until Plan 02 ships"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-01"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 3
  files_created: 0
---

# Phase 9 Plan 01: Skills Navigation & Translation Scaffolding Summary

**One-liner:** Wired Skills into the app's navigation, routing, and i18n layer with 56-key translation block covering both Indonesian and English locales.

---

## What Was Built

Three surgical, additive patches establish the foundation that Plans 02–04 depend on:

1. **`frontend/src/i18n/translations.ts`** — Added 56-key `skills.*` block plus `nav.skills` to both the `id` and `en` locale maps. Keys cover all user-facing strings for the Skills page: CTAs, empty states, banners (global/owner-global), all error messages, file preview labels, and import progress/summary strings. Strings inserted after `clauseLibrary.allRisks` in both locale maps with `// Skills (Phase 9)` section comment.

2. **`frontend/src/components/layout/IconRail.tsx`** — Added `Zap` to the `lucide-react` import and inserted `{ path: '/skills', icon: Zap, labelKey: 'nav.skills' }` into `standaloneItems[]` between the Chat (`/`) and Dashboard entries. The existing rendering loop and `railButtonClass` handle active-state styling (purple stripe) automatically.

3. **`frontend/src/App.tsx`** — Added `import { SkillsPage } from '@/pages/SkillsPage'` (alphabetically after SettingsPage) and registered `<Route path="skills" element={<SkillsPage />} />` under the AppLayout parent, between `clause-library` and `compare`. No AdminGuard — backend RLS is the authoritative gate (T-09-01-03 mitigated at route level by AuthGuard).

---

## Task Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add Phase 9 translation block | ec7f093 | `frontend/src/i18n/translations.ts` |
| 2 | Add Skills standalone nav entry to IconRail | 41b9562 | `frontend/src/components/layout/IconRail.tsx` |
| 3 | Register /skills route in App.tsx | f39c502 | `frontend/src/App.tsx` |

---

## Deviations from Plan

None — plan executed exactly as written.

- All translation strings copied verbatim from UI-SPEC §Copywriting Contract.
- Insertion positions matched exactly (after `clauseLibrary.allRisks` in both locale maps).
- Zap icon, `/skills` path, and `nav.skills` labelKey used as specified.
- No `end: true` on Skills nav entry (correct — only `'/'` index route needs it).

---

## Known Stubs

None — this plan adds no UI components or data rendering. Translation keys are fully populated values, not placeholders. `SkillsPage.tsx` import in App.tsx is a forward dependency (Plan 02 creates the file), not a stub.

---

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced by this plan. All three modifications are static frontend configuration (i18n strings, nav array, route declaration). Threat register items T-09-01-01 through T-09-01-04 remain at the same disposition as planned.

---

## Self-Check

**Checking modified files exist:**

- frontend/src/i18n/translations.ts: exists (modified)
- frontend/src/components/layout/IconRail.tsx: exists (modified)
- frontend/src/App.tsx: exists (modified)

**Checking commits exist:**

- ec7f093: feat(09-01): add Phase 9 Skills translation block — FOUND
- 41b9562: feat(09-01): add Skills standalone nav entry to IconRail — FOUND
- f39c502: feat(09-01): register /skills route in App.tsx — FOUND

**Acceptance criteria spot-check:**

- `grep -c "'nav.skills':" translations.ts` → 2 (one per locale)
- `grep -c "'skills.bannerOwnerGlobal':" translations.ts` → 2
- `grep -c "Zap" IconRail.tsx` → 2 (import + standaloneItems)
- `grep -c "path: '/skills'" IconRail.tsx` → 1
- `/skills` entry order: after `'/'`, before `/dashboard` — CONFIRMED
- `grep -c 'path="skills"' App.tsx` → 1
- Route after clause-library, before compare — CONFIRMED
- AdminGuard around skills: 0 — CONFIRMED

## Self-Check: PASSED
