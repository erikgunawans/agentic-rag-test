---
phase: 03-entity-resolution-llm-provider-configuration
plan: 06
subsystem: admin-settings + frontend admin UI
tags: [phase-3, admin, pii, llm-provider, i18n, security]
requires:
  - Settings fields from Plan 03-01 (config.py — local_llm_base_url, cloud_llm_api_key, etc.)
  - system_settings columns from Plan 03-02 (migration 030)
  - Existing SystemSettingsUpdate Pydantic model + PATCH /admin/settings handler (pre-Phase-3)
  - Existing AdminSettingsPage section-state machine (activeSection + SECTIONS array)
  - Existing I18nProvider + translations.ts (id/en)
provides:
  - SystemSettingsUpdate extended with 9 Literal-typed Phase 3 fields (D-60)
  - GET /admin/settings/llm-provider-status endpoint (D-58 — masked status badges)
  - 'pii' admin section with mode selector, provider selector, fallback toggle,
    missed-scan toggle, 5 per-feature overrides, 2 status badges
  - 22 admin.pii.* i18n keys in both Indonesian (default) and English
affects:
  - frontend/src/pages/AdminSettingsPage.tsx
  - backend/app/routers/admin_settings.py
  - frontend/src/i18n/translations.ts
tech-stack:
  added: []
  patterns:
    - "Pydantic Literal validation at API edge (D-60 — mirrors rag_rerank_mode)"
    - "Read-only masked status badge from /admin/settings/llm-provider-status (D-58)"
    - "Section state machine extension — single new entry in AdminSection union + SECTIONS array (D-59)"
key-files:
  created: []
  modified:
    - backend/app/routers/admin_settings.py
    - frontend/src/pages/AdminSettingsPage.tsx
    - frontend/src/i18n/translations.ts
decisions:
  - "Used native HTML <select>/<input type=checkbox> rather than shadcn Select/Switch primitives — matches existing AdminSettingsPage idiom (file uses raw form elements + inputClass throughout, never imports from @/components/ui/select)"
  - "PER_FEATURE_OVERRIDES declared as a const array to keep the 5 override selects DRY"
  - "Probe URL is `${local_llm_base_url}/models` (no extra /v1) — local_llm_base_url default already includes /v1 per Plan 03-01 default 'http://localhost:1234/v1'"
  - "httpx is imported lazily inside the endpoint (matches existing tool_service.py pattern)"
  - "piiStatus initial state is null — UI renders 'missing'/'unreachable' badges until status fetch resolves (graceful degradation per D-58 spec)"
metrics:
  duration: ~25 minutes
  tasks_completed: 2
  files_modified: 3
  total_lines_added: 256
  total_lines_removed: 1
  completed: 2026-04-26
---

# Phase 03 Plan 06: Admin Settings Router & UI Summary

Surface Phase 3 PII redaction settings through the admin API + admin UI without introducing a new admin route — extended `SystemSettingsUpdate` with 9 Literal-typed fields (D-60), added the masked `GET /admin/settings/llm-provider-status` endpoint (D-58), and added a new `'pii'` section to `AdminSettingsPage.tsx` (D-59) with all 9 form controls, 2 status badges, and 22 i18n keys in both Indonesian (default) and English.

## Files Modified

| File | Lines Δ | Role |
| ---- | ------- | ---- |
| `backend/app/routers/admin_settings.py` | +45 / 0 | Pydantic model extension + new GET endpoint |
| `frontend/src/pages/AdminSettingsPage.tsx` | +162 / -1 | New `'pii'` section + status fetch + 5 per-feature override selects |
| `frontend/src/i18n/translations.ts` | +50 / 0 | 22 keys × 2 locales (id + en) = 44 lines added (plus blank-line + comment overhead) |

Total: **3 files modified, +256/-1 lines.**

## Commits

| Task | Description | Commit |
| ---- | ----------- | ------ |
| 1    | `feat(03-06): extend SystemSettingsUpdate + add llm-provider-status endpoint` | `2e0014b` |
| 2    | `feat(03-06): add 'pii' section to AdminSettingsPage with status badges + i18n` | `92fa98e` |

## Task 1 — Backend (admin_settings.py)

**SystemSettingsUpdate extended** with 9 new optional Literal-typed fields, all defaulting to `None`:
- `entity_resolution_mode: Literal["algorithmic", "llm", "none"] | None`
- `llm_provider: Literal["local", "cloud"] | None`
- `llm_provider_fallback_enabled: bool | None`
- 5 per-feature overrides: `entity_resolution_llm_provider`, `missed_scan_llm_provider`, `title_gen_llm_provider`, `metadata_llm_provider`, `fuzzy_deanon_llm_provider` (all `Literal["local", "cloud"] | None`)
- `pii_missed_scan_enabled: bool | None` (Phase 4 forward-compat)

The existing PATCH handler picks them up automatically via `model_dump(exclude_none=True)` — **no handler change needed**, and the existing `log_action(action="update", resource_type="system_settings", details={"changed_fields": [...]})` automatically audits the new fields.

**New endpoint**: `GET /admin/settings/llm-provider-status` (gated by `Depends(require_admin)`):
- Returns exactly two booleans: `cloud_key_configured`, `local_endpoint_reachable`
- `cloud_key_configured = bool(settings.cloud_llm_api_key)` — boolean cast only; the raw key is never echoed
- `local_endpoint_reachable` is a 2-second `httpx.AsyncClient` GET probe to `${local_llm_base_url}/models`; any exception → `False` (probe failure never crashes the endpoint)
- `httpx` imported lazily inside the function

### Confirmation: the new GET endpoint NEVER returns the raw cloud key

Source code reference (admin_settings.py L83):
```python
cloud_key_configured = bool(app_settings.cloud_llm_api_key)
```
The variable holds only a boolean. The returned dict (L95–98) has exactly two keys: `cloud_key_configured` and `local_endpoint_reachable`. The raw `cloud_llm_api_key` value never crosses the JSON serialization boundary, never appears in any error message, and is not logged.

### Pydantic Literal validation verified

```python
SystemSettingsUpdate(entity_resolution_mode='bogus')  # raises ValidationError ✓
SystemSettingsUpdate(llm_provider='aws_bedrock')       # raises ValidationError ✓
```

D-60 defense-in-depth at API edge confirmed.

## Task 2 — Frontend (AdminSettingsPage.tsx + translations.ts)

**AdminSection union** extended with `'pii'`. **SECTIONS array** gains one entry: `{ id: 'pii', icon: Shield, labelKey: 'admin.pii.title' }` (Shield icon already imported on L2).

**`SystemSettings` interface** in the page extended with the 9 Phase 3 optional fields (matching Pydantic model exactly).

**New `LlmProviderStatus`** type for the status fetch response.

**New `useEffect`** triggered on `activeSection === 'pii'`: calls `apiFetch('/admin/settings/llm-provider-status')`, sets `piiStatus`. On any error (404, network, etc.) sets both flags to `false` (graceful degradation). Cleanup uses `cancelled` flag.

**Section render block** (`{activeSection === 'pii' && (...)}`) added directly after the `'hitl'` block, containing:

1. Section header (h2 + description from `admin.pii.title` / `admin.pii.description`)
2. **Status badges (D-58)** — cloud-key + local-endpoint, color-coded (green when configured/reachable, red/amber otherwise)
3. **Mode select** — `entity_resolution_mode`: algorithmic / llm / none
4. **Provider select** — `llm_provider`: local / cloud
5. **Fallback checkbox** — `llm_provider_fallback_enabled`
6. **Missed-PII scan checkbox** — `pii_missed_scan_enabled` (Phase 4 forward-compat)
7. **Per-feature overrides** — 5 selects rendered from a `PER_FEATURE_OVERRIDES` const array; each has options Inherit / local / cloud, where `inherit` maps to `null` in the form state (omitted from the PATCH payload)

**Form-element library** — used native HTML `<select>` / `<input type="checkbox">` matching the existing page idiom (the file uses raw form elements with `inputClass`, NOT shadcn Select/Switch primitives). The Separator component (already imported) is used between groups.

**No `backdrop-blur` / glass classes** on the new persistent section. CLAUDE.md design rule honored.

**Save handler** — completely unchanged. Existing `JSON.stringify(form)` automatically includes any newly-set Phase 3 fields; PATCH route accepts them because Task 1 added them to `SystemSettingsUpdate`.

### i18n keys added (22 keys × 2 locales = 44 lines)

| Key | Indonesian | English |
| --- | --- | --- |
| `admin.pii.title` | "Redaksi PII & Penyedia LLM" | "PII Redaction & Provider" |
| `admin.pii.description` | (full sentence) | (full sentence) |
| `admin.pii.mode.label` | "Mode resolusi entitas" | "Entity resolution mode" |
| `admin.pii.mode.algorithmic` | "Algoritmik (Union-Find — default)" | "Algorithmic (Union-Find — default)" |
| `admin.pii.mode.llm` | "LLM (refinement via penyedia)" | "LLM (refinement via provider)" |
| `admin.pii.mode.none` | "Tidak ada (passthrough)" | "None (passthrough)" |
| `admin.pii.provider.label` | "Penyedia LLM global" | "Global LLM provider" |
| `admin.pii.provider.local` | "Lokal (LM Studio / Ollama)" | "Local (LM Studio / Ollama)" |
| `admin.pii.provider.cloud` | "Cloud (OpenAI-kompatibel)" | "Cloud (OpenAI-compatible)" |
| `admin.pii.cloudKey.configured` | "Cloud key terkonfigurasi" | "Cloud key configured" |
| `admin.pii.cloudKey.missing` | "Cloud key TIDAK ADA — mode cloud akan gagal" | "Cloud key MISSING — cloud mode will fail" |
| `admin.pii.localEndpoint.reachable` | "Endpoint lokal terjangkau" | "Local endpoint reachable" |
| `admin.pii.localEndpoint.unreachable` | "Endpoint lokal tidak terjangkau" | "Local endpoint unreachable" |
| `admin.pii.fallback.label` | "Aktifkan fallback antar-penyedia (cloud↔local)" | "Enable cross-provider fallback (cloud↔local)" |
| `admin.pii.missedScan.label` | "Aktifkan secondary missed-PII scan (Phase 4)" | "Enable secondary missed-PII scan (Phase 4)" |
| `admin.pii.overrides.title` | "Override per-fitur" | "Per-feature overrides" |
| `admin.pii.overrides.inherit` | "(warisi global)" | "(inherit global)" |
| `admin.pii.overrides.entityResolution` | "Entity resolution" | "Entity resolution" |
| `admin.pii.overrides.missedScan` | "Missed-PII scan" | "Missed-PII scan" |
| `admin.pii.overrides.titleGen` | "Title generation" | "Title generation" |
| `admin.pii.overrides.metadata` | "Metadata extraction" | "Metadata extraction" |
| `admin.pii.overrides.fuzzyDeanon` | "Fuzzy de-anonymization" | "Fuzzy de-anonymization" |

## Verification Results

### Type-check (`npx tsc --noEmit`)
- **PASS** — zero errors. Worktree had no `node_modules`; symlinked from main repo to run the check.

### Lint (`npm run lint`)
- **10 errors total — all pre-existing, none in files modified by this plan.**
- Affected pre-existing files (out of scope per Rule scope boundary): `DocumentsPage.tsx` (2× set-state-in-effect), `ThemeContext.tsx`, `DocumentCreationPage.tsx`, `AuthContext.tsx`, `useToolHistory.ts`, `I18nContext.tsx`, `UserAvatar.tsx`, `button.tsx`. These are pre-existing as documented in STATE.md; no regression introduced by this plan.

### Backend import (`from app.main import app`)
- **PASS** — when run from worktree against main repo's venv + `.env`. Backend module graph compiles cleanly.

### Pydantic Literal rejection
- **PASS** — `SystemSettingsUpdate(entity_resolution_mode='bogus')` raises `ValidationError` (D-60 verified).
- **PASS** — `SystemSettingsUpdate(llm_provider='aws_bedrock')` raises `ValidationError`.

### Endpoint registration
- **PASS** — router contains route `/admin/settings/llm-provider-status` (verified via `[r.path for r in router.routes]`).

### Plan automated check
- **PASS** — Task 1 verification (full Pydantic + route check) returned `ROUTER_OK`.
- **PASS** — Task 2 verification (12-grep + tsc check) returned `ADMIN_UI_OK`.

## Phase 1 + Phase 2 regression

Did not run full pytest suite from this executor (worktree lacks Supabase test creds in env; running blackbox tests requires `TEST_EMAIL/TEST_PASSWORD` env). The changes here are confined to:
- `admin_settings.py` — adding new fields to a Pydantic optional-field model + adding a new endpoint behind `require_admin`. The PATCH handler signature/body is unchanged.
- `AdminSettingsPage.tsx` — additive: new section behind `activeSection === 'pii'` guard. Existing sections untouched.
- `translations.ts` — additive: new keys appended to the existing key-value dict.

No code path used by existing tests is modified. **Regression risk: minimal.** The existing `pytest tests/ -x` suite (39/39 per earlier phase verification) is unaffected by this plan's changes.

## Plan 03-07 (tests) is now unblocked

Plan 03-07 will write `backend/tests/api/test_resolution_and_provider.py` SC#5, which calls `PATCH /admin/settings` with `llm_provider='cloud'` and asserts the value persists. Both prerequisites — the Pydantic field acceptance + the route registration — are now in place.

## Deviations from Plan

### Auto-fixed Issues

None.

### Implementation choices (Claude's Discretion within plan)

**1. Native HTML form elements instead of shadcn Select/Switch/Badge**
- **Why:** The existing `AdminSettingsPage.tsx` uses ONLY native HTML form elements (`<input type="radio">`, `<input type="checkbox">`, `<input type="number">`) wrapped in the `inputClass` constant. It does NOT import from `@/components/ui/select` or `@/components/ui/switch`. Introducing shadcn primitives mid-page would violate the "match existing convention" guidance in the plan and CLAUDE.md.
- **Effect:** The `'pii'` section uses `<select>` for dropdowns and `<input type="checkbox">` for toggles, with the existing `inputClass` and Separator component for visual cohesion. Status badges are styled `<span>` elements following the existing `admin.hitl.preview` pattern.

**2. Probe URL = `${local_llm_base_url}/models` (no `/v1` suffix)**
- **Why:** `local_llm_base_url` already defaults to `http://localhost:1234/v1` in `config.py` (Plan 03-01). Appending `/models` yields the correct OpenAI-compatible endpoint. The plan's example `LOCAL_LLM_BASE_URL/models` was honored verbatim.

**3. piiStatus initial null → renders "missing"/"unreachable" badges until fetch resolves**
- **Why:** Mirrors graceful-degradation invariant from D-58. If the user sees momentarily-red badges they know the page is loading; once status arrives the badges flip to green if applicable. No spinner needed.

## Threat Flags

None — this plan introduces no new network endpoint surface beyond what was specified in the plan's threat model. The `GET /admin/settings/llm-provider-status` endpoint:
- Is gated by `Depends(require_admin)` (T-AUTH-02 mitigated)
- Returns booleans only — no raw cloud key (T-AUTH-01 mitigated)
- Uses 2-second timeout for local-endpoint probe (T-DOS-01 mitigated)
- Pydantic Literal validation rejects bad enums at API edge (T-CONFIG-01 mitigated, defense-in-depth with DB CHECK from migration 030)

## Self-Check: PASSED

- **Files modified:**
  - `backend/app/routers/admin_settings.py` → FOUND (45 lines added; SystemSettingsUpdate has 9 new fields; GET /admin/settings/llm-provider-status registered)
  - `frontend/src/pages/AdminSettingsPage.tsx` → FOUND (`'pii'` in AdminSection union, SECTIONS array, conditional render block; useEffect for status fetch; 25 references to `admin.pii.*`)
  - `frontend/src/i18n/translations.ts` → FOUND (44 admin.pii.* keys total, 22 in id + 22 in en)
- **Commits:**
  - `2e0014b` (Task 1) → FOUND in `git log`
  - `92fa98e` (Task 2) → FOUND in `git log`
- **Verification:**
  - Type-check: PASS (zero errors)
  - Backend import: PASS
  - Pydantic Literal rejection: PASS
  - Endpoint route registered: PASS
  - Plan Task 1 automated check: ROUTER_OK
  - Plan Task 2 automated check: ADMIN_UI_OK
