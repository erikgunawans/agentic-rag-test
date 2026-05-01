import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Plus, Pencil, Trash2, X, Menu, ChevronLeft, PanelLeftClose,
  Globe, Search, Sparkles, FileArchive, Loader2, Zap,
} from 'lucide-react'
import { useSidebar } from '@/hooks/useSidebar'
import { useI18n } from '@/i18n/I18nContext'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { apiFetch } from '@/lib/api'

export interface Skill {
  id: string
  name: string
  description: string
  instructions: string
  enabled: boolean
  user_id: string | null
  created_by: string | null
  license?: string | null
  compatibility?: string | null
}

export interface SkillFile {
  id: string
  skill_id: string
  filename: string
  size_bytes: number
  mime_type: string | null
  created_at: string
}

const inputBase = "w-full rounded-lg bg-secondary text-foreground px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
const inputClass = `${inputBase} border border-border`

// Suppress unused variable warning — textareaClass is used by Plan 03 in the same file scope
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const _textareaClass = `${inputClass} min-h-[100px] resize-none`

export function SkillsPage() {
  const { t } = useI18n()
  const { user } = useAuth()
  const navigate = useNavigate()
  const { panelCollapsed, togglePanel } = useSidebar()

  // ---- Layout state ----
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)

  // ---- List state ----
  const [skills, setSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  // ---- Editor state (slot for Plan 03; defined here so the state machine is centralized) ----
  const [editMode, setEditMode] = useState<'create' | 'edit' | null>(null)
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null)
  const [skillFiles, setSkillFiles] = useState<SkillFile[]>([])
  const [detailLoading, setDetailLoading] = useState(false)

  // ---- Cross-cutting error banner state (consumed by Plan 03's editor) ----
  const [errorBanner, setErrorBanner] = useState<string | null>(null)

  // ---- Fetch list (debounced) ----
  const fetchSkills = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (search) params.set('search', search)
      params.set('limit', '50')
      const res = await apiFetch(`/skills?${params}`)
      const data = await res.json()
      setSkills(data.data || [])
    } catch {
      setSkills([])
    } finally {
      setLoading(false)
    }
  }, [search])

  // 300ms debounce — verbatim from ClauseLibraryPage:79-82
  useEffect(() => {
    const timer = setTimeout(fetchSkills, 300)
    return () => clearTimeout(timer)
  }, [fetchSkills])

  // ---- Selection / ownership branch ----
  async function selectSkill(skill: Skill) {
    setEditMode('edit')
    setMobilePanelOpen(false)
    setErrorBanner(null)
    setDetailLoading(true)
    setSelectedSkill(skill)
    try {
      // Fetch full skill (including instructions + license + compatibility)
      const skillRes = await apiFetch(`/skills/${skill.id}`)
      const skillBody = await skillRes.json()
      setSelectedSkill(skillBody.data ?? skillBody)
      // Fetch attached files
      const filesRes = await apiFetch(`/skills/${skill.id}/files`)
      const filesBody = await filesRes.json()
      setSkillFiles(filesBody.data || [])
    } catch {
      setErrorBanner(t('skills.errorSave'))  // generic load failure -> reuse generic save error string
    } finally {
      setDetailLoading(false)
    }
  }

  function startCreate() {
    setEditMode('create')
    setSelectedSkill(null)
    setSkillFiles([])
    setErrorBanner(null)
    setMobilePanelOpen(false)
  }

  function resetEditor() {
    setEditMode(null)
    setSelectedSkill(null)
    setSkillFiles([])
    setErrorBanner(null)
  }

  // ---- Ownership branch flags (LOCKED from D-P9-11/12/13 + 07-CONTEXT D-P7-01) ----
  // Computed only when a skill is selected; create-mode is always isOwnPrivate (not yet saved).
  const isOwnPrivate =
    selectedSkill !== null &&
    selectedSkill.user_id !== null &&
    selectedSkill.user_id === user?.id

  const isOwnGlobal =
    selectedSkill !== null &&
    selectedSkill.user_id === null && selectedSkill.created_by === user?.id

  const isOtherGlobal =
    selectedSkill !== null &&
    selectedSkill.user_id === null && selectedSkill.created_by !== user?.id

  const formDisabled = isOwnGlobal || isOtherGlobal  // Plan 03 wires this through

  // ---- Navigation handlers ----
  function createWithAI() {
    // D-P9-09 locked: exact prefill string. State-based routing per UI-SPEC.
    navigate('/', { state: { prefill: 'I want to create a new skill.' } })
  }

  function tryInChat(skill: Skill) {
    // Discretion-locked: substitute skill name into the prefill template.
    navigate('/', { state: { prefill: `Please use the ${skill.name} skill.` } })
  }

  // Hidden file input ref for "Import from File" Popover entry — consumed by Plan 04
  const importInputRef = useRef<HTMLInputElement>(null)

  // ---- List row renderer ----
  function renderListRow(skill: Skill) {
    const isSelected = selectedSkill?.id === skill.id
    return (
      <button
        key={skill.id}
        type="button"
        onClick={() => selectSkill(skill)}
        className={`w-full text-left px-3 py-2.5 border-b border-border/50 transition-colors focus-ring ${
          isSelected ? 'bg-primary/10 text-primary' : 'hover:bg-muted/50'
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-xs font-semibold truncate">{skill.name}</h3>
          <div className="flex items-center gap-1 shrink-0">
            {skill.user_id === null && (
              <span className="flex items-center gap-0.5 text-[9px] text-primary">
                <Globe className="h-2.5 w-2.5" />
                {t('skills.badgeGlobal')}
              </span>
            )}
            {!skill.enabled && (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                {t('skills.badgeDisabled')}
              </span>
            )}
          </div>
        </div>
        <p className="text-[10px] text-muted-foreground line-clamp-1 mt-0.5">{skill.description}</p>
      </button>
    )
  }

  // ---- Left panel content (search + list + new-skill popover) ----
  function renderPanel() {
    return (
      <div className="flex flex-col flex-1 min-h-0">
        <div className="px-5 py-3 space-y-2 border-b border-border/50">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
            <input
              className={`${inputClass} pl-8`}
              placeholder={t('skills.search')}
              value={search}
              onChange={e => setSearch(e.target.value)}
              aria-label={t('skills.search')}
            />
          </div>
          <Popover>
            <PopoverTrigger asChild>
              <Button size="sm" className="w-full text-xs">
                <Plus className="mr-1.5 h-3 w-3" />
                {t('skills.new')}
              </Button>
            </PopoverTrigger>
            <PopoverContent side="bottom" align="start" className="w-52 p-2">
              <button
                type="button"
                onClick={startCreate}
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50"
              >
                <Pencil className="h-4 w-4 shrink-0" />
                {t('skills.createManual')}
              </button>
              <button
                type="button"
                onClick={createWithAI}
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50"
              >
                <Sparkles className="h-4 w-4 shrink-0" />
                {t('skills.createWithAI')}
              </button>
              <button
                type="button"
                onClick={() => importInputRef.current?.click()}
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50"
              >
                <FileArchive className="h-4 w-4 shrink-0" />
                {t('skills.importFile')}
              </button>
            </PopoverContent>
          </Popover>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading && skills.length === 0 ? (
            // 5 shimmer placeholder rows per UI-SPEC §Loading states
            <>
              {[0, 1, 2, 3, 4].map(i => (
                <div key={i} className="shimmer h-[52px] rounded-md mx-3 my-1" />
              ))}
            </>
          ) : skills.length === 0 ? (
            <div className="px-5 py-6 text-center">
              {search ? (
                <p className="text-xs text-muted-foreground">
                  {t('skills.emptySearch', { query: search })}
                </p>
              ) : (
                <>
                  <Zap className="h-8 w-8 mx-auto text-muted-foreground/40 mb-2" />
                  <p className="text-xs font-semibold mb-1">{t('skills.emptyHeading')}</p>
                  <p className="text-[10px] text-muted-foreground">{t('skills.emptyBody')}</p>
                </>
              )}
            </div>
          ) : (
            skills.map(renderListRow)
          )}
        </div>
      </div>
    )
  }

  // ---- Editor placeholder (Plan 03 replaces this with the full form) ----
  function renderEditor() {
    if (editMode === null) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-center px-6">
          <Zap className="h-10 w-10 text-muted-foreground/40 mb-3" />
          <p className="text-sm font-semibold mb-1">{t('skills.editorEmptyHeading')}</p>
          <p className="text-xs text-muted-foreground max-w-sm">{t('skills.editorEmptyBody')}</p>
        </div>
      )
    }
    if (detailLoading) {
      return <div className="shimmer h-[400px] rounded-md m-6" />
    }
    // Plan 03 fills this branch. Until then, render a stub that shows the selected skill name
    // so manual smoke tests confirm the click-to-select path works.
    return (
      <div className="px-5 py-4 space-y-3" data-testid="skills-editor-slot">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold">
            {editMode === 'create' ? t('skills.createManual') : selectedSkill?.name ?? ''}
          </h2>
          <button onClick={resetEditor} className="text-muted-foreground hover:text-foreground" aria-label={t('skills.cancel')}>
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
        <p className="text-[10px] text-muted-foreground">
          {/* Plan 03 placeholder — replaced by the full editor form. Ownership flags are visible
              for executor verification: isOwnPrivate / isOwnGlobal / isOtherGlobal. */}
          {isOwnPrivate && 'own private'}
          {isOwnGlobal && 'own global'}
          {isOtherGlobal && 'other global'}
        </p>
        {errorBanner && (
          <div
            role="alert"
            className="bg-destructive/10 text-destructive border border-destructive/30 text-xs px-3 py-2 rounded-md"
          >
            {errorBanner}
          </div>
        )}
        {/* Try in Chat stub — Plan 03 moves this into the editor footer, but expose it here
            so the tryInChat function is reachable and the compiler does not tree-shake it. */}
        {selectedSkill && (
          <Button
            size="sm"
            variant="outline"
            className="text-xs"
            onClick={() => tryInChat(selectedSkill)}
          >
            {t('skills.tryInChat')}
          </Button>
        )}
      </div>
    )
  }

  // Suppress unused variable warning for skillFiles setter — consumed by Plan 03/04 via the
  // exported setSkillFiles / skillFiles surface. Referencing here keeps tsc happy.
  void (skillFiles.length >= 0)
  void (formDisabled)

  // Suppress unused variable warning for Trash2, Loader2 — imported for use in Plan 03.
  void Trash2
  void Loader2

  return (
    <div className="flex h-full">
      {/* Hidden file input for "Import from File" — Plan 04 wires onChange */}
      <input
        ref={importInputRef}
        type="file"
        accept=".zip,application/zip"
        className="hidden"
        data-testid="skills-import-input"
        onChange={() => { /* Plan 04 wires the import handler */ }}
      />

      {/* Mobile FAB */}
      <button
        onClick={() => setMobilePanelOpen(true)}
        className="md:hidden fixed bottom-4 right-4 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg focus-ring"
        aria-label={t('skills.title')}
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Mobile panel overlay */}
      {mobilePanelOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div className="mobile-backdrop" onClick={() => setMobilePanelOpen(false)} />
          <div className="mobile-panel bg-background border-r border-border/50 flex flex-col">
            <div className="flex items-center justify-between px-5 py-3 border-b border-border/50">
              <div>
                <h1 className="text-sm font-semibold">{t('skills.title')}</h1>
                <p className="text-[10px] text-muted-foreground">
                  {t('skills.count', { n: String(skills.length) })}
                </p>
              </div>
              <button
                onClick={() => setMobilePanelOpen(false)}
                className="text-muted-foreground hover:text-foreground focus-ring"
                aria-label={t('skills.cancel')}
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            </div>
            {renderPanel()}
          </div>
        </div>
      )}

      {/* Desktop list panel */}
      {!panelCollapsed && (
        <div className="hidden md:flex w-[340px] shrink-0 flex-col border-r border-border/50 bg-sidebar">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border/50">
            <div>
              <h1 className="text-sm font-semibold">{t('skills.title')}</h1>
              <p className="text-[10px] text-muted-foreground">
                {t('skills.count', { n: String(skills.length) })}
              </p>
            </div>
            <button
              onClick={togglePanel}
              className="flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors focus-ring"
              aria-label={t('skills.cancel')}
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </div>
          {renderPanel()}
        </div>
      )}

      {/* Right column — editor placeholder (Plan 03 fills) */}
      <div className="flex-1 overflow-y-auto bg-background">
        {renderEditor()}
      </div>
    </div>
  )
}
