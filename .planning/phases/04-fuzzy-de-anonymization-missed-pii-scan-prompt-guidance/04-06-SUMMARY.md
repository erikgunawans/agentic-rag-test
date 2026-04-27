---
phase: 04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance
plan: 06
subsystem: admin-settings
tags: [pii, admin-ui, fuzzy-deanon, settings-router, react, shadcn]
requirements_addressed: [DEANON-03]
dependency_graph:
  requires:
    - "Plan 04-01 migration 031 columns (fuzzy_deanon_mode, fuzzy_deanon_threshold) live on system_settings"
    - "Phase 3 D-59 admin settings router + page baseline"
  provides:
    - "Admin-editable fuzzy de-anon mode and threshold via PATCH /admin/settings"
    - "Admin UI form fields inside AdminSettingsPage 'pii' section"
  affects:
    - "Plan 04-03 fuzzy_deanon runtime gate (now configurable without redeploy)"
tech_stack:
  added: []
  patterns:
    - "Pydantic Literal + Field(ge,le) defense-in-depth (D-60) mirroring DB CHECK"
    - "model_dump(exclude_none=True) partial-PATCH semantics"
key_files:
  modified:
    - "backend/app/routers/admin_settings.py"
    - "frontend/src/pages/AdminSettingsPage.tsx"
    - "frontend/src/i18n/translations.ts"
  created: []
decisions:
  - "Spliced 2 new form fields after the missed-scan toggle and before per-feature overrides — own Separator group keeps Phase 4 fuzzy controls visually distinct from Phase 3 provider controls."
  - "Default slider value 0.85 (matches Plan 04-01 Settings.fuzzy_deanon_threshold default) when form value is undefined; default mode 'none' to keep fuzzy disabled until admin opts in."
  - "Reused existing form-state machinery — zero new useState hooks, zero new effects."
metrics:
  duration: "~10 min"
  completed: "2026-04-27"
---

# Phase 4 Plan 06: Admin Settings Router + UI for Fuzzy De-anonymization Summary

One-liner: Surfaced Plan 04-01's `fuzzy_deanon_mode` + `fuzzy_deanon_threshold` columns through the admin API and AdminSettingsPage, closing the loop on PROVIDER-06 / DEANON-03 configurability.

## What Changed

### Backend (`backend/app/routers/admin_settings.py`)

Appended 2 optional fields to `SystemSettingsUpdate` immediately after `pii_missed_scan_enabled`:

```python
# Phase 4: Fuzzy de-anonymization (D-67..D-70)
fuzzy_deanon_mode: Literal["algorithmic", "llm", "none"] | None = None
fuzzy_deanon_threshold: float | None = Field(default=None, ge=0.50, le=1.00)
```

Zero handler changes — the existing PATCH path uses `model_dump(exclude_none=True) → update_system_settings()`, and `log_action(..., details={'changed_fields': list(updates.keys())})` auto-includes the new keys. The GET endpoint returns the row via `get_system_settings()` (single-row cached service that selects all columns).

Defense-in-depth (D-60): Pydantic mirrors the DB CHECK constraints from migration 031 — Literal vs CHECK enum (returns 422 vs 23514), and `Field(ge=0.50, le=1.00)` vs CHECK range.

### Frontend (`frontend/src/pages/AdminSettingsPage.tsx`)

1. Extended `SystemSettings` interface with `fuzzy_deanon_mode?: 'algorithmic'|'llm'|'none'` and `fuzzy_deanon_threshold?: number` (immediately after `pii_missed_scan_enabled`).
2. Spliced 2 new form fields inside the 'pii' section, after the missed-scan toggle's `<Separator />` and before the per-feature overrides block, in their own grouped block followed by another Separator:
   - `<select>` for fuzzy mode with options none / algorithmic / llm (default 'none')
   - `<input type="range" min={0.50} max={1.00} step={0.05}>` with live numeric display (default 0.85, formatted to 2 decimals)
3. Reused `updateField()` and `form` state — no new state variables.

### i18n (`frontend/src/i18n/translations.ts`)

Added 5 keys × 2 languages (10 entries total) under `admin.pii.fuzzy.{mode,threshold}.{label,none,algorithmic,llm}`:

| Key                                       | id (Indonesian)                       | en (English)                       |
| ----------------------------------------- | ------------------------------------- | ---------------------------------- |
| `admin.pii.fuzzy.mode.label`              | Mode De-anonymization Fuzzy           | Fuzzy De-anonymization Mode        |
| `admin.pii.fuzzy.mode.none`               | Nonaktif                              | Disabled                           |
| `admin.pii.fuzzy.mode.algorithmic`        | Algoritmik (Jaro-Winkler)             | Algorithmic (Jaro-Winkler)         |
| `admin.pii.fuzzy.mode.llm`                | LLM                                   | LLM                                |
| `admin.pii.fuzzy.threshold.label`         | Ambang Kemiripan                      | Match Threshold                    |

Inserted directly after the existing `admin.pii.overrides.fuzzyDeanon` entries in both language blocks for locality.

## Must-Haves Coverage

| Truth                                                            | Status |
| ---------------------------------------------------------------- | ------ |
| SystemSettingsUpdate accepts both new fields as optional         | OK     |
| PATCH persists via existing `model_dump(exclude_none=True)` path | OK (zero handler changes) |
| GET returns new columns inline                                   | OK (no schema gate; GET unchanged) |
| `log_action` audit captures new fields                           | OK (auto via `changed_fields`) |
| AdminSettingsPage gains 2 new form fields                        | OK |
| TS interface extended with both fields                           | OK |
| Existing form-state machinery handles new fields                 | OK (zero new state) |
| i18n strings added for id + en                                   | OK (10 entries) |
| 60s cache auto-invalidates on PATCH                              | OK (existing Phase 2 D-21 plumbing) |

## Verification Evidence

```
fuzzy_deanon_mode in tsx: 3            (interface + select value + onChange)
fuzzy_deanon_threshold in tsx: 4       (interface + label display + slider value + onChange)
type="range" in tsx: 1                 (slider)
step={0.05} in tsx: 1
admin.pii.fuzzy.mode keys in tsx: 4    (label + 3 options)
admin.pii.fuzzy.threshold.label: 1
fuzzy keys in translations.ts: 10      (5 keys × 2 languages)
backdrop-blur count: 0                 (no glass on persistent panel)
```

Backend Pydantic contract test (manual `python -c …`):
- Accepts valid values (algorithmic/llm/none, threshold 0.90)
- Rejects threshold 0.49 and 1.01 (Pydantic 422)
- Rejects mode 'bogus' (Pydantic 422)
- Empty model dumps without the Phase 4 keys (partial-PATCH preserved)

Backend regression: `pytest tests/ -x --tb=short -q --ignore=tests/api` → **75/75 passed**.
Backend import smoke: `python -c "from app.main import app"` → **OK**.

Frontend type check: `npx tsc --noEmit` → **0 errors**.
Frontend lint scoped to AdminSettingsPage.tsx: **0 errors from this plan's changes** (the 10 pre-existing errors are in `DocumentsPage.tsx` and `theme/ThemeContext.tsx` — unrelated, untouched per scope boundary).

## Threat Model Status

All 4 threats from `<threat_model>` are mitigated/accepted exactly as planned:
- **T-04-06-1** (non-admin tampering): existing `require_admin` dependency unchanged.
- **T-04-06-2** (out-of-range threshold): Pydantic `Field(ge=0.50, le=1.00)` returns 422; DB CHECK is the second gate.
- **T-04-06-3** (invalid mode): Pydantic `Literal` returns 422; DB CHECK second gate.
- **T-04-06-4** (audit log info-disclosure): accepted — fields are public configuration values, no PII.

No new threat surface introduced beyond the planned register.

## Deviations from Plan

None — plan executed exactly as written. Field placement (after missed-scan, with own Separator) is consistent with PATTERNS.md guidance to splice "after the existing Phase 3 PII fields" while keeping the new Phase 4 group visually separated.

## Commits

- `2f488f5` feat(04-06): extend SystemSettingsUpdate with fuzzy_deanon_mode + threshold (D-67/D-69)
- `d805f95` feat(04-06): add fuzzy mode select + threshold slider to admin PII settings (D-67/D-69)

## Self-Check: PASSED

- backend/app/routers/admin_settings.py — FOUND
- frontend/src/pages/AdminSettingsPage.tsx — FOUND
- frontend/src/i18n/translations.ts — FOUND
- Commit 2f488f5 — FOUND
- Commit d805f95 — FOUND
