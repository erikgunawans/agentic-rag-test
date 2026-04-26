---
phase: 03-entity-resolution-llm-provider-configuration
plan: 06
type: execute
wave: 4
depends_on: [02]
files_modified:
  - backend/app/routers/admin_settings.py
  - frontend/src/pages/AdminSettingsPage.tsx
autonomous: true
requirements_addressed: [PROVIDER-06, PROVIDER-07, RESOLVE-01]
must_haves:
  truths:
    - "SystemSettingsUpdate Pydantic model gains 9 new optional fields (1 mode + 1 global provider + 1 fallback toggle + 5 per-feature overrides + 1 missed-scan toggle) — D-60"
    - "All new fields use Literal types matching the DB CHECK enums exactly (algorithmic/llm/none, local/cloud) — D-60"
    - "GET /admin/settings/llm-provider-status endpoint returns {cloud_key_configured: bool, local_endpoint_reachable: bool} — D-58; never returns the raw cloud key"
    - "AdminSettingsPage gains a 'pii' section in SECTIONS array; new conditional render block for activeSection === 'pii' — D-59"
    - "i18n strings under admin.pii.* added to both Indonesian and English translation files"
    - "Existing log_action audit on PATCH /admin/settings auto-covers the new fields via changed_fields — no new audit code needed"
    - "No DB column for cloud_llm_api_key in this plan (or any other) — D-58 invariant"
  artifacts:
    - path: "backend/app/routers/admin_settings.py"
      provides: "SystemSettingsUpdate extended with Phase 3 fields + new GET /admin/settings/llm-provider-status endpoint"
      contains: "entity_resolution_mode"
    - path: "frontend/src/pages/AdminSettingsPage.tsx"
      provides: "New 'pii' section in admin UI with mode + provider + per-feature overrides + status badges"
      contains: "admin.pii"
  key_links:
    - from: "backend/app/routers/admin_settings.py"
      to: "system_settings columns added in migration 030"
      via: "SystemSettingsUpdate.model_dump(exclude_none=True) → update_system_settings(updates)"
      pattern: "update_system_settings\\(updates\\)"
    - from: "frontend/src/pages/AdminSettingsPage.tsx"
      to: "PATCH /admin/settings"
      via: "existing save handler dispatches new pii fields automatically once added to form state"
      pattern: "PATCH"
    - from: "backend/app/routers/admin_settings.py"
      to: "backend/app/services/audit_service.log_action"
      via: "existing changed_fields audit log"
      pattern: "log_action\\("
---

<objective>
Surface the Phase 3 settings columns through the admin API + admin UI. Extend the existing `SystemSettingsUpdate` Pydantic model with the 9 new fields (D-60 Literal-typed); add the `GET /admin/settings/llm-provider-status` endpoint (D-58 — masked status badge backing); add the `'pii'` section to `AdminSettingsPage.tsx` (D-59 — one section in an existing section-state machine, NOT a new admin route).

Purpose: Wave 4 (parallel with Plan 03-04). Closes SC#5 — admin can switch `LLM_PROVIDER` and per-feature overrides from `/admin/settings`; changes propagate within the existing 60s `system_settings` cache TTL without redeploy.

Output: Two file modifications. Backend: `admin_settings.py` (~35 new lines = 9 Pydantic fields + 1 endpoint). Frontend: `AdminSettingsPage.tsx` (~120 new lines = SECTIONS entry + section block) + i18n strings.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md
@.planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md
@CLAUDE.md
@backend/app/routers/admin_settings.py
@backend/app/dependencies.py
@backend/app/services/system_settings_service.py
@backend/app/services/audit_service.py
@backend/app/config.py
@frontend/src/pages/AdminSettingsPage.tsx

<interfaces>
<!-- Existing primitives this plan extends. Read once; no codebase exploration needed. -->

From backend/app/routers/admin_settings.py (current shape — Phase 3 EXTENDS, doesn't replace):
- Imports: `from typing import Literal`, `from fastapi import APIRouter, Depends`, `from pydantic import BaseModel, Field`.
- Auth dep: `from app.dependencies import require_admin`.
- Service deps: `from app.services.audit_service import log_action`, `from app.services.system_settings_service import get_system_settings, update_system_settings`.
- Existing model:
  ```python
  class SystemSettingsUpdate(BaseModel):
      # ... existing fields like rag_rerank_mode: Literal["none", "llm", "cohere"] | None = None
  ```
- Existing PATCH handler (paraphrased):
  ```python
  @router.patch("/settings")
  async def patch_settings(payload: SystemSettingsUpdate, user: dict = Depends(require_admin)):
      updates = payload.model_dump(exclude_none=True)
      if updates:
          await update_system_settings(updates)
          log_action(
              user_id=user["id"], user_email=user["email"],
              action="update", resource_type="system_settings",
              details={"changed_fields": list(updates.keys())},
          )
      return {"updated": list(updates.keys())}
  ```
  The `model_dump(exclude_none=True)` automatically picks up the new fields once they're added to `SystemSettingsUpdate` — no PATCH-handler change needed.

From backend/app/dependencies.py:
- `require_admin` dep (used unchanged for the new GET endpoint).

From backend/app/config.py (Plan 03-01 Task 1 output):
- `settings.cloud_llm_api_key: str` (D-58 — env-only; admin UI shows masked badge).
- `settings.local_llm_base_url: str` (used for the local-endpoint reachability probe).

From frontend/src/pages/AdminSettingsPage.tsx (current shape — Phase 3 EXTENDS):
- Existing `type AdminSection = 'llm' | 'embedding' | 'rag' | 'tools' | 'hitl'`.
- Existing `const SECTIONS: { id: AdminSection; icon: typeof Brain; labelKey: string }[]`.
- Existing `useState<AdminSection>('llm')` initial value.
- Existing pattern: each section block is a `{activeSection === '<id>' && (<section>...</section>)}`.
- Existing form-element library: shadcn/ui Label + Select + Input + Switch + Badge — DO NOT introduce new primitives.
- Existing i18n: `I18nProvider` + `t('admin.<section>.<key>')`. Indonesian default + English variant.

Phase 3 contract — D-59 + D-58:
- Admin can set `entity_resolution_mode` (3 options), `llm_provider` (2 options), `llm_provider_fallback_enabled` (toggle), `pii_missed_scan_enabled` (toggle), and 5 per-feature overrides (each: Inherit / local / cloud).
- The cloud key status is read-only badge fed by `GET /admin/settings/llm-provider-status`.
- Save → existing PATCH /admin/settings → update_system_settings → cache invalidation → next call (within 60s TTL) reads new value.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Extend SystemSettingsUpdate + add GET /admin/settings/llm-provider-status to admin_settings.py</name>
  <files>backend/app/routers/admin_settings.py</files>
  <read_first>
    - backend/app/routers/admin_settings.py (current shape — read the FULL file before editing; locate the SystemSettingsUpdate model body and the existing PATCH handler)
    - backend/app/dependencies.py (require_admin dependency signature)
    - backend/app/services/system_settings_service.py (no changes needed — existing get_system_settings + update_system_settings carry the new columns once Plan 03-02 applied)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md D-58, D-59, D-60
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"backend/app/routers/admin_settings.py"
  </read_first>
  <action>
Open `backend/app/routers/admin_settings.py`. Read the FULL file. Identify the `SystemSettingsUpdate(BaseModel)` class and the existing `Literal[...]`-typed field for `rag_rerank_mode` — that's the exact pattern Phase 3 mirrors (D-60).

**Step 1** — Confirm `from typing import Literal` is already present at the top of the file (it must be, since `rag_rerank_mode: Literal[...]` exists). If not, ADD it.

**Step 2** — Add the 9 new fields to the `SystemSettingsUpdate` class. Insert them AFTER all existing fields (preserving alphabetical or grouped order — match the file's existing convention).

Append the following block to the body of `class SystemSettingsUpdate(BaseModel)`:
```python
    # Phase 3: Entity resolution mode + global LLM provider (D-60)
    entity_resolution_mode: Literal["algorithmic", "llm", "none"] | None = None
    llm_provider: Literal["local", "cloud"] | None = None
    llm_provider_fallback_enabled: bool | None = None

    # Phase 3: Per-feature provider overrides (None = inherit global) (D-51)
    entity_resolution_llm_provider: Literal["local", "cloud"] | None = None
    missed_scan_llm_provider: Literal["local", "cloud"] | None = None
    title_gen_llm_provider: Literal["local", "cloud"] | None = None
    metadata_llm_provider: Literal["local", "cloud"] | None = None
    fuzzy_deanon_llm_provider: Literal["local", "cloud"] | None = None

    # Phase 4 forward-compat (column shipped in Phase 3 to avoid migration churn)
    pii_missed_scan_enabled: bool | None = None
```

Field-naming MUST match the migration-030 column names AND the Settings-class field names from Plan 03-01 EXACTLY (case-sensitive). The `model_dump(exclude_none=True)` in the PATCH handler automatically picks these up — no handler change needed.

**Step 3** — Add the `GET /admin/settings/llm-provider-status` endpoint AFTER the existing PATCH handler. This endpoint is the backing for the D-58 masked status badges in the admin UI.

Append:
```python
@router.get("/settings/llm-provider-status")
async def get_llm_provider_status(user: dict = Depends(require_admin)) -> dict:
    """D-58: masked status badge for cloud key + local-endpoint reachability.

    NEVER returns the raw cloud key. Returns booleans only:
      - cloud_key_configured: True iff settings.cloud_llm_api_key has any value.
      - local_endpoint_reachable: True iff GET LOCAL_LLM_BASE_URL/models returns 2xx.
    """
    from app.config import get_settings
    import asyncio
    import httpx

    settings = get_settings()
    cloud_key_configured = bool(settings.cloud_llm_api_key)

    local_endpoint_reachable = False
    probe_url = f"{settings.local_llm_base_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(probe_url)
            local_endpoint_reachable = 200 <= resp.status_code < 300
    except Exception:
        # Probe failure → reachable=False; never crash the endpoint.
        local_endpoint_reachable = False

    return {
        "cloud_key_configured": cloud_key_configured,
        "local_endpoint_reachable": local_endpoint_reachable,
    }
```

Hard rules (verify after editing):
- The endpoint returns ONLY booleans — NEVER `cloud_llm_api_key` itself, NEVER the first N chars of the key, NEVER any error message that might echo the key.
- The `httpx` import is local to the function (lazy) so import-time of this module doesn't pull httpx unnecessarily for non-admin paths.
- The probe timeout is short (2s) so the admin page doesn't hang on a missing local endpoint.
- The endpoint is gated by `require_admin` — anonymous / non-admin users get 403.
- No new env var is read; the values come from `settings.cloud_llm_api_key` (D-58 env-only) and `settings.local_llm_base_url` (Plan 03-01 Task 1).

After editing, run the import check:
```bash
cd backend && source venv/bin/activate && python -c "from app.routers.admin_settings import router, SystemSettingsUpdate; m = SystemSettingsUpdate(entity_resolution_mode='algorithmic'); assert m.entity_resolution_mode == 'algorithmic'; m2 = SystemSettingsUpdate(llm_provider='local'); assert m2.llm_provider == 'local'; print('ROUTER_OK')"
```

Test the Pydantic Literal rejection (D-60 defense in depth at API edge):
```bash
cd backend && source venv/bin/activate && python -c "
from app.routers.admin_settings import SystemSettingsUpdate
from pydantic import ValidationError
try:
    SystemSettingsUpdate(entity_resolution_mode='bogus')
    print('PYDANTIC_LITERAL_BROKEN')
except ValidationError:
    print('PYDANTIC_LITERAL_OK')
"
```
Expected: `PYDANTIC_LITERAL_OK`.
  </action>
  <verify>
    <automated>cd backend && source venv/bin/activate && python -c "
from app.routers.admin_settings import router, SystemSettingsUpdate
from pydantic import ValidationError
m = SystemSettingsUpdate(entity_resolution_mode='algorithmic', llm_provider='local', llm_provider_fallback_enabled=False)
assert m.entity_resolution_mode == 'algorithmic'
assert m.llm_provider == 'local'
assert m.llm_provider_fallback_enabled is False
m2 = SystemSettingsUpdate(entity_resolution_llm_provider='cloud', missed_scan_llm_provider='local')
assert m2.entity_resolution_llm_provider == 'cloud'
m3 = SystemSettingsUpdate(pii_missed_scan_enabled=True)
assert m3.pii_missed_scan_enabled is True
try:
    SystemSettingsUpdate(entity_resolution_mode='bogus')
    raise SystemExit('PYDANTIC_LITERAL_BROKEN')
except ValidationError:
    pass
try:
    SystemSettingsUpdate(llm_provider='aws_bedrock')
    raise SystemExit('PYDANTIC_LITERAL_BROKEN')
except ValidationError:
    pass
routes = [r.path for r in router.routes]
assert '/settings/llm-provider-status' in routes, f'endpoint missing; routes={routes}'
print('ROUTER_OK')
" 2>&1 | grep -q "ROUTER_OK"</automated>
  </verify>
  <acceptance_criteria>
    - `backend/app/routers/admin_settings.py` `SystemSettingsUpdate` class contains literal `entity_resolution_mode: Literal["algorithmic", "llm", "none"] | None = None`.
    - Class contains literal `llm_provider: Literal["local", "cloud"] | None = None`.
    - Class contains literal `llm_provider_fallback_enabled: bool | None = None`.
    - Class contains 5 per-feature override fields (`entity_resolution_llm_provider`, `missed_scan_llm_provider`, `title_gen_llm_provider`, `metadata_llm_provider`, `fuzzy_deanon_llm_provider`), each typed `Literal["local", "cloud"] | None = None`.
    - Class contains `pii_missed_scan_enabled: bool | None = None`.
    - `Pydantic ValidationError` raised on `SystemSettingsUpdate(entity_resolution_mode='bogus')`.
    - File contains `@router.get("/settings/llm-provider-status")` decorator on a function.
    - The endpoint function signature includes `user: dict = Depends(require_admin)`.
    - The endpoint body contains `cloud_key_configured = bool(settings.cloud_llm_api_key)`.
    - The endpoint body contains an `httpx.AsyncClient` probe with a `timeout=2.0` argument.
    - The returned dict has exactly two keys: `cloud_key_configured`, `local_endpoint_reachable`.
    - The endpoint NEVER references `settings.cloud_llm_api_key` outside the boolean cast (no string echo).
    - `from app.routers.admin_settings import router` returns a router whose routes include `/settings/llm-provider-status`.
  </acceptance_criteria>
  <done>SystemSettingsUpdate extended with 9 fields; new GET endpoint shipped; Pydantic Literal validation enforced at API edge; backend imports cleanly.</done>
</task>

<task type="auto" tdd="false">
  <name>Task 2: Add 'pii' section to AdminSettingsPage.tsx with form fields + status badges + i18n</name>
  <files>frontend/src/pages/AdminSettingsPage.tsx</files>
  <read_first>
    - frontend/src/pages/AdminSettingsPage.tsx (read the FULL file — locate the AdminSection union type, the SECTIONS array, the existing `'rag'` section block as the canonical Literal-typed Select reference, the form-state shape, the save handler that calls PATCH /admin/settings, and the i18n key conventions)
    - frontend/src/pages/AdminSettingsPage.tsx — find the i18n provider import and the corresponding translation file paths (likely `frontend/src/i18n/id.ts` + `frontend/src/i18n/en.ts` or similar — adapt the paths to whatever the project uses)
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-CONTEXT.md D-58, D-59
    - .planning/phases/03-entity-resolution-llm-provider-configuration/03-PATTERNS.md §"frontend/src/pages/AdminSettingsPage.tsx"
    - CLAUDE.md "Glass / `backdrop-blur` is FORBIDDEN on persistent panels" (admin sections are persistent — no glass)
  </read_first>
  <action>
Open `frontend/src/pages/AdminSettingsPage.tsx`. Read the FULL file. The page is a section-state machine; Phase 3 D-59 adds EXACTLY three things:

**Step 1** — Extend the `AdminSection` union type. Locate:
```tsx
type AdminSection = 'llm' | 'embedding' | 'rag' | 'tools' | 'hitl'
```
Replace with:
```tsx
type AdminSection = 'llm' | 'embedding' | 'rag' | 'tools' | 'hitl' | 'pii'
```

**Step 2** — Add a `SECTIONS` entry. Locate the array and append:
```tsx
{ id: 'pii' as const, icon: Shield, labelKey: 'admin.pii.title' },
```
Add the `Shield` import from `lucide-react` if not already present (next to the existing `Brain`, `Database`, `Settings2`, `Wrench`, `ShieldCheck` imports).

**Step 3** — Add the section render block AFTER the existing `{activeSection === 'hitl' && (...)}` block. The form fields map to the new SystemSettingsUpdate Pydantic fields from Task 1 (D-60 type alignment).

The form fields:
1. **Mode** — `entity_resolution_mode` — Select with three options: `algorithmic` / `llm` / `none`.
2. **Global provider** — `llm_provider` — Select with two options: `local` / `cloud`.
3. **Fallback** — `llm_provider_fallback_enabled` — Switch.
4. **5 per-feature override Selects** — each with three options: `(inherit)` / `local` / `cloud`. Field names: `entity_resolution_llm_provider`, `missed_scan_llm_provider`, `title_gen_llm_provider`, `metadata_llm_provider`, `fuzzy_deanon_llm_provider`. The "(inherit)" UI-state corresponds to the API field value `null` / `undefined` (omitted from PATCH payload).
5. **Cloud-key status badge** — read-only — bound to `cloud_key_configured` from `GET /admin/settings/llm-provider-status`.
6. **Local-endpoint status badge** — read-only — bound to `local_endpoint_reachable` from the same endpoint.
7. **Missed-PII secondary scan** — `pii_missed_scan_enabled` — Switch (Phase 4 consumes; surface now to avoid UI churn).

Use the existing form-element primitives — Label + Select + Input + Switch + Badge from shadcn/ui. NO new primitives.

State + status fetch pattern (mirror the existing `'rag'` section's data flow):

```tsx
const [piiStatus, setPiiStatus] = useState<{ cloud_key_configured: boolean; local_endpoint_reachable: boolean } | null>(null)

useEffect(() => {
  if (activeSection !== 'pii') return
  let cancelled = false
  fetch('/admin/settings/llm-provider-status', { credentials: 'include' })
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => { if (!cancelled && data) setPiiStatus(data) })
    .catch(() => { if (!cancelled) setPiiStatus({ cloud_key_configured: false, local_endpoint_reachable: false }) })
  return () => { cancelled = true }
}, [activeSection])
```

Place this near the existing `useEffect` blocks. (If the existing fetch wrapper uses `apiClient` / `axios` instead of `fetch`, mirror THAT — match the page's existing convention.)

The section block (high-level shape — adapt the JSX to the project's existing class-name conventions and label/help patterns):

```tsx
{activeSection === 'pii' && (
  <section className="space-y-4">
    <h2 className="text-xl font-semibold">{t('admin.pii.title')}</h2>
    <p className="text-sm text-muted-foreground">{t('admin.pii.description')}</p>

    {/* Mode */}
    <div className="space-y-2">
      <Label>{t('admin.pii.mode.label')}</Label>
      <Select
        value={settings.entity_resolution_mode ?? 'algorithmic'}
        onValueChange={(v) => updateSetting('entity_resolution_mode', v)}
      >
        <SelectTrigger><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="algorithmic">{t('admin.pii.mode.algorithmic')}</SelectItem>
          <SelectItem value="llm">{t('admin.pii.mode.llm')}</SelectItem>
          <SelectItem value="none">{t('admin.pii.mode.none')}</SelectItem>
        </SelectContent>
      </Select>
    </div>

    {/* Global provider */}
    <div className="space-y-2">
      <Label>{t('admin.pii.provider.label')}</Label>
      <Select
        value={settings.llm_provider ?? 'local'}
        onValueChange={(v) => updateSetting('llm_provider', v)}
      >
        <SelectTrigger><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="local">{t('admin.pii.provider.local')}</SelectItem>
          <SelectItem value="cloud">{t('admin.pii.provider.cloud')}</SelectItem>
        </SelectContent>
      </Select>
    </div>

    {/* Status badges (D-58) */}
    <div className="flex flex-wrap gap-2">
      {piiStatus !== null && piiStatus.cloud_key_configured ? (
        <Badge variant="secondary">{t('admin.pii.cloudKey.configured')}</Badge>
      ) : (
        <Badge variant="destructive">{t('admin.pii.cloudKey.missing')}</Badge>
      )}
      {piiStatus !== null && piiStatus.local_endpoint_reachable ? (
        <Badge variant="secondary">{t('admin.pii.localEndpoint.reachable')}</Badge>
      ) : (
        <Badge variant="outline">{t('admin.pii.localEndpoint.unreachable')}</Badge>
      )}
    </div>

    {/* Fallback */}
    <div className="flex items-center justify-between">
      <Label>{t('admin.pii.fallback.label')}</Label>
      <Switch
        checked={!!settings.llm_provider_fallback_enabled}
        onCheckedChange={(v) => updateSetting('llm_provider_fallback_enabled', v)}
      />
    </div>

    {/* Missed-PII secondary scan */}
    <div className="flex items-center justify-between">
      <Label>{t('admin.pii.missedScan.label')}</Label>
      <Switch
        checked={!!settings.pii_missed_scan_enabled}
        onCheckedChange={(v) => updateSetting('pii_missed_scan_enabled', v)}
      />
    </div>

    {/* Per-feature overrides */}
    <h3 className="text-lg font-medium pt-4">{t('admin.pii.overrides.title')}</h3>
    {[
      { field: 'entity_resolution_llm_provider', labelKey: 'admin.pii.overrides.entityResolution' },
      { field: 'missed_scan_llm_provider', labelKey: 'admin.pii.overrides.missedScan' },
      { field: 'title_gen_llm_provider', labelKey: 'admin.pii.overrides.titleGen' },
      { field: 'metadata_llm_provider', labelKey: 'admin.pii.overrides.metadata' },
      { field: 'fuzzy_deanon_llm_provider', labelKey: 'admin.pii.overrides.fuzzyDeanon' },
    ].map(({ field, labelKey }) => (
      <div key={field} className="space-y-2">
        <Label>{t(labelKey)}</Label>
        <Select
          value={(settings as Record<string, unknown>)[field] as string ?? 'inherit'}
          onValueChange={(v) => updateSetting(field, v === 'inherit' ? null : v)}
        >
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="inherit">{t('admin.pii.overrides.inherit')}</SelectItem>
            <SelectItem value="local">{t('admin.pii.provider.local')}</SelectItem>
            <SelectItem value="cloud">{t('admin.pii.provider.cloud')}</SelectItem>
          </SelectContent>
        </Select>
      </div>
    ))}
  </section>
)}
```

NB — the exact prop names of `Select`, `Switch`, `Badge`, `Label` and the wrapper class names depend on the project's shadcn/ui shim. Match the EXACT patterns used in the existing `'rag'` section. The above is a structural template; refine surface details to match the page's visual conventions. NO `backdrop-blur` / glass classes (CLAUDE.md design rule for persistent panels).

**Step 4** — Add i18n strings. Locate the project's translation files. The exact paths depend on the project; common conventions:
- `frontend/src/i18n/id.ts` and `frontend/src/i18n/en.ts`, OR
- `frontend/src/i18n/locales/{id,en}.json`, OR
- Inline under `I18nProvider`.

Add these keys to BOTH the Indonesian (default) AND English files. Use the existing `admin.llm.*` / `admin.rag.*` blocks as the structural template (mirror the same nesting depth and key style).

Required key set — Indonesian:
```
admin.pii.title = "Redaksi PII & Penyedia LLM"
admin.pii.description = "Konfigurasi mode resolusi entitas dan penyedia LLM auxiliary (entity resolution, missed-PII scan, fuzzy de-anon, title generation, metadata)."
admin.pii.mode.label = "Mode resolusi entitas"
admin.pii.mode.algorithmic = "Algoritmik (Union-Find — default)"
admin.pii.mode.llm = "LLM (refinement via penyedia)"
admin.pii.mode.none = "Tidak ada (passthrough)"
admin.pii.provider.label = "Penyedia LLM global"
admin.pii.provider.local = "Lokal (LM Studio / Ollama)"
admin.pii.provider.cloud = "Cloud (OpenAI-kompatibel)"
admin.pii.cloudKey.configured = "Cloud key terkonfigurasi"
admin.pii.cloudKey.missing = "Cloud key TIDAK ADA — mode cloud akan gagal"
admin.pii.localEndpoint.reachable = "Endpoint lokal terjangkau"
admin.pii.localEndpoint.unreachable = "Endpoint lokal tidak terjangkau"
admin.pii.fallback.label = "Aktifkan fallback antar-penyedia (cloud↔local)"
admin.pii.missedScan.label = "Aktifkan secondary missed-PII scan (Phase 4)"
admin.pii.overrides.title = "Override per-fitur"
admin.pii.overrides.inherit = "(warisi global)"
admin.pii.overrides.entityResolution = "Entity resolution"
admin.pii.overrides.missedScan = "Missed-PII scan"
admin.pii.overrides.titleGen = "Title generation"
admin.pii.overrides.metadata = "Metadata extraction"
admin.pii.overrides.fuzzyDeanon = "Fuzzy de-anonymization"
```

Required key set — English (mirror structure):
```
admin.pii.title = "PII Redaction & Provider"
admin.pii.description = "Configure entity-resolution mode and the auxiliary LLM provider (entity resolution, missed-PII scan, fuzzy de-anon, title generation, metadata)."
admin.pii.mode.label = "Entity resolution mode"
admin.pii.mode.algorithmic = "Algorithmic (Union-Find — default)"
admin.pii.mode.llm = "LLM (refinement via provider)"
admin.pii.mode.none = "None (passthrough)"
admin.pii.provider.label = "Global LLM provider"
admin.pii.provider.local = "Local (LM Studio / Ollama)"
admin.pii.provider.cloud = "Cloud (OpenAI-compatible)"
admin.pii.cloudKey.configured = "Cloud key configured"
admin.pii.cloudKey.missing = "Cloud key MISSING — cloud mode will fail"
admin.pii.localEndpoint.reachable = "Local endpoint reachable"
admin.pii.localEndpoint.unreachable = "Local endpoint unreachable"
admin.pii.fallback.label = "Enable cross-provider fallback (cloud↔local)"
admin.pii.missedScan.label = "Enable secondary missed-PII scan (Phase 4)"
admin.pii.overrides.title = "Per-feature overrides"
admin.pii.overrides.inherit = "(inherit global)"
admin.pii.overrides.entityResolution = "Entity resolution"
admin.pii.overrides.missedScan = "Missed-PII scan"
admin.pii.overrides.titleGen = "Title generation"
admin.pii.overrides.metadata = "Metadata extraction"
admin.pii.overrides.fuzzyDeanon = "Fuzzy de-anonymization"
```

**Step 5** — Confirm the existing save handler PATCHes the new fields. The `updateSetting` (or whatever the local helper is named) typically writes to a local state object that is sent verbatim to PATCH /admin/settings. Because Plan 03-06 Task 1 added the new fields to `SystemSettingsUpdate` with `Optional` defaults, the existing PATCH handler accepts them automatically — NO save-handler edit needed.

After editing, run the type-check + lint:
```bash
cd frontend && npx tsc --noEmit && npm run lint
```

Both must pass clean (PostToolUse hook auto-runs these on .tsx edits).
  </action>
  <verify>
    <automated>cd frontend && npx tsc --noEmit 2>&1 | grep -qE "(error TS|Found [1-9])" && echo "TYPE_CHECK_FAILED" || (grep -q "type AdminSection" frontend/src/pages/AdminSettingsPage.tsx && grep -q "'pii'" frontend/src/pages/AdminSettingsPage.tsx && grep -q "admin.pii.title" frontend/src/pages/AdminSettingsPage.tsx && grep -q "entity_resolution_mode" frontend/src/pages/AdminSettingsPage.tsx && grep -q "llm_provider_fallback_enabled" frontend/src/pages/AdminSettingsPage.tsx && grep -q "/admin/settings/llm-provider-status" frontend/src/pages/AdminSettingsPage.tsx && grep -q "cloud_key_configured" frontend/src/pages/AdminSettingsPage.tsx && grep -q "local_endpoint_reachable" frontend/src/pages/AdminSettingsPage.tsx && grep -q "entity_resolution_llm_provider" frontend/src/pages/AdminSettingsPage.tsx && grep -q "fuzzy_deanon_llm_provider" frontend/src/pages/AdminSettingsPage.tsx && ! grep -E "backdrop-blur" frontend/src/pages/AdminSettingsPage.tsx | grep -i "pii" && echo "ADMIN_UI_OK")</automated>
  </verify>
  <acceptance_criteria>
    - `frontend/src/pages/AdminSettingsPage.tsx` `AdminSection` union type includes `'pii'` (literal addition).
    - SECTIONS array contains an entry with `id: 'pii'` and `labelKey: 'admin.pii.title'`.
    - File contains the conditional render block `{activeSection === 'pii' && (...)`.
    - The block contains form controls for all 9 settings: `entity_resolution_mode`, `llm_provider`, `llm_provider_fallback_enabled`, `pii_missed_scan_enabled`, and the 5 per-feature overrides.
    - File contains a fetch / GET to `/admin/settings/llm-provider-status` (reads `cloud_key_configured` + `local_endpoint_reachable`).
    - The cloud-key badge variant is destructive (or equivalent attention-grabbing) when `cloud_key_configured === false`.
    - File contains i18n keys `admin.pii.title`, `admin.pii.mode.label`, `admin.pii.provider.label`, `admin.pii.cloudKey.configured`, `admin.pii.cloudKey.missing`, `admin.pii.overrides.title` (all referenced in the JSX).
    - The 'pii' section block does NOT contain any `backdrop-blur` / glass class (CLAUDE.md design rule for persistent panels).
    - Translation files contain `admin.pii.*` keys for both Indonesian (default) and English.
    - `npx tsc --noEmit` returns 0 errors (no TS errors).
    - `npm run lint` returns 0 new errors (the 6 pre-existing ESLint errors in `DocumentsPage.tsx` per STATE.md L54 are NOT new).
  </acceptance_criteria>
  <done>'pii' section added to AdminSettingsPage; all 9 form controls + 2 status badges + 22 i18n keys (id+en); type-check + lint pass.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| admin browser → PATCH /admin/settings | gated by require_admin (existing); audit log via log_action |
| admin browser → GET /admin/settings/llm-provider-status | gated by require_admin; never returns raw cloud key (D-58) |
| backend env (CLOUD_LLM_API_KEY) → admin UI | one-way: existence check only; raw value never crosses this boundary |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-AUTH-01 | Information Disclosure | CLOUD_LLM_API_KEY exfiltration via admin endpoint | mitigate | D-58 — `/admin/settings/llm-provider-status` returns ONLY `bool(settings.cloud_llm_api_key)`; the endpoint never returns the raw value, never the first N chars, never an error message that echoes the key. Acceptance criterion forbids string echo. |
| T-AUTH-02 | Elevation of Privilege | Non-admin user changes provider settings | mitigate | Existing PATCH and new GET both use `Depends(require_admin)`; non-admin returns 403. |
| T-CONFIG-01 | Tampering | Bad enum value persisted via PATCH | mitigate | D-60 Pydantic Literal validation rejects bad enums at API edge (422); DB CHECK constraints (Plan 03-01 Task 2) catch any direct-SQL bypass (23514). Acceptance criterion verifies Pydantic ValidationError on bogus values. |
| T-AUDIT-01 | Repudiation | Provider switch unaudited | mitigate | Existing PATCH handler auto-audits via `log_action(action="update", resource_type="system_settings", details={"changed_fields": list(updates.keys())})`. The new fields are auto-included. NO new audit code needed. |
| T-DOS-01 | Denial of Service | Local-endpoint probe hangs the admin page | mitigate | The httpx probe in the new GET endpoint uses `timeout=2.0`; on timeout returns `local_endpoint_reachable=False`. The frontend useEffect uses `cancelled` cleanup to avoid hanging state. |
| T-XSS-01 | Tampering | i18n string injection if a label is unsafely rendered | accept | All i18n strings are static literals committed to the repo (no user-supplied content); the existing I18nProvider escapes via React's text-node defaults. No new XSS surface. |
</threat_model>

<verification>
After this plan completes:
- `git status` shows two modified files (`admin_settings.py`, `AdminSettingsPage.tsx`) and the project's i18n locale files modified.
- Backend imports cleanly: `cd backend && source venv/bin/activate && python -c "from app.main import app; print('OK')"`.
- Frontend type-check + lint clean: `cd frontend && npx tsc --noEmit && npm run lint`.
- A manual smoke-test (PATCH `/admin/settings` with `entity_resolution_mode=llm`) followed by `GET /admin/settings` confirms the new value persists.
- A manual call to `GET /admin/settings/llm-provider-status` returns the boolean dict.
- Phase 1 + Phase 2 regression: `pytest tests/ -x` returns 39/39.
- Plan 03-07 (tests) is now unblocked.
</verification>

<success_criteria>
- SystemSettingsUpdate Pydantic model gains 9 new optional Literal-typed fields (D-60).
- GET /admin/settings/llm-provider-status returns only booleans (D-58 — no raw key echo).
- AdminSettingsPage 'pii' section renders all 9 controls + 2 status badges with i18n in id+en.
- No new admin route; no new IconRail entry; one section in an existing section-state machine.
- No `backdrop-blur` / glass on the new persistent section (CLAUDE.md rule).
- Existing audit / require_admin / 60s cache TTL all carry — no service-layer changes.
- Phase 1 + Phase 2 tests still pass.
</success_criteria>

<output>
Create `.planning/phases/03-entity-resolution-llm-provider-configuration/03-06-SUMMARY.md` with:
- Files modified + line-count deltas
- Confirmation that the new GET endpoint never returns the raw cloud key
- i18n key list added (id + en)
- Type-check + lint results
- Phase 1 + Phase 2 regression: 39/39 still pass
- Plan 03-07 (tests) is now unblocked.
</output>
