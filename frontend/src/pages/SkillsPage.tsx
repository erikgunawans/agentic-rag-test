import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Plus, Pencil, Trash2, X, Menu, ChevronLeft, PanelLeftClose,
  Globe, Search, Sparkles, FileArchive, Loader2, Zap,
  Save, Download, Share2, MessageSquare, FileText, FileCode,
  File, Copy, Check, Upload,
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

  // ---- Form state ----
  const [formName, setFormName] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formInstructions, setFormInstructions] = useState('')
  const [formLicense, setFormLicense] = useState('')
  const [formCompatibility, setFormCompatibility] = useState('')
  const [formEnabled, setFormEnabled] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [sharing, setSharing] = useState(false)

  // ---- File preview state ----
  interface PreviewFileState {
    fileId: string
    filename: string
    mimeType: string | null
    content: string | null  // null = binary
    truncated: boolean
    totalBytes: number
  }
  const [previewFile, setPreviewFile] = useState<PreviewFileState | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [copyState, setCopyState] = useState<'idle' | 'copied'>('idle')
  const [uploading, setUploading] = useState(false)

  // ---- Import state ----
  interface ImportResult { name: string; status: 'created' | 'error' | 'skipped'; skill_id?: string; error?: string }
  interface ImportSummary { created_count: number; error_count: number; results: ImportResult[] }
  const [importInProgress, setImportInProgress] = useState(false)
  const [importSummary, setImportSummary] = useState<ImportSummary | null>(null)

  const textareaClass = `${inputClass} min-h-[100px] resize-none`
  const instructionsClass = `${inputClass} min-h-[240px] resize-none font-mono`

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

  // ---- Hydrate form when selectedSkill changes ----
  useEffect(() => {
    if (editMode === 'edit' && selectedSkill) {
      setFormName(selectedSkill.name)
      setFormDescription(selectedSkill.description)
      setFormInstructions(selectedSkill.instructions || '')
      setFormLicense(selectedSkill.license || '')
      setFormCompatibility(selectedSkill.compatibility || '')
      setFormEnabled(selectedSkill.enabled)
    } else if (editMode === 'create') {
      setFormName('')
      setFormDescription('')
      setFormInstructions('')
      setFormLicense('')
      setFormCompatibility('')
      setFormEnabled(true)
    }
  }, [editMode, selectedSkill])

  // ---- Body scroll lock + Escape key when preview drawer is open ----
  useEffect(() => {
    if (!previewFile) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closePreview()
    }
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [previewFile])

  // ---- Selection / ownership branch ----
  async function selectSkill(skill: Skill) {
    setEditMode('edit')
    setMobilePanelOpen(false)
    setErrorBanner(null)
    setDetailLoading(true)
    setSelectedSkill(skill)
    setPreviewFile(null)
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
    setPreviewFile(null)
    setMobilePanelOpen(false)
  }

  function resetEditor() {
    setEditMode(null)
    setSelectedSkill(null)
    setSkillFiles([])
    setErrorBanner(null)
    setPreviewFile(null)
    setFormName('')
    setFormDescription('')
    setFormInstructions('')
    setFormLicense('')
    setFormCompatibility('')
    setFormEnabled(true)
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

  // ---- Validation helpers ----
  const NAME_RE = /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/
  const NAME_MAX = 64
  const DESC_MAX = 1024

  function validateForm(): string | null {
    if (!formName.trim()) return t('skills.errorNameFormat')
    if (formName.length > NAME_MAX) return t('skills.errorNameFormat')
    if (!NAME_RE.test(formName)) return t('skills.errorNameFormat')
    if (!formDescription.trim()) return t('skills.errorSave')
    if (formDescription.length > DESC_MAX) return t('skills.errorSave')
    if (!formInstructions.trim()) return t('skills.errorSave')
    return null
  }

  async function handleSave() {
    const err = validateForm()
    if (err) { setErrorBanner(err); return }
    setSaving(true)
    setErrorBanner(null)
    try {
      const body = {
        name: formName.trim(),
        description: formDescription,
        instructions: formInstructions,
        enabled: formEnabled,
        license: formLicense.trim() || null,
        compatibility: formCompatibility.trim() || null,
      }
      let saved: Skill | null = null
      if (editMode === 'create') {
        const res = await apiFetch('/skills', { method: 'POST', body: JSON.stringify(body) })
        const data = await res.json()
        saved = (data.data ?? data) as Skill
      } else if (editMode === 'edit' && selectedSkill) {
        const res = await apiFetch(`/skills/${selectedSkill.id}`, { method: 'PATCH', body: JSON.stringify(body) })
        const data = await res.json()
        saved = (data.data ?? data) as Skill
      }
      await fetchSkills()
      if (saved) {
        setSelectedSkill(saved)
        setEditMode('edit')
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : ''
      if (/already exists/i.test(msg)) {
        setErrorBanner(t('skills.errorNameConflict'))
      } else if (/lowercase|hyphen|format/i.test(msg)) {
        setErrorBanner(t('skills.errorNameFormat'))
      } else {
        setErrorBanner(t('skills.errorSave'))
      }
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!selectedSkill) return
    if (!confirm(t('skills.deleteConfirm'))) return
    setDeleting(true)
    setErrorBanner(null)
    try {
      await apiFetch(`/skills/${selectedSkill.id}`, { method: 'DELETE' })
      await fetchSkills()
      resetEditor()
    } catch {
      setErrorBanner(t('skills.errorDelete'))
    } finally {
      setDeleting(false)
    }
  }

  async function handleShare(makeGlobal: boolean) {
    if (!selectedSkill) return
    if (!makeGlobal && !confirm(t('skills.unshareConfirm'))) return
    setSharing(true)
    setErrorBanner(null)
    try {
      const res = await apiFetch(`/skills/${selectedSkill.id}/share`, { method: 'PATCH', body: JSON.stringify({ global: makeGlobal }) })
      const data = await res.json()
      const updated = (data.data ?? data) as Skill
      setSelectedSkill(updated)
      await fetchSkills()
    } catch {
      setErrorBanner(t('skills.errorSave'))
    } finally {
      setSharing(false)
    }
  }

  async function handleExport() {
    if (!selectedSkill) return
    try {
      const res = await apiFetch(`/skills/${selectedSkill.id}/export`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${selectedSkill.name}.zip`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      setErrorBanner(t('skills.errorSave'))
    }
  }

  // ---- File helpers ----
  function fileIconFor(mime: string | null) {
    if (mime && mime.startsWith('text/')) return FileText
    if (mime && mime.startsWith('application/') && /(json|xml|yaml|javascript|typescript|markdown)/.test(mime)) return FileCode
    return File
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''  // allow re-upload of same filename later
    if (!file || !selectedSkill) return
    if (file.size > 10 * 1024 * 1024) {
      setErrorBanner(t('skills.errorFileSize'))
      return
    }
    setUploading(true)
    setErrorBanner(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      await apiFetch(`/skills/${selectedSkill.id}/files`, { method: 'POST', body: formData })
      // Re-fetch file list
      const filesRes = await apiFetch(`/skills/${selectedSkill.id}/files`)
      const filesBody = await filesRes.json()
      setSkillFiles(filesBody.data || [])
    } catch {
      setErrorBanner(t('skills.errorUpload'))
    } finally {
      setUploading(false)
    }
  }

  async function handleDeleteFile(fileId: string, filename: string) {
    if (!selectedSkill) return
    if (!confirm(t('skills.fileDeleteConfirm'))) return
    try {
      await apiFetch(`/skills/${selectedSkill.id}/files/${fileId}`, { method: 'DELETE' })
      // Re-fetch file list
      const filesRes = await apiFetch(`/skills/${selectedSkill.id}/files`)
      const filesBody = await filesRes.json()
      setSkillFiles(filesBody.data || [])
      // Close preview if it was showing this file
      if (previewFile?.fileId === fileId) setPreviewFile(null)
    } catch {
      setErrorBanner(t('skills.errorUpload'))
    }
    void filename  // suppress unused parameter warning
  }

  async function openPreview(file: SkillFile) {
    if (!selectedSkill) return
    setPreviewLoading(true)
    setPreviewFile({
      fileId: file.id,
      filename: file.filename,
      mimeType: file.mime_type,
      content: null,
      truncated: false,
      totalBytes: file.size_bytes,
    })
    try {
      const res = await apiFetch(`/skills/${selectedSkill.id}/files/${file.id}/content`)
      const body = await res.json()
      // Backend response shape (per D-P8-12 / D-P8-13):
      //   text:   { filename, content, truncated, total_bytes, mime_type }
      //   binary: { filename, mime_type, size_bytes, readable: false, message }
      if (body.readable === false || typeof body.content !== 'string') {
        setPreviewFile({
          fileId: file.id,
          filename: body.filename ?? file.filename,
          mimeType: body.mime_type ?? file.mime_type,
          content: null,
          truncated: false,
          totalBytes: body.size_bytes ?? file.size_bytes,
        })
      } else {
        setPreviewFile({
          fileId: file.id,
          filename: body.filename ?? file.filename,
          mimeType: body.mime_type ?? file.mime_type,
          content: body.content,
          truncated: Boolean(body.truncated),
          totalBytes: body.total_bytes ?? file.size_bytes,
        })
      }
    } catch {
      setErrorBanner(t('skills.errorUpload'))
      setPreviewFile(null)
    } finally {
      setPreviewLoading(false)
    }
  }

  function closePreview() {
    setPreviewFile(null)
    setCopyState('idle')
  }

  async function handleCopy() {
    if (!previewFile?.content) return
    try {
      await navigator.clipboard.writeText(previewFile.content)
      setCopyState('copied')
      setTimeout(() => setCopyState('idle'), 1500)
    } catch {
      // clipboard API can fail on http (non-localhost); silently no-op.
    }
  }

  function handleDownloadPreview() {
    if (!previewFile) return
    if (previewFile.content !== null) {
      // Text — download from in-memory content as blob
      const blob = new Blob([previewFile.content], { type: previewFile.mimeType ?? 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = previewFile.filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } else {
      // Binary — backend returns metadata-only (D-P8-13), no raw byte endpoint.
      // Fall back to re-fetching via the content endpoint with Accept: application/octet-stream.
      // If unsupported, the request will return JSON metadata again; we silently no-op.
      if (!selectedSkill) return
      apiFetch(`/skills/${selectedSkill.id}/files/${previewFile.fileId}/content`, {
        headers: { 'Accept': 'application/octet-stream' },
      })
        .then(r => r.blob())
        .then(blob => {
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = previewFile.filename
          document.body.appendChild(a)
          a.click()
          document.body.removeChild(a)
          URL.revokeObjectURL(url)
        })
        .catch(() => setErrorBanner(t('skills.errorUpload')))
    }
  }

  // ---- Import from ZIP flow ----
  async function handleImportZip(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setImportInProgress(true)
    setErrorBanner(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await apiFetch('/skills/import', { method: 'POST', body: formData })
      const body = (await res.json()) as ImportSummary
      setImportSummary(body)
      await fetchSkills()
    } catch {
      setErrorBanner(t('skills.errorImport'))
    } finally {
      setImportInProgress(false)
    }
  }

  // Hidden file input refs
  const importInputRef = useRef<HTMLInputElement>(null)
  const uploadInputRef = useRef<HTMLInputElement>(null)

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

  // ---- Full editor form ----
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

    const requiredMark = <span className="text-red-600 dark:text-red-400" aria-hidden="true">*</span>
    const overName = formName.length > NAME_MAX
    const overDesc = formDescription.length > DESC_MAX

    return (
      <div className={`px-5 py-4 space-y-3 max-w-[900px] ${formDisabled ? 'opacity-60 pointer-events-none' : ''}`} aria-disabled={formDisabled || undefined}>
        {/* Header with title + close button */}
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold">
            {editMode === 'create' ? t('skills.createManual') : selectedSkill?.name ?? ''}
          </h2>
          <button
            onClick={resetEditor}
            className="text-muted-foreground hover:text-foreground"
            aria-label={t('skills.cancel')}
            style={{ pointerEvents: 'auto' }}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Ownership banner */}
        {isOwnGlobal && (
          <div role="status" className="bg-primary/10 text-primary text-xs px-4 py-2 rounded-md border border-primary/20 flex items-center gap-2">
            <Globe className="h-3 w-3 shrink-0" />
            <span>{t('skills.bannerOwnerGlobal')}</span>
          </div>
        )}
        {isOtherGlobal && (
          <div role="status" className="bg-primary/10 text-primary text-xs px-4 py-2 rounded-md border border-primary/20 flex items-center gap-2">
            <Globe className="h-3 w-3 shrink-0" />
            <span>{t('skills.bannerGlobal')}</span>
          </div>
        )}

        {/* Inline error banner */}
        {errorBanner && (
          <div role="alert" className="bg-destructive/10 text-destructive border border-destructive/30 text-xs px-3 py-2 rounded-md flex items-start gap-2">
            <span className="flex-1">{errorBanner}</span>
            <button onClick={() => setErrorBanner(null)} aria-label={t('skills.cancel')} style={{ pointerEvents: 'auto' }}>
              <X className="h-3 w-3" />
            </button>
          </div>
        )}

        {/* Name */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="skill-name" className="text-[10px] font-medium">
              {t('skills.fieldName')} {requiredMark}
            </label>
            <span className={`text-[9px] ${overName ? 'text-destructive' : 'text-muted-foreground'}`}>
              {formName.length}/{NAME_MAX}
            </span>
          </div>
          <input
            id="skill-name"
            aria-required="true"
            aria-disabled={formDisabled || undefined}
            disabled={formDisabled}
            className={inputClass}
            value={formName}
            onChange={e => setFormName(e.target.value)}
            placeholder={t('skills.placeholderName')}
          />
        </div>

        {/* Description */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="skill-description" className="text-[10px] font-medium">
              {t('skills.fieldDescription')} {requiredMark}
            </label>
            <span className={`text-[9px] ${overDesc ? 'text-destructive' : 'text-muted-foreground'}`}>
              {formDescription.length}/{DESC_MAX}
            </span>
          </div>
          <textarea
            id="skill-description"
            aria-required="true"
            aria-disabled={formDisabled || undefined}
            disabled={formDisabled}
            className={textareaClass}
            value={formDescription}
            onChange={e => setFormDescription(e.target.value)}
            placeholder={t('skills.placeholderDescription')}
          />
        </div>

        {/* Instructions (monospace, 240px min-h) */}
        <div className="space-y-1.5">
          <label htmlFor="skill-instructions" className="text-[10px] font-medium">
            {t('skills.fieldInstructions')} {requiredMark}
          </label>
          <textarea
            id="skill-instructions"
            aria-required="true"
            aria-disabled={formDisabled || undefined}
            disabled={formDisabled}
            className={instructionsClass}
            value={formInstructions}
            onChange={e => setFormInstructions(e.target.value)}
            placeholder={t('skills.placeholderInstructions')}
          />
        </div>

        {/* License + Compatibility (grid) */}
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1.5">
            <label htmlFor="skill-license" className="text-[10px] font-medium">{t('skills.fieldLicense')}</label>
            <input
              id="skill-license"
              aria-disabled={formDisabled || undefined}
              disabled={formDisabled}
              className={inputClass}
              value={formLicense}
              onChange={e => setFormLicense(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="skill-compat" className="text-[10px] font-medium">{t('skills.fieldCompatibility')}</label>
            <input
              id="skill-compat"
              aria-disabled={formDisabled || undefined}
              disabled={formDisabled}
              className={inputClass}
              value={formCompatibility}
              onChange={e => setFormCompatibility(e.target.value)}
            />
          </div>
        </div>

        {/* Files section — Plan 04 implementation */}
        <div className="space-y-1.5" data-testid="skills-files-section-slot">
          <div className="flex items-center justify-between">
            <p className="text-[10px] font-medium">{t('skills.filesSection')}</p>
            {isOwnPrivate && editMode === 'edit' && (
              <>
                <input
                  ref={uploadInputRef}
                  type="file"
                  className="hidden"
                  data-testid="skills-upload-input"
                  onChange={handleUpload}
                />
                <Button
                  size="sm"
                  variant="outline"
                  className="text-xs"
                  onClick={() => uploadInputRef.current?.click()}
                  disabled={uploading}
                  style={{ pointerEvents: 'auto' }}
                >
                  {uploading
                    ? <><Loader2 className="animate-spin h-3 w-3 mr-1.5" />{t('skills.uploading')}</>
                    : <><Upload className="h-3 w-3 mr-1.5" />{t('skills.upload')}</>}
                </Button>
              </>
            )}
          </div>
          {skillFiles.length === 0 ? (
            <p className="text-[10px] text-muted-foreground py-2">{t('skills.filesEmpty')}</p>
          ) : (
            <div className="rounded-md border border-border/50 overflow-hidden">
              {skillFiles.map(file => {
                const Icon = fileIconFor(file.mime_type)
                const isSelected = previewFile?.fileId === file.id
                return (
                  <div
                    key={file.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => openPreview(file)}
                    onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPreview(file) } }}
                    className={`flex items-center gap-2 px-3 py-2 border-b border-border/50 last:border-b-0 cursor-pointer transition-colors focus-ring ${isSelected ? 'bg-primary/10 text-primary' : 'hover:bg-muted/50'}`}
                  >
                    <Icon className="h-3.5 w-3.5 shrink-0" />
                    <span className="text-xs truncate flex-1">{file.filename}</span>
                    <span className="text-[10px] text-muted-foreground shrink-0">{formatFileSize(file.size_bytes)}</span>
                    <span className="text-[9px] text-muted-foreground shrink-0 max-w-[120px] truncate">{file.mime_type ?? ''}</span>
                    {isOwnPrivate && (
                      <button
                        type="button"
                        onClick={e => { e.stopPropagation(); handleDeleteFile(file.id, file.filename) }}
                        className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 focus-ring"
                        aria-label={`${t('skills.delete')} ${file.filename}`}
                        style={{ pointerEvents: 'auto' }}
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer: Enabled toggle (left) + action buttons (right) */}
        <div className="flex items-center justify-between gap-2 pt-2 border-t border-border/50">
          <div className="flex items-center gap-2">
            <button
              type="button"
              role="switch"
              aria-checked={formEnabled}
              aria-disabled={formDisabled || undefined}
              disabled={formDisabled}
              onClick={() => !formDisabled && setFormEnabled(v => !v)}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors ${formEnabled ? 'bg-primary' : 'bg-muted'} ${formDisabled ? 'cursor-not-allowed' : ''}`}
              style={{ pointerEvents: 'auto' }}
            >
              <span className={`inline-block h-4 w-4 rounded-full bg-background shadow transform transition-transform ${formEnabled ? 'translate-x-[18px]' : 'translate-x-0.5'} mt-0.5`} />
            </button>
            <span className="text-xs">{t('skills.fieldEnabled')}</span>
          </div>

          <div className="flex flex-wrap items-center gap-2 justify-end">
            {/* Save — only if not formDisabled (own private OR create mode) */}
            {!formDisabled && (
              <Button
                size="sm"
                className="text-xs"
                onClick={handleSave}
                disabled={saving || !formName.trim() || !formDescription.trim() || !formInstructions.trim() || overName || overDesc}
                style={{ pointerEvents: 'auto' }}
              >
                {saving ? <><Loader2 className="animate-spin h-3 w-3 mr-1.5" />{t('skills.saving')}</> : <><Save className="h-3 w-3 mr-1.5" />{t('skills.save')}</>}
              </Button>
            )}

            {/* Cancel — visible in create mode */}
            {editMode === 'create' && (
              <Button
                size="sm"
                variant="outline"
                className="text-xs"
                onClick={resetEditor}
                style={{ pointerEvents: 'auto' }}
              >
                {t('skills.cancel')}
              </Button>
            )}

            {/* Delete — only on own private skills (NOT global, NOT create mode) */}
            {isOwnPrivate && (
              <Button
                size="sm"
                variant="outline"
                className="text-xs text-destructive hover:bg-destructive/10"
                onClick={handleDelete}
                disabled={deleting}
                style={{ pointerEvents: 'auto' }}
              >
                {deleting ? <Loader2 className="animate-spin h-3 w-3 mr-1.5" /> : <Trash2 className="h-3 w-3 mr-1.5" />}
                {t('skills.delete')}
              </Button>
            )}

            {/* Share — only on own private skills */}
            {isOwnPrivate && (
              <Button
                size="sm"
                variant="outline"
                className="text-xs"
                onClick={() => handleShare(true)}
                disabled={sharing}
                style={{ pointerEvents: 'auto' }}
              >
                {sharing ? <Loader2 className="animate-spin h-3 w-3 mr-1.5" /> : <Share2 className="h-3 w-3 mr-1.5" />}
                {t('skills.share')}
              </Button>
            )}

            {/* Unshare — only on own global skills */}
            {isOwnGlobal && (
              <Button
                size="sm"
                variant="outline"
                className="text-xs"
                onClick={() => handleShare(false)}
                disabled={sharing}
                style={{ pointerEvents: 'auto' }}
              >
                {sharing ? <Loader2 className="animate-spin h-3 w-3 mr-1.5" /> : <Share2 className="h-3 w-3 mr-1.5" />}
                {t('skills.unshare')}
              </Button>
            )}

            {/* Export — visible whenever a skill is selected (own private, own global, other global) */}
            {selectedSkill && editMode === 'edit' && (
              <Button
                size="sm"
                variant="outline"
                className="text-xs"
                onClick={handleExport}
                style={{ pointerEvents: 'auto' }}
              >
                <Download className="h-3 w-3 mr-1.5" />
                {t('skills.export')}
              </Button>
            )}

            {/* Try in Chat — visible whenever a skill is selected */}
            {selectedSkill && editMode === 'edit' && (
              <Button
                size="sm"
                className="text-xs"
                onClick={() => tryInChat(selectedSkill)}
                style={{ pointerEvents: 'auto' }}
              >
                <MessageSquare className="h-3 w-3 mr-1.5" />
                {t('skills.tryInChat')}
              </Button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full">
      {/* Hidden file input for "Import from File" — wired to handleImportZip */}
      <input
        ref={importInputRef}
        type="file"
        accept=".zip,application/zip"
        className="hidden"
        data-testid="skills-import-input"
        onChange={handleImportZip}
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

      {/* Right column — editor */}
      <div className="flex-1 overflow-y-auto bg-background">
        {renderEditor()}
      </div>

      {/* File preview drawer */}
      {previewFile && (
        <>
          <div
            className="fixed inset-0 z-30 bg-black/40 backdrop-blur-sm motion-safe:transition-opacity motion-safe:duration-200"
            onClick={closePreview}
            aria-hidden="true"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="skills-preview-title"
            className="fixed inset-y-0 right-0 z-40 w-full md:w-[480px] bg-card border-l border-border shadow-lg flex flex-col motion-safe:transition-transform motion-safe:duration-200 ease-out"
          >
            <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between gap-2">
              <h2 id="skills-preview-title" className="text-xs font-semibold truncate flex-1">{previewFile.filename}</h2>
              <div className="flex items-center gap-1 shrink-0">
                {previewFile.content !== null && (
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted/50 focus-ring"
                    aria-label={t('skills.previewCopy')}
                    title={copyState === 'copied' ? t('skills.previewCopied') : t('skills.previewCopy')}
                  >
                    {copyState === 'copied' ? <Check className="h-3.5 w-3.5 text-primary" /> : <Copy className="h-3.5 w-3.5" />}
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleDownloadPreview}
                  className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted/50 focus-ring"
                  aria-label={t('skills.previewDownload')}
                >
                  <Download className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={closePreview}
                  className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted/50 focus-ring"
                  aria-label={t('skills.previewClose')}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto">
              {previewLoading ? (
                <div className="shimmer h-full m-4" />
              ) : previewFile.content === null ? (
                <div className="flex flex-col items-center justify-center h-full text-center px-6">
                  <File className="h-10 w-10 text-muted-foreground/40 mb-3" />
                  <p className="text-xs text-muted-foreground mb-3">{t('skills.previewBinary')}</p>
                  <Button size="sm" onClick={handleDownloadPreview}>
                    <Download className="h-3 w-3 mr-1.5" />
                    {t('skills.previewDownload')}
                  </Button>
                </div>
              ) : (
                <>
                  <pre className="font-mono text-xs leading-relaxed whitespace-pre-wrap break-words p-4">{previewFile.content}</pre>
                  {previewFile.truncated && (
                    <div className="px-4 py-2 border-t border-border/50 bg-muted/30 text-[10px] text-muted-foreground">
                      {t('skills.previewTruncated')}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </>
      )}

      {/* Import progress / summary overlay */}
      {(importInProgress || importSummary) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm motion-safe:transition-opacity motion-safe:duration-200">
          <div className="bg-card border border-border rounded-lg shadow-lg p-6 max-w-md w-[90%] max-h-[80vh] overflow-auto">
            {importInProgress && (
              <div className="flex items-center gap-3">
                <Loader2 className="animate-spin h-4 w-4 text-primary" />
                <p className="text-xs">{t('skills.importInProgress', { n: '0', total: '0' })}</p>
              </div>
            )}
            {importSummary && !importInProgress && (
              <div className="space-y-3">
                <h2 className="text-sm font-semibold">
                  {t('skills.importSummary', { created: String(importSummary.created_count), errors: String(importSummary.error_count) })}
                </h2>
                {importSummary.results.length > 0 && (
                  <ul className="space-y-1 text-xs max-h-[40vh] overflow-auto">
                    {importSummary.results.map((r, i) => (
                      <li key={i} className={`flex items-start gap-2 ${r.status === 'error' ? 'text-destructive' : r.status === 'skipped' ? 'text-muted-foreground' : ''}`}>
                        <span className="font-mono shrink-0">[{r.status}]</span>
                        <span className="font-mono">{r.name}</span>
                        {r.error && <span className="text-muted-foreground">— {r.error}</span>}
                      </li>
                    ))}
                  </ul>
                )}
                <div className="flex justify-end">
                  <Button size="sm" variant="outline" className="text-xs" onClick={() => setImportSummary(null)}>
                    {t('skills.importClose')}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
