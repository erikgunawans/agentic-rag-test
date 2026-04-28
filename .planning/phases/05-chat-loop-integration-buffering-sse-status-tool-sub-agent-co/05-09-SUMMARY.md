---
phase: 05-chat-loop-integration-buffering-sse-status-tool-sub-agent-co
plan: "09"
gap_closure: true
subsystem: pii-redaction-admin-toggle-frontend
tags: [pii-redaction, admin-ui, gap-closure, frontend]
dependency_graph:
  requires: ["05-08 (backend pii_redaction_enabled column + API)"]
  provides: [admin-toggleable-pii-redaction-via-ui]
  affects: [frontend/src/pages/AdminSettingsPage.tsx, frontend/src/i18n/translations.ts]
tech_stack:
  added: []
  patterns: [controlled-checkbox-PATCH-form, bilingual-i18n]
key_files:
  created: []
  modified:
    - frontend/src/pages/AdminSettingsPage.tsx
    - frontend/src/i18n/translations.ts
decisions:
  - "Master toggle placed at TOP of PII section (before status badges) to communicate that it is the on/off gate for all downstream PII controls"
  - "Default `?? true` matches the DB default (`BOOLEAN NOT NULL DEFAULT TRUE` from migration 032) — undefined-safe rendering during initial load"
  - "Bilingual i18n strings added in both Indonesian (default) and English translation maps to match LexCore's existing i18n discipline"
metrics:
  duration: "~5 minutes"
  completed: "2026-04-28"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 2
  lines_added: 21
---

# Phase 05 Plan 09: Frontend pii_redaction_enabled Toggle (Gap Closure) Summary

## One-liner

Wired the missing frontend toggle for `pii_redaction_enabled` so admins can flip PII redaction on/off from `/admin/settings` without direct API calls — closes the UAT gap from Plan 05-08 which had built only the backend half.

## What Was Built

### Task 1: SystemSettings interface extension

Added `pii_redaction_enabled?: boolean` to the `SystemSettings` TypeScript interface in `AdminSettingsPage.tsx`, with an inline comment marking it as Phase 5 / Plan 05-08 (D-83-toggle).

### Task 2: Master toggle rendered in PII section

Added a controlled checkbox at the top of the `activeSection === 'pii'` block. Layout: section header → master toggle → `<Separator />` → existing status badges and downstream controls. The toggle uses the established controlled-input pattern (`checked={form.pii_redaction_enabled ?? true}`, `onChange={(e) => updateField('pii_redaction_enabled', e.target.checked)}`) so the existing `handleSave` flow picks it up automatically — no save-handler changes needed.

### Task 3: Bilingual i18n strings

Added `admin.pii.redactionEnabled.label` and `admin.pii.redactionEnabled.desc` in both Indonesian and English translation maps. ID label: "Aktifkan redaksi PII" / desc: "Saat nonaktif, pesan diteruskan ke LLM tanpa anonymisasi. Default: aktif." EN label: "Enable PII redaction" / desc: "When off, messages reach the LLM without anonymization. Default: on."

## Test Results

- `npx tsc --noEmit` — exit 0 (no type errors)
- `npm run lint` — no new errors introduced; pre-existing errors in `DocumentsPage.tsx` and `ThemeContext.tsx` are unrelated
- Playwright production verification:
  - Toggle visible at top of PII section ✓
  - Toggle reflects DB value (true by default) ✓
  - React `onChange` fires correctly when clicked via Playwright's accessibility-tree click ✓
  - Save button enables when state is dirty, fires PATCH `/admin/settings`, response 200 ✓
  - Direct API verification confirms `pii_redaction_enabled` writes through to DB (transient cache delay due to `get_system_settings()` 60s TTL is by design) ✓

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1+2+3 | bb467ef | feat(05-09): add pii_redaction_enabled master toggle to admin settings UI |

All three tasks committed as a single coherent change since they form one user-visible surface — splitting the type extension, JSX render, and i18n strings into separate commits would have left the build broken between commits.

## Deviations from Plan

None. Plan executed as specified.

## Known Stubs

None — toggle is fully wired end-to-end (UI ↔ PATCH ↔ DB).

## Threat Surface Scan

No new endpoints, auth boundaries, or data flows. The `PATCH /admin/settings` endpoint already required `super_admin` role (existing RLS gate from Phase 1), and the new field flows through the same `SystemSettingsUpdate` Pydantic model that backed Plan 05-08's other field additions.

## Operator Note

Production frontend deploy required `npx vercel --prod --yes` — `git push origin master:main` alone does not trigger Vercel builds for this project (this is a known operational quirk documented in the user's Vercel deploy memory). The new deployment was promoted to production successfully.

## Self-Check: PASSED

- frontend/src/pages/AdminSettingsPage.tsx — FOUND (contains `pii_redaction_enabled`)
- frontend/src/i18n/translations.ts — FOUND (contains `admin.pii.redactionEnabled.label` in both ID and EN maps)
- Commit bb467ef — FOUND
- Production deployment dpl_CdaFyv525bQ3gbo56vvq2MH4Vb8F — promoted, toggle visible at https://frontend-one-rho-88.vercel.app/admin/settings
