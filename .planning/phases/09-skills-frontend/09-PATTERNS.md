# Phase 9: Skills Frontend - Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 5 (1 create, 4 modify)
**Analogs found:** 5 / 5

This is a pure-frontend phase. All analogs come from the existing React/Vite/Tailwind/shadcn-ui codebase. The dominant analog is `frontend/src/pages/ClauseLibraryPage.tsx` — its two-column list+inline-editor skeleton is copied wholesale and adapted for skills. `IconRail.tsx` and `App.tsx` get small, surgical patches. `i18n/translations.ts` gets new keys appended to both `id` and `en` maps. `ChatPage.tsx` gets a small `useEffect` that reads `location.state?.prefill` and forwards it to the existing chat input via the existing `handleSendMessage` (or composes it through a small lifted-state path — see notes below).

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------------|------|-----------|----------------|---------------|
| `frontend/src/pages/SkillsPage.tsx` (CREATE) | page / list+editor view | request-response (CRUD) + file-I/O | `frontend/src/pages/ClauseLibraryPage.tsx` | exact (same role + same data flow shape) |
| `frontend/src/components/layout/IconRail.tsx` (MODIFY) | layout / nav rail | request-response (route nav) | self — extend `standaloneItems[]` | exact (same file, additive patch) |
| `frontend/src/App.tsx` (MODIFY) | router config | request-response | self — sibling AppLayout child routes | exact |
| `frontend/src/i18n/translations.ts` (MODIFY) | i18n dictionary | static map | self — `nav.clauseLibrary` + `clauseLibrary.*` block | exact |
| `frontend/src/pages/ChatPage.tsx` (MODIFY, conditional) | page / chat host | event (route-state → input prefill) | self — uses `useChatContext().handleSendMessage` | role-match (no existing prefill consumer) |

Single shared analog file: `ClauseLibraryPage.tsx` (361 lines). Three modify-targets are self-extending edits to existing files. The only file with no internal precedent is the route-state prefill consumer in `ChatPage.tsx` (handled with a small new `useEffect`).

---

## Pattern Assignments

### `frontend/src/pages/SkillsPage.tsx` (CREATE — page, request-response + file-I/O)

**Analog:** `frontend/src/pages/ClauseLibraryPage.tsx` — copy the entire skeleton (imports, hooks, state machine, layout, mobile FAB, mobile overlay, desktop panel, header strip, search debounce, form rendering, save/delete handlers). Adapt field names from `clause` → `skill`, swap categories/risk for `enabled`/`is_global`/file-list/ownership state, and add the floating file-preview drawer (no analog inside this file — invent following UI-SPEC §File preview drawer with `fixed inset-y-0 right-0 z-40 w-[480px]` + `.mobile-backdrop` reuse).

**Imports pattern** (from `ClauseLibraryPage.tsx` lines 1-6):
```tsx
import { useState, useEffect, useCallback } from 'react'
import { Library, Plus, Pencil, Trash2, X, Menu, ChevronLeft, PanelLeftClose, Globe, Search } from 'lucide-react'
import { useSidebar } from '@/hooks/useSidebar'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { apiFetch } from '@/lib/api'
```

**Adapt for SkillsPage** — add `useNavigate` from `react-router-dom`, add `useAuth` from `@/contexts/AuthContext` (for ownership matrix `currentUser.id`), and swap the lucide icons for the Phase 9 set declared in UI-SPEC §Component Inventory (`Zap` is NOT needed here — it's only in IconRail; SkillsPage uses `Plus, Pencil, Trash2, Save, Download, Upload, Share2, X, Search, Globe, FileText, FileCode, File, Copy, Check, Sparkles, FileArchive, MessageSquare, Loader2, Menu, ChevronLeft, PanelLeftClose`).

**CSS class constants** (lines 35-37 — copy verbatim):
```tsx
const inputBase = "w-full rounded-lg bg-secondary text-foreground px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
const inputClass = `${inputBase} border border-border`
const textareaClass = `${inputClass} min-h-[100px] resize-none`
```
**Adapt:** keep these three constants in SkillsPage. The `instructions` textarea overrides `min-h-[100px]` → `min-h-[240px]` and adds `font-mono` per UI-SPEC.

**State machine pattern** (lines 39-94 — copy structure, adapt names):
```tsx
const { t } = useI18n()
const { panelCollapsed, togglePanel } = useSidebar()
const [mobilePanelOpen, setMobilePanelOpen] = useState(false)

const [clauses, setClauses] = useState<Clause[]>([])  // → setSkills<Skill[]>
const [loading, setLoading] = useState(true)
const [search, setSearch] = useState('')
const [categoryFilter, setCategoryFilter] = useState('')  // → drop
const [riskFilter, setRiskFilter] = useState('')          // → drop

const [editMode, setEditMode] = useState<'create' | 'edit' | null>(null)
const [editingClause, setEditingClause] = useState<Clause | null>(null)  // → editingSkill
const [formTitle, setFormTitle] = useState('')                            // → formName
const [formContent, setFormContent] = useState('')                        // → formDescription
// ... add: formInstructions, formLicense, formCompatibility, formEnabled
const [saving, setSaving] = useState(false)
```

**Search debounce pattern** (lines 79-82 — copy verbatim, change endpoint):
```tsx
useEffect(() => {
  const timer = setTimeout(fetchClauses, 300)
  return () => clearTimeout(timer)
}, [fetchClauses])
```
This delivers the 300ms debounce required by UI-SPEC §Search debounce.

**List fetch pattern** (lines 61-77 — copy structure, swap endpoint to `/skills`):
```tsx
const fetchClauses = useCallback(async () => {
  setLoading(true)
  try {
    const params = new URLSearchParams()
    if (categoryFilter) params.set('category', categoryFilter)
    if (riskFilter) params.set('risk_level', riskFilter)
    if (search) params.set('search', search)
    params.set('limit', '50')
    const res = await apiFetch(`/clause-library?${params}`)
    const data = await res.json()
    setClauses(data.data || [])
  } catch {
    setClauses([])
  } finally {
    setLoading(false)
  }
}, [categoryFilter, riskFilter, search])
```
**Adapt** for skills: `apiFetch('/skills?' + params)` with optional `?search=` and no category/risk filters. Phase 9 also calls this on mount with no args (D-P9-10 auto-refresh).

**Save handler pattern** (lines 113-138 — copy structure, swap endpoints):
```tsx
async function handleSave() {
  if (!formTitle.trim() || !formContent.trim()) return
  setSaving(true)
  try {
    const body = { /* ... */ }
    if (editMode === 'create') {
      await apiFetch('/clause-library', { method: 'POST', body: JSON.stringify(body) })
    } else if (editMode === 'edit' && editingClause) {
      await apiFetch(`/clause-library/${editingClause.id}`, { method: 'PATCH', body: JSON.stringify(body) })
    }
    resetForm()
    fetchClauses()
  } catch {
    alert('Failed to save clause')
  } finally {
    setSaving(false)
  }
}
```
**Adapt:** body for skills is `{name, description, instructions, enabled, license?, compatibility?}`. Replace `alert()` with the inline destructive banner per UI-SPEC §Error handling — `bg-destructive/10 text-destructive border-destructive/30 text-xs px-3 py-2 rounded-md`. Map name-conflict (HTTP 409) to `t('skills.errorNameConflict')`. Keep the `.catch{} → setError(t('skills.errorSave'))` shape; `apiFetch` already throws on non-OK (api.ts:21-24) so a single catch is sufficient.

**Delete handler pattern** (lines 140-148 — copy verbatim, swap message):
```tsx
async function handleDelete(id: string) {
  if (!confirm('Delete this clause?')) return
  try {
    await apiFetch(`/clause-library/${id}`, { method: 'DELETE' })
    fetchClauses()
  } catch {
    alert('Failed to delete clause')
  }
}
```
**Adapt:** `confirm(t('skills.deleteConfirm'))`, endpoint `/skills/${id}`, error → inline destructive banner. UI-SPEC §Component Inventory locks `window.confirm()` for v1 (custom Dialog deferred).

**Editor form layout pattern** (lines 156-216 — copy structure, replace fields):
```tsx
<div className="px-5 py-4 space-y-3">
  <div className="flex items-center justify-between">
    <h2 className="text-xs font-semibold">{editMode === 'create' ? t('clauseLibrary.create') : t('clauseLibrary.edit')}</h2>
    <button onClick={resetForm} className="text-muted-foreground hover:text-foreground"><X className="h-3.5 w-3.5" /></button>
  </div>
  <div className="space-y-1.5">
    <label className="text-[10px] font-medium">Title <span className="text-red-600 dark:text-red-400">*</span></label>
    <input className={inputClass} value={formTitle} onChange={e => setFormTitle(e.target.value)} placeholder="Clause title" />
  </div>
  <div className="space-y-1.5">
    <label className="text-[10px] font-medium">{t('clauseLibrary.content')} <span className="text-red-600 dark:text-red-400">*</span></label>
    <textarea className={textareaClass} value={formContent} onChange={e => setFormContent(e.target.value)} placeholder="Clause text..." />
  </div>
  ...
  <div className="flex gap-2 pt-1">
    <Button size="sm" className="flex-1 text-xs" onClick={handleSave} disabled={saving || !formTitle.trim() || !formContent.trim()}>
      {saving ? 'Saving...' : t('clauseLibrary.save')}
    </Button>
    <Button size="sm" variant="outline" className="text-xs" onClick={resetForm}>
      {t('clauseLibrary.cancel')}
    </Button>
  </div>
</div>
```
**Adapt to UI-SPEC §Skill editor:** name (required, 64-char counter) → description (required, 1024-char counter) → instructions (font-mono, 240px min-h) → grid `grid-cols-2 gap-2` for license + compatibility → "Building Block Files" section with file rows + Upload (own only) → footer with `enabled` Switch on left and the ownership-matrix action buttons on right. The required-asterisk treatment `<span className="text-red-600 dark:text-red-400">*</span>` is the locked precedent (line 164) — reuse for `name`, `description`, `instructions`.

**Save button loading state** (lines 207-210):
```tsx
<Button size="sm" className="flex-1 text-xs" onClick={handleSave} disabled={saving || !formTitle.trim() || !formContent.trim()}>
  {saving ? 'Saving...' : t('clauseLibrary.save')}
</Button>
```
**Adapt:** swap label to `t('skills.save')`; UI-SPEC §Loading states upgrades `'Saving...'` to `<Loader2 className="animate-spin h-3 w-3 mr-1.5" /> Saving…` on Save and Delete and Upload.

**Page-level layout** (lines 253-358 — copy structure, swap content):
```tsx
return (
  <div className="flex h-full">
    {/* Mobile FAB */}
    <button
      onClick={() => setMobilePanelOpen(true)}
      className="md:hidden fixed bottom-4 right-4 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg focus-ring"
    >
      <Menu className="h-5 w-5" />
    </button>

    {/* Mobile panel overlay */}
    {mobilePanelOpen && (
      <div className="md:hidden fixed inset-0 z-40">
        <div className="mobile-backdrop" onClick={() => setMobilePanelOpen(false)} />
        <div className="mobile-panel bg-background border-r border-border/50 overflow-y-auto">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border/50">
            <div><h1 className="text-sm font-semibold">{t('clauseLibrary.title')}</h1></div>
            <button onClick={() => setMobilePanelOpen(false)} className="text-muted-foreground hover:text-foreground focus-ring">
              <ChevronLeft className="h-4 w-4" />
            </button>
          </div>
          {renderPanel()}
        </div>
      </div>
    )}

    {/* Desktop filter panel */}
    {!panelCollapsed && (
      <div className="hidden md:flex w-[340px] shrink-0 flex-col border-r border-border/50 bg-sidebar">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/50">
          <div>
            <h1 className="text-sm font-semibold">{t('clauseLibrary.title')}</h1>
            <p className="text-[10px] text-muted-foreground">{clauses.length} clauses</p>
          </div>
          <button onClick={togglePanel} className="flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors focus-ring">
            <PanelLeftClose className="h-4 w-4" />
          </button>
        </div>
        {renderPanel()}
      </div>
    )}

    {/* Main content */}
    <div className="flex-1 overflow-y-auto p-6">
      {loading ? (...) : clauses.length === 0 ? (...) : (...)}
    </div>
  </div>
)
```
**Critical adaptations for SkillsPage:**

1. **Left panel content is the SKILL LIST** (not filter form). ClauseLibrary puts the search+filter form into the left panel and the list into the main content area. SkillsPage inverts this per D-P9-05 / UI-SPEC §Page-level: **left = searchable list, right = inline editor**. The left panel renders search input + skill list rows; the right panel (`flex-1`) renders the editor or empty state.
2. **Mobile FAB stays in same position** (`bottom-4 right-4 h-12 w-12`) but its purpose is to open the skill list (not a filter panel).
3. **Header subhead** swaps `{n} clauses` → `t('skills.count', {n})` — see Shared Patterns §i18n interpolation below.
4. **The "+" CTA in the left panel header** becomes the "+ New Skill" Popover trigger (UI-SPEC §Layout § Skill list rows → split-button menu with Manual / AI / Import). Use shadcn `Popover` (already imported in `IconRail.tsx:4` so the component exists at `@/components/ui/popover`).

**Skill list row pattern** (no exact analog — synthesize from clause grid card lines 313-353 + UI-SPEC §Skill list rows):
```tsx
// Selection state + ownership badges follow ClauseLibraryPage:316-325 precedent:
<h3 className="text-xs font-semibold truncate">{clause.title}</h3>
<div className="flex items-center gap-1.5 mt-1">
  <span className="text-[9px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{t(`clauseCategory.${clause.category}`)}</span>
  ...
  {clause.is_global && (
    <span className="flex items-center gap-0.5 text-[9px] text-primary">
      <Globe className="h-2.5 w-2.5" /> {t('clauseLibrary.global')}
    </span>
  )}
</div>
```
**Adapt to row format** (UI-SPEC: `px-3 py-2.5 border-b border-border/50 hover:bg-muted/50` + `bg-primary/10 text-primary` when selected): two-line layout — `name` row with right-aligned badges (`GLOBAL` purple + `DISABLED` muted + tiny disabled-toggle indicator), `description` line below muted/line-clamp-1. Whole row clickable → calls `startEdit(skill)` (or `startView` for non-owned global skills).

**File-row pattern inside editor** (no in-repo analog for this exact UI — synthesize from UI-SPEC §File list rows):
- 36px tall rows, `px-3 py-2 border-b border-border/50 hover:bg-muted/50 cursor-pointer`
- icon by mime: `text/*` → `FileText`, `application/*` text-readable → `FileCode`, else → `File`
- size formatter: `<1KB → "{n} B"`, `<1MB → "{n} KB"`, `≥1MB → "{n}.{m} MB"`
- trash icon (own skills only) at right with `e.stopPropagation()` per UI-SPEC §File list rows
- selected state when its preview drawer is open: `bg-primary/10 text-primary`
- click anywhere on row (except trash) opens preview drawer

**File preview drawer** (no in-repo analog — synthesize from UI-SPEC §File preview drawer):
```tsx
{previewFile && (
  <>
    {/* Backdrop — backdrop-blur ALLOWED here per CLAUDE.md (transient overlay) */}
    <div
      className="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm motion-safe:transition-opacity motion-safe:duration-200"
      onClick={closePreview}
      aria-hidden="true"
    />
    {/* Drawer */}
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="preview-title"
      className="fixed inset-y-0 right-0 z-40 w-full md:w-[480px] bg-card border-l border-border shadow-lg flex flex-col motion-safe:transition-transform motion-safe:duration-200 ease-out"
    >
      <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between gap-2">
        <h2 id="preview-title" className="text-xs font-semibold truncate">{previewFile.filename}</h2>
        <div className="flex items-center gap-1">
          {/* Copy, Download, X icon buttons with tooltips */}
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        {previewLoading ? (
          <div className="shimmer h-full m-4" />
        ) : previewFile.binary ? (
          <BinaryPreviewCard /> /* per UI-SPEC */
        ) : (
          <pre className="font-mono text-xs leading-relaxed whitespace-pre-wrap break-words p-4">{previewFile.content}</pre>
        )}
      </div>
    </div>
  </>
)}
```
- `Esc` key closes (use `useEffect` with `keydown` listener while drawer is mounted).
- `document.body.style.overflow = 'hidden'` on open, `''` on close (UI-SPEC §State machine: file preview drawer → body scroll lock).
- Reduced motion gating via `motion-safe:` prefix per UI-SPEC §Animation Inventory + Accessibility.

**Ownership matrix logic** (no analog — synthesize from D-P9-11/12/13 + UI-SPEC §Ownership × button matrix):
```tsx
const { user } = useAuth() // user.id
const isOwnPrivate = selectedSkill.user_id === user?.id
const isOwnGlobal  = selectedSkill.created_by === user?.id && selectedSkill.user_id === null
const isOtherGlobal = !isOwnPrivate && !isOwnGlobal && selectedSkill.user_id === null

const formDisabled = isOwnGlobal || isOtherGlobal
// Apply BOTH: form-wrapper className includes "opacity-60 pointer-events-none" when disabled
//             AND each <input>/<textarea> gets native `disabled={formDisabled}` + `aria-disabled={formDisabled}`
// (UI-SPEC §Accessibility Contract — both signals required)
```
Banner visibility: `isOwnGlobal` → `t('skills.bannerOwnerGlobal')`; `isOtherGlobal` → `t('skills.bannerGlobal')`.
Banner styling: `bg-primary/10 text-primary text-xs px-4 py-2 rounded-md border border-primary/20 flex items-center gap-2 role="status"` with inline `<Globe className="h-3 w-3" />`.

**"+ New Skill" Popover pattern** (use shadcn Popover already exercised in `IconRail.tsx:113-136`):
```tsx
<Popover>
  <PopoverTrigger asChild><Button size="sm" className="w-full text-xs"><Plus className="mr-1.5 h-3 w-3" />{t('skills.new')}</Button></PopoverTrigger>
  <PopoverContent side="bottom" align="start" className="w-52 p-2">
    <button onClick={startCreate}><Sparkles ... />{t('skills.createManual')}</button>      {/* opens editor in create mode */}
    <button onClick={createWithAI}><Sparkles ... />{t('skills.createWithAI')}</button>     {/* navigate('/', { state: { prefill }}) */}
    <button onClick={() => fileInputRef.current?.click()}>{t('skills.importFile')}</button> {/* triggers hidden file input */}
  </PopoverContent>
</Popover>
```

**"Create with AI" / "Try in Chat" navigation** (locked from UI-SPEC §"Create with AI" navigation + §"Try in Chat" navigation):
```tsx
const navigate = useNavigate()
// Create with AI:
navigate('/', { state: { prefill: 'I want to create a new skill.' } })
// Try in Chat:
navigate('/', { state: { prefill: `Please use the ${skill.name} skill.` } })
```
The receiving end is in `ChatPage.tsx` — see that file's pattern below.

**File upload pattern** — multipart FormData via `apiFetch`. The api.ts:9-15 already handles `FormData` correctly (skips Content-Type to let the browser set the boundary). Use a hidden `<input type="file" />` triggered by the Upload button:
```tsx
const file = e.target.files?.[0]
if (!file) return
if (file.size > 10 * 1024 * 1024) { setError(t('skills.errorFileSize')); return }
const formData = new FormData()
formData.append('file', file)
await apiFetch(`/skills/${selectedSkill.id}/files`, { method: 'POST', body: formData })
```

**Error handling pattern** — `apiFetch` (api.ts:21-24) throws `Error(error.detail || 'Request failed')` on non-OK. Catch and set inline destructive banner per UI-SPEC §Error handling. NEVER use `alert()` in Phase 9 (UI-SPEC explicit override of the ClauseLibraryPage `alert()` precedent at lines 134/146).

---

### `frontend/src/components/layout/IconRail.tsx` (MODIFY — layout, request-response)

**Analog:** the file itself — extend `standaloneItems[]` array.

**Imports patch** (line 3 — add `Zap`):
```tsx
import { Home, Folder, FilePlus, Library, GitCompare, ShieldCheck, ShieldAlert, Scale, ClipboardList, FileCheck, BookOpen, Plug, LayoutDashboard, Settings, PanelLeftClose, PanelLeftOpen, Clock, Zap } from 'lucide-react'
```

**Array extension pattern** (lines 25-30 — insert new entry between Chat and Dashboard per D-P9-03):
```tsx
const standaloneItems: NavItem[] = [
  { path: '/', icon: Home, labelKey: 'nav.chat', end: true },
  { path: '/skills', icon: Zap, labelKey: 'nav.skills' },          // ← NEW
  { path: '/dashboard', icon: LayoutDashboard, labelKey: 'nav.dashboard' },
  { path: '/bjr', icon: Scale, labelKey: 'nav.bjr' },
  { path: '/pdp', icon: ShieldAlert, labelKey: 'nav.pdp' },
]
```
**No other changes** — the existing rendering loop at lines 165-183 (`standaloneItems.map(...)`) handles the new item with the existing `railButtonClass` active-state treatment (purple bar + 3px gradient stripe), tooltip via `Tooltip`/`TooltipContent`, and `aria-label={t(labelKey)}`. Zero new component code.

---

### `frontend/src/App.tsx` (MODIFY — router config, request-response)

**Analog:** the file itself — sibling AppLayout child routes.

**Import pattern** (lines 5-28 — alphabetical block of page imports; add `SkillsPage` near `SettingsPage`):
```tsx
import { SettingsPage } from '@/pages/SettingsPage'
import { SkillsPage } from '@/pages/SkillsPage'           // ← NEW
```

**Route registration pattern** (line 51-69 — add inside the AppLayout child routes, near `clause-library` since they're peer CRUD pages):
```tsx
<Route index element={<ChatPage />} />
<Route path="documents" element={<DocumentsPage />} />
<Route path="create" element={<DocumentCreationPage />} />
<Route path="clause-library" element={<ClauseLibraryPage />} />
<Route path="skills" element={<SkillsPage />} />          {/* ← NEW */}
<Route path="compare" element={<DocumentComparisonPage />} />
...
```
**No `AdminGuard`** — skills are user-facing (any authenticated user). The wrapping `AuthGuard > AppLayout` (lines 46-50) covers auth-gating.

---

### `frontend/src/i18n/translations.ts` (MODIFY — i18n dictionary, static)

**Analog:** the file itself — `nav.clauseLibrary` (lines 172 / 770) plus the `clauseLibrary.*` block that follows.

**Existing pattern — Indonesian block** (lines 172-189):
```ts
'nav.clauseLibrary': 'Pustaka Klausul',
'clauseLibrary.title': 'Pustaka Klausul',
'clauseLibrary.search': 'Cari klausul...',
'clauseLibrary.create': 'Buat Klausul',
'clauseLibrary.edit': 'Edit Klausul',
'clauseLibrary.delete': 'Hapus',
'clauseLibrary.save': 'Simpan',
'clauseLibrary.cancel': 'Batal',
'clauseLibrary.global': 'Global',
'clauseLibrary.empty': 'Belum ada klausul.',
...
```

**Existing pattern — English block** (lines 770-787 mirrored structure):
```ts
'nav.clauseLibrary': 'Clause Library',
'clauseLibrary.title': 'Clause Library',
...
```

**Adapt — append a new `skills.*` block to BOTH the `id` map and the `en` map.** All key/value pairs are pre-locked in UI-SPEC §Copywriting Contract:

- Keys (alphabetical, suggested insertion order under each existing block):
  - `nav.skills` (new entry inside Navigation block — lines ~21-24 for `id`, lines ~619-622 for `en`)
  - `skills.title`, `skills.new`, `skills.save`, `skills.tryInChat`, `skills.cancel`, `skills.share`, `skills.unshare`, `skills.export`, `skills.import`, `skills.createWithAI`, `skills.createManual`, `skills.importFile`, `skills.delete`, `skills.deleteConfirm`, `skills.unshareConfirm`, `skills.fileDeleteConfirm`, `skills.empty` (heading + body — split into two keys: `skills.emptyHeading`, `skills.emptyBody`), `skills.emptySearch` (with `{query}` interpolation), `skills.editorEmptyHeading`, `skills.editorEmptyBody`, `skills.filesEmpty`, `skills.errorSave`, `skills.errorDelete`, `skills.errorFileSize`, `skills.errorUpload`, `skills.errorImport`, `skills.errorNameConflict`, `skills.errorNameFormat`, `skills.bannerGlobal`, `skills.bannerOwnerGlobal`, `skills.count` (e.g. `'{n} skills'` / `'{n} skill'`).
- All EN + ID values are explicitly listed in UI-SPEC §Copywriting Contract — copy them verbatim.

**No code changes to `I18nContext.tsx`** — the `t(key)` function reads from the existing flat dict.

**Interpolation note:** the existing `t()` does NOT auto-interpolate `{n}` / `{query}` (no precedent in the file for parameterized keys — the count lines like `{clauses.length} clauses` are concatenated in JSX). For Phase 9, follow the same pattern — render `{skills.length} {t('skills.unitPlural')}` or implement a tiny inline interpolation (`t('skills.count').replace('{n}', String(n))`). UI-SPEC labels EN as `{n} skills` and ID as `{n} skill`, so a single `skills.unit` key with JSX concat `{n} {t('skills.unit')}` is the smallest deviation. Planner picks; both are acceptable.

---

### `frontend/src/pages/ChatPage.tsx` (MODIFY conditional — page, event)

**Analog:** the file itself — currently consumes `useChatContext()` and renders `<MessageInput onSend={handleSendMessage} ... />`. There is no existing `location.state` consumer in the chat path (verified: `grep -n "useLocation\|location.state\|prefill"` returns empty across `ChatPage.tsx`, `MessageInput.tsx`, `WelcomeScreen.tsx`).

**Existing structure** (full file, 50 lines):
```tsx
import { useChatContext } from '@/contexts/ChatContext'
import { MessageView } from '@/components/chat/MessageView'
import { MessageInput } from '@/components/chat/MessageInput'
import { WelcomeScreen } from '@/components/chat/WelcomeScreen'

export function ChatPage() {
  const { activeThreadId, ..., handleSendMessage, ... } = useChatContext()
  if (!activeThreadId) return <WelcomeScreen />
  return (
    <div className="flex flex-1 min-h-0 flex-col">
      <MessageView ... />
      <MessageInput onSend={handleSendMessage} disabled={isStreaming} ... />
    </div>
  )
}
```

**Pattern to add — route-state prefill consumer:**
```tsx
import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
...
export function ChatPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const consumedRef = useRef(false)
  const { handleSendMessage, ... } = useChatContext()

  useEffect(() => {
    const prefill = (location.state as { prefill?: string } | null)?.prefill
    if (prefill && !consumedRef.current) {
      consumedRef.current = true
      handleSendMessage(prefill)
      // Clear the state so refresh doesn't re-trigger
      navigate(location.pathname, { replace: true, state: null })
    }
  }, [location.state, handleSendMessage, navigate, location.pathname])
  ...
}
```

**Notes:**
- **Auto-send vs. prefill-into-input**: UI-SPEC §"Create with AI" navigation says "pre-populate the input" — this implies the user can review/edit before sending. However, `MessageInput` keeps its `value` in local component state (line 15: `const [value, setValue] = useState('')`) with no external prefill prop. To preserve that contract without surgery, the simplest read is **auto-send**: call `handleSendMessage(prefill)` from `ChatPage`'s `useEffect`. This matches the chat semantics (`setMessage / sendMessage handler` mentioned in UI-SPEC). If true prefill-into-input is required, the planner must add a `prefill?: string` prop to `MessageInput` and propagate it to its `useState` initial value via a `useEffect` watcher — that's a 2-line change to `MessageInput.tsx` (lift initial value).
- **WelcomeScreen path**: when `activeThreadId` is null, `<WelcomeScreen />` renders BEFORE the input is mounted. `handleSendMessage` from `useChatContext()` should still be callable (it creates a thread on first send) — verify with `useChatState` source. If `WelcomeScreen` needs the prefill instead, the same `useEffect` pattern applies but mounted there. Planner should pick the location after reading `useChatState.handleSendMessage` to confirm it works without an active thread.
- **Idempotency**: the `consumedRef` + `navigate(..., { state: null })` pair is required to prevent re-sending on hot reload, route remount, or when the user navigates back to chat. This is a standard pattern; the file currently has no analog.

---

## Shared Patterns

### apiFetch (cross-cutting — applied to all CRUD/file calls in SkillsPage)

**Source:** `frontend/src/lib/api.ts` (full file, 27 lines).
**Apply to:** every backend call in SkillsPage.

```tsx
export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  const isFormData = options.body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || 'Request failed')
  }
  return response
}
```

Key facts the planner must rely on:
- Auth header is automatic — never add `Authorization` manually.
- `FormData` body skips `Content-Type` (works for `POST /skills/import` and `POST /skills/{id}/files`).
- Non-OK throws an `Error` with `detail` from the JSON body. **Phase 9 must catch this to map `409 Skill name already exists` → `t('skills.errorNameConflict')`**, but the thrown message is a generic string, NOT a status code. Either: (a) parse the message string, or (b) add an extension to `apiFetch` to surface status codes (not in scope for Phase 9 — keep string-matching for now).

### Two-column layout skeleton

**Source:** `ClauseLibraryPage.tsx` lines 253-358.
**Apply to:** `SkillsPage.tsx` only.
- Outer flex container `flex h-full`.
- Mobile FAB at `fixed bottom-4 right-4 z-40 h-12 w-12 rounded-full bg-primary text-primary-foreground shadow-lg focus-ring`.
- Mobile overlay using `.mobile-backdrop` + `.mobile-panel` classes (defined in `index.css:401-415` — verified).
- Desktop panel: `hidden md:flex w-[340px] shrink-0 flex-col border-r border-border/50 bg-sidebar` (NO `backdrop-blur` — confirmed CLAUDE.md rule).
- Header strip: `flex items-center justify-between px-5 py-3 border-b border-border/50` with title + count + collapse button.
- Main content: `flex-1 overflow-y-auto p-6`.
- `useSidebar()` panel-collapse pattern is wired through `AppLayout` Outlet context (confirmed via `useSidebar.ts`).

### shadcn `Button` variants

**Source:** `ClauseLibraryPage.tsx` lines 207-214 (Save = default purple, Cancel = `variant="outline"`).
**Apply to:** all editor footer buttons in SkillsPage per UI-SPEC §Color §Accent reserved set:
- `[Save]`, `[Try in Chat]` → default (primary purple)
- `[Cancel]`, `[Share]`, `[Unshare]`, `[Export]`, `[Import]` → `variant="outline"`
- `[Delete]` → `variant="ghost"` with destructive hover OR `variant="outline"` with destructive text — UI-SPEC §Color forbids primary purple on Delete (use destructive on hover only). The exact shadcn variant is not pinned in UI-SPEC; planner can use `variant="outline"` + `text-destructive hover:bg-destructive/10` for the cleanest mapping with no new variant.

### Loading-state component (`shimmer`)

**Source:** `frontend/src/index.css:417-427` defines `.shimmer` keyframes + class.
**Apply to:** SkillsPage initial list load (5 placeholder rows), skill-detail load on row click, file-preview drawer body during fetch. Per UI-SPEC §Loading states:
```tsx
<div className="shimmer h-[52px] rounded-md mx-3 my-1" />  // list row placeholder
<div className="shimmer h-[400px] rounded-md" />            // editor body
<div className="shimmer h-full m-4" />                       // drawer body
```

### Required-field asterisk

**Source:** `ClauseLibraryPage.tsx:164,168` — `<span className="text-red-600 dark:text-red-400">*</span>`.
**Apply to:** SkillsPage `name`, `description`, `instructions` field labels (per UI-SPEC §Copywriting Contract §Required-field markers).

### Mobile FAB + overlay classes

**Source:** `index.css:400-415` (`.mobile-backdrop`, `.mobile-panel`) + `ClauseLibraryPage.tsx:256-279`.
**Apply to:** SkillsPage mobile breakpoint behavior (UI-SPEC §Mobile Breakpoint Behavior). NOTE: `.mobile-panel` has `max-width: 340px` baked in — this exactly matches the desktop panel width and requires no override.

### Tooltip on icon-only buttons

**Source:** `IconRail.tsx:151-161` (single Tooltip + TooltipContent on a button) + `tooltip.tsx` shim (base-ui-backed; uses `render` prop internally per CLAUDE.md "base-ui tooltips use `render` prop, not `asChild`").
**Apply to:** every icon-only button in SkillsPage (drawer `Copy`/`Download`/`X`, file-row `Trash2`, panel collapse). The shim translates `asChild` so the existing usage form is correct.

### Globe badge for "global" indicator

**Source:** `ClauseLibraryPage.tsx:320-324` — purple Globe + label inside a small inline-flex span.
**Apply to:** SkillsPage GLOBAL badge in skill list rows AND in the editor banner. Same `text-primary` + `<Globe className="h-2.5 w-2.5" />` treatment. UI-SPEC pins this as one of the 7 reserved primary-accent uses.

### Hidden file input + button-trigger upload

**Source:** No exact analog in `ClauseLibraryPage.tsx` (clauses don't take file uploads). Closest analog is `documents.py` upload pattern referenced from CONTEXT.md, but the frontend equivalent is the `DocumentsPage.tsx` upload flow (not loaded; planner can skim if needed). Standard React idiom:
```tsx
const fileInputRef = useRef<HTMLInputElement>(null)
<input ref={fileInputRef} type="file" className="hidden" onChange={handleUpload} accept="*/*" />
<Button onClick={() => fileInputRef.current?.click()}>Upload</Button>
```
**Apply to:** SkillsPage Upload button AND the "Import from File" Popover entry (multipart ZIP upload to `POST /skills/import`).

### Auth user identity (ownership matrix)

**Source:** `frontend/src/contexts/AuthContext.tsx:53-55` — `useAuth()` returns `{ user, role, isAdmin, loading }` where `user` is a Supabase `User` with `user.id`.
**Apply to:** SkillsPage ownership branch (`isOwnPrivate`, `isOwnGlobal`, `isOtherGlobal`). Use `user?.id` not `user.id` (it can be null while loading).

---

## No Analog Found

No file in scope is fully without an analog — the only patterns without an in-repo precedent are **internal sub-features** of `SkillsPage.tsx`:

| Sub-feature | Reason no analog exists | Planner falls back to |
|-------------|--------------------------|-----------------------|
| File preview drawer (`fixed inset-y-0 right-0 w-[480px]` slide-in) | No transient overlay drawer in the repo today (mobile FAB overlay is left-side, drawer is right-side). | UI-SPEC §File preview drawer (fully specified) — use Tailwind utility classes + `motion-safe:` gating. |
| Ownership-state form-disable wrapper (`opacity-60 pointer-events-none` + native `disabled` on every control) | No existing page disables an entire form based on ownership; clause library hides edit/delete actions for global rows but doesn't render a read-only editor. | UI-SPEC §Ownership × button matrix (fully specified). |
| Live char counter on input (`{n}/64`, `{n}/1024`) turning destructive at overflow | No precedent — Counter is always rendered as static text in this app. | UI-SPEC §Character counters (fully specified). Render as `text-[9px] text-muted-foreground` aligned bottom-right of textarea container; toggle to `text-destructive` when over cap. |
| Copy-to-clipboard with success swap (`Copy` → `Check` for 1500ms) | No precedent in repo. | UI-SPEC §Animation Inventory + §File preview drawer. Standard `navigator.clipboard.writeText` + `setTimeout`. |
| `Cmd/Ctrl+S` → save | No keyboard shortcut precedent on CRUD pages. | UI-SPEC marks this as **optional polish — defer if scope tight**. Planner can drop. |
| Route-state prefill consumer (`location.state.prefill` → auto-send chat message) | No existing consumer of `location.state` in the chat path (verified by grep). | UI-SPEC §"Create with AI" navigation (fully specified). Pattern is in this PATTERNS.md under `ChatPage.tsx` above. |
| Import-summary modal (post-ZIP-upload result list) | No bulk-import UI exists today. | UI-SPEC §Loading states §Import ZIP — modal-style overlay with `Loader2` + post-completion summary card. Planner can implement inline (a Tailwind-styled `<div className="fixed inset-0 z-50 ...">` modal — no shadcn Dialog needed since UI-SPEC defers Dialog). |

For each of the above, the **UI-SPEC is the authoritative source** — every value (size, padding, color, animation, copy) is pinned in the spec, so planning does not require additional research.

---

## Notes for Planner

1. **`Badge` and `Switch` shadcn primitives are NOT installed** (verified `ls frontend/src/components/ui/`: only `button, input, popover, scroll-area, select, separator, skeleton, textarea, tooltip`). UI-SPEC §Component Inventory references both. Planner must either:
   - (a) add them via `npx shadcn@latest add badge switch`, OR
   - (b) inline them as Tailwind-styled `<span>` (badge) and `<button role="switch" aria-checked>` (switch) — clause library takes the inline route at lines 318-322 (`<span className="text-[9px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">`). UI-SPEC lists the components abstractly; either path satisfies the contract. Inline is faster and avoids a registry add.
2. **`Dialog` shadcn primitive is NOT installed** — UI-SPEC explicitly accepts `window.confirm()` for v1 (matching ClauseLibraryPage:141). No Dialog add required.
3. **Translation interpolation is NOT supported** by the current `t()` function — confirmed from existing usage (`{clauses.length} clauses` is JSX concat, not `t('...', {n})`). Planner must do the interpolation at the call site (template strings) OR add a tiny `t(key, params)` overload to `I18nContext`. The smallest path: split parameterized strings into prefix/suffix keys (e.g. `skills.emptySearchPrefix='No skills match "'`, `skills.emptySearchSuffix='"'`) — but this is awkward for two languages. Recommended: add a 5-line interpolator to `I18nContext.tsx` (`return value.replace(/\{(\w+)\}/g, (_, k) => params?.[k] ?? '')`). This is a tiny, local change and unblocks `{n}` / `{query}` cleanly. Planner decides; either works.
4. **`MessageInput` is uncontrolled from outside** (line 15: `const [value, setValue] = useState('')`). UI-SPEC §"Create with AI" navigation says "pre-populate the input." If true prefill (visible-but-not-sent) is required, that needs a 2-line lift in `MessageInput.tsx`. The cleaner read of UI-SPEC plus the simpler implementation is **auto-send**: `handleSendMessage(prefill)` from `ChatPage`'s `useEffect`. Planner decides; the no-MessageInput-touch path is recommended.
5. **`WelcomeScreen` vs `ChatPage` mount order:** When `!activeThreadId`, `WelcomeScreen` renders and `MessageInput` does NOT mount. The route-state-prefill `useEffect` should live at the `ChatPage` (route-component) level so it runs regardless of which child renders. `handleSendMessage` from `useChatContext()` is available in both branches.
6. **No skill catalog refresh trigger after `save_skill` from chat:** D-P9-10 locks the policy at "auto-refresh on mount" — the user must navigate to `/skills` to see a newly-saved-via-chat skill. No live invalidation. The `useEffect(() => { fetchSkills() }, [])` covers this.

---

## Metadata

**Analog search scope:** `frontend/src/pages/`, `frontend/src/components/layout/`, `frontend/src/components/ui/`, `frontend/src/components/chat/`, `frontend/src/contexts/`, `frontend/src/hooks/`, `frontend/src/i18n/`, `frontend/src/lib/`, `frontend/src/index.css`.
**Files scanned:** 11 read in full or in part (`ClauseLibraryPage.tsx`, `IconRail.tsx`, `App.tsx`, `ChatPage.tsx`, `MessageInput.tsx`, `ChatContext.tsx`, `useSidebar.ts`, `AuthContext.tsx`, `api.ts`, `index.css` §mobile/shimmer/focus, `translations.ts` §nav+clauseLibrary). Component directory listed (`components/ui/`).
**Pattern extraction date:** 2026-05-01.

---

*Phase: 9-Skills Frontend*
*PATTERNS compiled: 2026-05-01*
