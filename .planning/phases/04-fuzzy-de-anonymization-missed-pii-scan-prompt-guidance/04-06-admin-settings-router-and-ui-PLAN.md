---
phase: 04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance
plan: 06
type: execute
wave: 5
depends_on: [01]
files_modified:
  - backend/app/routers/admin_settings.py
  - frontend/src/pages/AdminSettingsPage.tsx
autonomous: true
requirements_addressed: [DEANON-03]
tags: [pii, admin-ui, fuzzy-deanon, settings-router, react, shadcn]
must_haves:
  truths:
    - "SystemSettingsUpdate Pydantic model accepts new fields fuzzy_deanon_mode (Literal['algorithmic','llm','none'] | None) and fuzzy_deanon_threshold (float | None, ge=0.50, le=1.00) — both optional for partial PATCH"
    - "PATCH /admin/settings persists fuzzy_deanon_mode and fuzzy_deanon_threshold to system_settings via the existing model_dump(exclude_none=True) → upsert path; no new handler logic required"
    - "GET /admin/settings returns the new columns inline with the existing row payload (no schema gate; supabase select returns all columns by default)"
    - "log_action() audit captures fuzzy_deanon_mode + fuzzy_deanon_threshold in changed_fields when admin updates them — auto-included via existing details builder"
    - "AdminSettingsPage 'pii' section gains 2 new form fields: a fuzzy mode <select> (algorithmic/llm/none) + a fuzzy threshold range slider (0.50-1.00, step 0.05) with live numeric display"
    - "Frontend SystemSettings TypeScript interface extended with fuzzy_deanon_mode?: 'algorithmic'|'llm'|'none' and fuzzy_deanon_threshold?: number"
    - "Existing form-state machinery (form/setForm/isDirty/handleSave) auto-handles the new fields — no new state variables needed"
    - "i18n strings added to BOTH translation files (id + en) under admin.pii.fuzzy.{mode|threshold}.{label,algorithmic,llm,none}"
    - "60s system_settings cache (Phase 2 D-21 / SET-01) invalidates on PATCH; admin changes propagate to next chat turn within TTL — no additional plumbing"
  artifacts:
    - path: "backend/app/routers/admin_settings.py"
      provides: "PATCH/GET schema extension for fuzzy_deanon_mode + fuzzy_deanon_threshold"
      contains: "fuzzy_deanon_mode"
    - path: "frontend/src/pages/AdminSettingsPage.tsx"
      provides: "Admin UI form fields for fuzzy mode + threshold inside the existing 'pii' section block"
      contains: "fuzzy_deanon_mode"
  key_links:
    - from: "frontend/src/pages/AdminSettingsPage.tsx"
      to: "backend/app/routers/admin_settings.py:SystemSettingsUpdate"
      via: "PATCH /admin/settings JSON payload (fuzzy_deanon_mode, fuzzy_deanon_threshold)"
      pattern: "fuzzy_deanon_mode"
    - from: "backend/app/routers/admin_settings.py:SystemSettingsUpdate"
      to: "system_settings columns (Plan 04-01 migration 031)"
      via: "supabase upsert via model_dump(exclude_none=True)"
      pattern: "model_dump\\(exclude_none=True\\)"
threat_model:
  trust_boundaries:
    - "Admin user (super_admin role) → PATCH /admin/settings → SystemSettingsUpdate Pydantic validation → supabase upsert (service-role client; RLS bypass via require_admin)"
    - "AdminSettingsPage UI form → fetch PATCH (HTTP) → backend"
  threats:
    - id: "T-04-06-1"
      category: "Tampering (non-admin user PATCHes settings)"
      component: "PATCH /admin/settings endpoint"
      severity: "high"
      disposition: "mitigate"
      mitigation: "Existing route is gated by `require_admin` dependency (Phase 1 baseline; AUTH-02). Non-admin requests are rejected with 403 before reaching the SystemSettingsUpdate model. No change required for this plan; verified by inspecting the router decorator."
    - id: "T-04-06-2"
      category: "Tampering (out-of-range threshold via API bypass)"
      component: "fuzzy_deanon_threshold field"
      severity: "low"
      disposition: "mitigate"
      mitigation: "Defense-in-depth: Pydantic `Field(ge=0.50, le=1.00)` at API layer (returns 422 on out-of-range) + DB CHECK constraint (returns 23514) per Plan 04-01. Both layers reject; this plan adds the API layer."
    - id: "T-04-06-3"
      category: "Tampering (invalid mode enum via API bypass)"
      component: "fuzzy_deanon_mode field"
      severity: "low"
      disposition: "mitigate"
      mitigation: "Pydantic `Literal['algorithmic','llm','none']` at API layer (422 on bad enum) + DB CHECK constraint (23514). Defense-in-depth identical to Phase 3 D-60 for entity_resolution_mode."
    - id: "T-04-06-4"
      category: "Information Disclosure (audit log leaks PII via changed_fields)"
      component: "log_action(details={'changed_fields': ...}) call"
      severity: "low"
      disposition: "accept"
      mitigation: "The new fields contain enum values + bounded floats — no PII. The existing audit-detail builder hashes nothing; it stores raw values. fuzzy_deanon_mode = 'algorithmic'/'llm'/'none' is a public configuration choice, not sensitive. Acceptable per the same risk profile as entity_resolution_mode (Phase 3)."
---

<objective>
Surface the Plan 04-01 migration 031 columns through the admin API + UI so an admin can switch fuzzy mode + threshold from the settings page without redeploy. Ship 2 backend Pydantic field additions + 2 frontend form fields, both inside existing PII surfaces.

Purpose: Plan 04-01 ships the columns; Plan 04-03 reads them via `get_settings()`; this plan closes the loop by making them ADMINISTRATIVELY EDITABLE — required by PROVIDER-06 (configurability via env + admin UI) which is consumed by DEANON-03's runtime gate. Without this plan, Plan 04-01's columns are reachable only via direct DB UPDATE.

Output: 2 files modified. `admin_settings.py` SystemSettingsUpdate gets 2 new optional fields. `AdminSettingsPage.tsx` 'pii' section gets a fuzzy-mode <select> + threshold range slider. i18n strings added to both translation files.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md
@.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md
@.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-01-config-and-migration-031-PLAN.md
@CLAUDE.md
@backend/app/routers/admin_settings.py
@frontend/src/pages/AdminSettingsPage.tsx

<interfaces>
Phase 3 baseline (extend, do NOT replace):

```python
# backend/app/routers/admin_settings.py — Phase 3 D-59 (lines 29-44)
class SystemSettingsUpdate(BaseModel):
    rag_rerank_mode: Literal["none", "llm", "cohere"] | None = None
    entity_resolution_mode: Literal["algorithmic", "llm", "none"] | None = None
    llm_provider: Literal["local", "cloud"] | None = None
    # ... 6 more Phase 3 provider fields ...
    pii_missed_scan_enabled: bool | None = None
    # Phase 4 fields go HERE.
```

```tsx
// frontend/src/pages/AdminSettingsPage.tsx — Phase 3 D-59 (interface near line 22)
interface SystemSettings {
  rag_rerank_mode?: 'none' | 'llm' | 'cohere'
  entity_resolution_mode?: 'algorithmic' | 'llm' | 'none'
  llm_provider?: 'local' | 'cloud'
  // ... 6 more Phase 3 provider fields ...
  pii_missed_scan_enabled?: boolean
  // Phase 4 fields go HERE.
}
```

Existing 'pii' section block (Phase 3 D-59 lines 466-584) already contains an `entity_resolution_mode` <select>. Phase 4 adds 2 more fields inside the same section.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Extend SystemSettingsUpdate with fuzzy_deanon_mode + fuzzy_deanon_threshold (D-67/D-69)</name>
  <files>backend/app/routers/admin_settings.py</files>
  <read_first>
    - backend/app/routers/admin_settings.py (the file being modified — locate `SystemSettingsUpdate` class near line 29; identify the closing line of the existing field block; identify `pii_missed_scan_enabled` for the splice point per PATTERNS.md line 794)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "MODIFIED · backend/app/routers/admin_settings.py" section (lines 786-808)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md decisions D-67 / D-69
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-06-admin-settings-router-and-ui-PLAN.md (Phase 3 analog — same Literal/Field pattern)
    - backend/app/config.py (confirm Phase 4 Plan 04-01 added the fuzzy_deanon_mode + fuzzy_deanon_threshold Settings fields; this task mirrors them at the API surface)
  </read_first>
  <action>
**Step 1 — Confirm `Field` and `Literal` imports** at the top of `admin_settings.py`. Phase 3 already imports them per the existing `Literal`-typed fields. If `Field` is not already imported from `pydantic`, add it:
```python
from pydantic import BaseModel, Field
```

**Step 2 — Append 2 new fields to `SystemSettingsUpdate`** immediately AFTER `pii_missed_scan_enabled: bool | None = None`. The fields MUST be `Optional` (`| None = None`) so the existing partial-PATCH semantics are preserved (`model_dump(exclude_none=True)` filters out unset keys):

```python
class SystemSettingsUpdate(BaseModel):
    # ... existing Phase 3 fields ...
    pii_missed_scan_enabled: bool | None = None   # ← Phase 3 D-57 (existing)

    # Phase 4: Fuzzy de-anonymization (D-67..D-70)
    fuzzy_deanon_mode: Literal["algorithmic", "llm", "none"] | None = None
    fuzzy_deanon_threshold: float | None = Field(default=None, ge=0.50, le=1.00)
```

**Step 3 — DO NOT modify the PATCH handler body.** Per PATTERNS.md line 800-803 the existing handler uses `model_dump(exclude_none=True)` to build the upsert payload — new fields are auto-picked. The audit-trail call `log_action(...)` similarly auto-includes the new fields in `details={'changed_fields': ...}` (the changed_fields are computed from the PATCH payload, not from a hardcoded list). Verify by reading the handler body BEFORE editing — if the handler hardcodes a field whitelist anywhere, add the 2 new field names to it. Otherwise, ZERO handler changes.

**Step 4 — DO NOT modify the GET endpoint.** Per PATTERNS.md line 805-807 the existing `GET /admin/settings` returns the `system_settings` row in full via `client.table('system_settings').select('*')` (or equivalent). New columns from migration 031 (Plan 04-01) appear automatically. Verify by reading the GET handler — if the SELECT explicitly enumerates columns, add `fuzzy_deanon_mode, fuzzy_deanon_threshold` to the column list. Otherwise, ZERO GET changes.

**Constraints**:
- Both new fields are `| None = None` (optional partial-PATCH semantics; Phase 3 D-58 / SET-01 invariant).
- The `Literal` type MUST match Plan 04-01's `Settings.fuzzy_deanon_mode` literal exactly: `("algorithmic", "llm", "none")` in the same order.
- The `Field(ge=0.50, le=1.00)` constraint MUST match Plan 04-01's `Settings.fuzzy_deanon_threshold` Field exactly + the DB CHECK from migration 031 — defense-in-depth per D-60.
- DO NOT reorder or rename any existing field. Append-only.

**Verification (immediate, before Task 2)**:
```bash
cd backend && source venv/bin/activate
python -c "
from app.routers.admin_settings import SystemSettingsUpdate
m = SystemSettingsUpdate(fuzzy_deanon_mode='algorithmic', fuzzy_deanon_threshold=0.90)
assert m.fuzzy_deanon_mode == 'algorithmic'
assert m.fuzzy_deanon_threshold == 0.90
# Out-of-range rejected
try:
    SystemSettingsUpdate(fuzzy_deanon_threshold=0.49)
    raise SystemExit('should have rejected 0.49')
except Exception:
    pass
try:
    SystemSettingsUpdate(fuzzy_deanon_threshold=1.01)
    raise SystemExit('should have rejected 1.01')
except Exception:
    pass
# Bad enum rejected
try:
    SystemSettingsUpdate(fuzzy_deanon_mode='bogus')
    raise SystemExit('should have rejected bogus')
except Exception:
    pass
# Partial PATCH semantics preserved
m_empty = SystemSettingsUpdate()
assert m_empty.fuzzy_deanon_mode is None
assert m_empty.fuzzy_deanon_threshold is None
dump = m_empty.model_dump(exclude_none=True)
assert 'fuzzy_deanon_mode' not in dump
assert 'fuzzy_deanon_threshold' not in dump
print('OK')
"
python -c "from app.main import app; print('main OK')"
pytest tests/ -x --tb=short -q
```
Phase 1+2+3 baseline 79/79 must remain green.
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/backend &amp;&amp; source venv/bin/activate &amp;&amp; python -c "
from app.routers.admin_settings import SystemSettingsUpdate
m = SystemSettingsUpdate(fuzzy_deanon_mode='algorithmic', fuzzy_deanon_threshold=0.90)
assert m.fuzzy_deanon_mode == 'algorithmic' and m.fuzzy_deanon_threshold == 0.90
try: SystemSettingsUpdate(fuzzy_deanon_threshold=0.49); raise SystemExit('bad-low not rejected')
except SystemExit: raise
except Exception: pass
try: SystemSettingsUpdate(fuzzy_deanon_threshold=1.01); raise SystemExit('bad-high not rejected')
except SystemExit: raise
except Exception: pass
try: SystemSettingsUpdate(fuzzy_deanon_mode='bogus'); raise SystemExit('bad-enum not rejected')
except SystemExit: raise
except Exception: pass
m_empty = SystemSettingsUpdate()
assert m_empty.fuzzy_deanon_mode is None and 'fuzzy_deanon_mode' not in m_empty.model_dump(exclude_none=True)
print('OK')
" &amp;&amp; pytest tests/ -x --tb=short -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -cE 'fuzzy_deanon_mode:\s*Literal\["algorithmic",\s*"llm",\s*"none"\]\s*\|\s*None\s*=\s*None' backend/app/routers/admin_settings.py` returns exactly 1.
    - `grep -cE 'fuzzy_deanon_threshold:\s*float\s*\|\s*None\s*=\s*Field\(default=None,\s*ge=0\.50,\s*le=1\.00\)' backend/app/routers/admin_settings.py` returns exactly 1.
    - The new fields are inside the `class SystemSettingsUpdate(BaseModel):` block (not module-scope): `python -c "from app.routers.admin_settings import SystemSettingsUpdate; assert 'fuzzy_deanon_mode' in SystemSettingsUpdate.model_fields; assert 'fuzzy_deanon_threshold' in SystemSettingsUpdate.model_fields; print('OK')"` exits 0.
    - Out-of-range threshold rejected by Pydantic: validation script in `<verify>` exits 0.
    - Invalid mode rejected by Pydantic: same.
    - Partial PATCH semantics preserved: `model_dump(exclude_none=True)` omits unset Phase 4 fields.
    - `pytest tests/ -x --tb=short` exits 0 — Phase 1+2+3 79/79 still green.
    - `python -c "from app.main import app"` succeeds (PostToolUse import-check).
    - No regression: existing fields (`pii_missed_scan_enabled`, `entity_resolution_mode`) still accept their defined types.
  </acceptance_criteria>
  <done>
SystemSettingsUpdate accepts the 2 new fields with the exact validation contract from Plan 04-01. Partial PATCH semantics preserved. Phase 1+2+3 regression suite green.
  </done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Extend AdminSettingsPage with fuzzy mode <select> + threshold slider in the existing 'pii' section</name>
  <files>frontend/src/pages/AdminSettingsPage.tsx</files>
  <read_first>
    - frontend/src/pages/AdminSettingsPage.tsx (the file being modified — locate the `SystemSettings` interface near line 22-44; locate the 'pii' section block near lines 466-584; locate the existing `entity_resolution_mode` <select> around lines 499-513 for pattern mirroring)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-PATTERNS.md "MODIFIED · frontend/src/pages/AdminSettingsPage.tsx" section (lines 919-1001)
    - .planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-CONTEXT.md decisions D-67 / D-69
    - frontend/src/lib/i18n.tsx (or wherever the I18nProvider translation maps live — confirm path before editing) — must be updated for both `id` and `en`
  </read_first>
  <action>
**Step 1 — Extend the `SystemSettings` TypeScript interface.** Locate the interface near line 22-44 and append the 2 new optional fields IMMEDIATELY AFTER `pii_missed_scan_enabled?: boolean`:

```tsx
interface SystemSettings {
  // ... existing Phase 3 fields ...
  pii_missed_scan_enabled?: boolean
  // Phase 4: Fuzzy de-anonymization (D-67..D-70)
  fuzzy_deanon_mode?: 'algorithmic' | 'llm' | 'none'
  fuzzy_deanon_threshold?: number
}
```

The exact union ordering MUST match the backend `Literal["algorithmic", "llm", "none"]` order; field names MUST match snake_case to align with the PATCH payload.

**Step 2 — Add 2 form fields inside the existing 'pii' section block.** Locate the existing `entity_resolution_mode` <select> block (around lines 499-513 per PATTERNS.md). The new fields go AFTER the existing Phase 3 PII fields (after the `entity_resolution_mode` block + the global provider block) and BEFORE any `<Separator />` that closes the section. Place them adjacent to one another (mode then threshold).

Mirror the existing `entity_resolution_mode` <select> styling and the threshold slider's `<input type="range">` per PATTERNS.md:

```tsx
              {/* Phase 4: Fuzzy de-anon mode (D-67) */}
              <div className="space-y-1">
                <label className="text-xs font-medium">{t('admin.pii.fuzzy.mode.label')}</label>
                <select
                  value={form.fuzzy_deanon_mode ?? 'none'}
                  onChange={(e) =>
                    updateField('fuzzy_deanon_mode', e.target.value as 'algorithmic' | 'llm' | 'none')
                  }
                  className={inputClass}
                >
                  <option value="none">{t('admin.pii.fuzzy.mode.none')}</option>
                  <option value="algorithmic">{t('admin.pii.fuzzy.mode.algorithmic')}</option>
                  <option value="llm">{t('admin.pii.fuzzy.mode.llm')}</option>
                </select>
              </div>

              {/* Phase 4: Fuzzy threshold slider (D-69) */}
              <div className="space-y-1">
                <label className="text-xs font-medium">
                  {t('admin.pii.fuzzy.threshold.label')}: {(form.fuzzy_deanon_threshold ?? 0.85).toFixed(2)}
                </label>
                <input
                  type="range"
                  min={0.50}
                  max={1.00}
                  step={0.05}
                  value={form.fuzzy_deanon_threshold ?? 0.85}
                  onChange={(e) =>
                    updateField('fuzzy_deanon_threshold', parseFloat(e.target.value))
                  }
                  className="w-full"
                />
              </div>
```

**Step 3 — DO NOT add any new state variables.** The existing `form` state covers the new fields automatically; the existing `handleSave` PATCHes `form` as-is; the existing `isDirty` check auto-tracks changes. Verify by reading the surrounding form-state machinery BEFORE writing — if any imperative `useEffect`/`setForm` hardcodes a key whitelist, add the 2 new keys.

**Step 4 — Add i18n strings.** Locate the i18n translation files referenced by `I18nProvider` (per the project conventions: typically `frontend/src/lib/i18n.tsx` or `frontend/src/i18n/{id,en}.ts`). Add 5 new keys under `admin.pii.fuzzy`:

For both `id` (Indonesian, default) and `en` (English):
```
admin.pii.fuzzy.mode.label             → "Mode De-anonymization Fuzzy"  (id)  /  "Fuzzy De-anonymization Mode"  (en)
admin.pii.fuzzy.mode.none              → "Nonaktif"  (id)  /  "Disabled"  (en)
admin.pii.fuzzy.mode.algorithmic       → "Algoritmik (Jaro-Winkler)"  (id)  /  "Algorithmic (Jaro-Winkler)"  (en)
admin.pii.fuzzy.mode.llm               → "LLM"  (id)  /  "LLM"  (en)
admin.pii.fuzzy.threshold.label        → "Ambang Kemiripan"  (id)  /  "Match Threshold"  (en)
```

Confirm the actual translation-file shape before editing — Indonesian phrasing should match the LexCore voice already used in adjacent admin.pii.* keys (read existing entries for tone calibration).

**Step 5 — DO NOT modify any other section** of AdminSettingsPage.tsx. Frontend lint hook will run automatically; if it fails, fix lint warnings introduced by your changes only.

**Verification**:
```bash
cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/frontend
npx tsc --noEmit
npm run lint -- src/pages/AdminSettingsPage.tsx
# Optional manual smoke: npm run dev, navigate to /admin/settings, verify the 2 new fields appear inside the PII section and PATCH on change.
```

The two CLI commands MUST exit 0. Pre-existing lint errors in OTHER files (DocumentsPage.tsx per STATE.md) should NOT count — `npm run lint -- src/pages/AdminSettingsPage.tsx` scopes to this file only.

**Constraints**:
- Field names in the React component MUST match the backend snake_case payload (`fuzzy_deanon_mode`, `fuzzy_deanon_threshold`).
- The threshold slider step is `0.05`, range `[0.50, 1.00]` per CONTEXT.md schema_changes section. The backend rejects out-of-range; the slider mechanically prevents it.
- The default display value when `form.fuzzy_deanon_threshold` is undefined MUST be `0.85` (Plan 04-01 default).
- DO NOT add `backdrop-blur` to the new form fields (per CLAUDE.md gotcha — glass is forbidden on persistent panels).
- DO NOT introduce new components beyond standard shadcn/ui + native HTML `<select>` / `<input type="range">` per the existing Phase 3 pattern.
  </action>
  <verify>
    <automated>cd /Users/erikgunawansupriatna/claude-code-agentic-rag-masterclass-1/frontend &amp;&amp; npx tsc --noEmit &amp;&amp; npm run lint -- src/pages/AdminSettingsPage.tsx</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c 'fuzzy_deanon_mode' frontend/src/pages/AdminSettingsPage.tsx` returns ≥ 3 (interface + select value + onChange).
    - `grep -c 'fuzzy_deanon_threshold' frontend/src/pages/AdminSettingsPage.tsx` returns ≥ 3 (interface + slider value + onChange).
    - `grep -c "type=\"range\"" frontend/src/pages/AdminSettingsPage.tsx` returns ≥ 1 (slider added; existing file may already have range inputs from other features — must increase by 1 minimum).
    - `grep -cE "step=\{0\.05\}|step=\"0\.05\"" frontend/src/pages/AdminSettingsPage.tsx` returns ≥ 1 (slider step matches D-69 contract).
    - `grep -c "admin.pii.fuzzy.mode" frontend/src/pages/AdminSettingsPage.tsx` returns ≥ 4 (label + 3 options).
    - `grep -c "admin.pii.fuzzy.threshold.label" frontend/src/pages/AdminSettingsPage.tsx` returns ≥ 1.
    - i18n entries added: `grep -rE "admin.pii.fuzzy.mode.(label|none|algorithmic|llm)" frontend/src/` returns ≥ 5 hits across the translation files (one per key per language file).
    - `cd frontend && npx tsc --noEmit` exits 0 (no TypeScript errors introduced).
    - `cd frontend && npm run lint -- src/pages/AdminSettingsPage.tsx` exits 0 OR only emits warnings unrelated to this file's new fields (pre-existing lint in OTHER files does not count, per STATE.md note).
    - `grep -c 'backdrop-blur' frontend/src/pages/AdminSettingsPage.tsx` does NOT increase compared to baseline (no glass on persistent panels).
    - DOM smoke test (manual / optional): visiting `/admin/settings` shows the 2 new fields inside the existing PII Redaction & Provider section, and changing values triggers `isDirty=true` (Save button enables).
  </acceptance_criteria>
  <done>
AdminSettingsPage 'pii' section now exposes the fuzzy mode dropdown + threshold slider. TypeScript and lint pass. The existing PATCH/GET cycle persists the 2 new fields without backend handler changes.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Admin user (super_admin role) → `PATCH /admin/settings` | HTTP request → `require_admin` dependency → SystemSettingsUpdate Pydantic validation → supabase upsert. RLS bypass via service-role client (admin context). |
| AdminSettingsPage UI form → fetch PATCH → backend | Standard same-origin fetch with admin JWT bearer. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation |
|-----------|----------|-----------|----------|-------------|------------|
| T-04-06-1 | Tampering (non-admin PATCHes settings) | PATCH /admin/settings | high | mitigate | Existing `require_admin` dependency (AUTH-02). Non-admin returns 403 before validation runs. No new gate needed. |
| T-04-06-2 | Tampering (out-of-range threshold via API bypass) | `fuzzy_deanon_threshold` | low | mitigate | Pydantic `Field(ge=0.50, le=1.00)` returns 422 on out-of-range; DB CHECK constraint (Plan 04-01) returns 23514. Two-layer rejection. |
| T-04-06-3 | Tampering (invalid mode enum via API bypass) | `fuzzy_deanon_mode` | low | mitigate | Pydantic `Literal` returns 422 on bad enum; DB CHECK constraint (Plan 04-01) returns 23514. |
| T-04-06-4 | Information Disclosure (audit log leaks) | log_action changed_fields | low | accept | New fields are public configuration enums + bounded float — no PII. Same risk profile as Phase 3 entity_resolution_mode. |

## Cross-plan threats covered elsewhere
- **T-1 (raw PII to cloud LLM):** Plan 04-03 (placeholder-tokenization) + Phase 3 D-53..D-56 (egress filter).
- **T-3 (missed-scan injecting fabricated entity types):** Plan 04-04.
- **T-5 (prompt injection):** Plan 04-05.
</threat_model>

<verification>
- `pytest tests/ -x --tb=short` from `backend/` is green — 79/79 Phase 1+2+3 baseline preserved.
- `python -c "from app.main import app"` succeeds (PostToolUse import-check).
- `cd frontend && npx tsc --noEmit` exits 0.
- `cd frontend && npm run lint -- src/pages/AdminSettingsPage.tsx` exits 0 (or warnings only, none from this plan's new fields).
- Plan 04-07 integration test will exercise PATCH/GET round-trip if needed (or rely on Plan 04-01's live-DB column verification + Plan 04-03's runtime read).
</verification>

<success_criteria>
- D-67 / D-69 admin surface live: SystemSettingsUpdate validates the 2 new fields with the same contract as Settings.
- AdminSettingsPage 'pii' section shows mode dropdown + threshold slider; both PATCH on change.
- TypeScript + lint pass on the modified file.
- 79/79 Phase 1+2+3 regression suite still green.
</success_criteria>

<output>
After completion, create `.planning/phases/04-fuzzy-de-anonymization-missed-pii-scan-prompt-guidance/04-06-SUMMARY.md` capturing: SystemSettingsUpdate field additions, AdminSettingsPage interface + form-field splice locations, i18n keys added (path + language coverage), TypeScript/lint status, and any deviations from the verbatim PATTERNS.md template.
</output>
</content>
