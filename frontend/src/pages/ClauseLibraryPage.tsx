import { useState, useEffect, useCallback } from 'react'
import { Library, Plus, Pencil, Trash2, X, Menu, ChevronLeft, PanelLeftClose, Globe, Search } from 'lucide-react'
import { useSidebar } from '@/hooks/useSidebar'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { apiFetch } from '@/lib/api'

interface Clause {
  id: string
  title: string
  content: string
  category: string
  applicable_doc_types: string[]
  risk_level: string
  language: string
  tags: string[]
  is_global: boolean
}

const RISK_STYLE: Record<string, { color: string; bg: string; label: string }> = {
  high: { color: 'text-red-400', bg: 'border-red-500/30 bg-red-500/5', label: 'HIGH' },
  medium: { color: 'text-amber-400', bg: 'border-amber-500/30 bg-amber-500/5', label: 'MEDIUM' },
  low: { color: 'text-green-400', bg: 'border-green-500/30 bg-green-500/5', label: 'LOW' },
}

const CATEGORIES = [
  'confidentiality', 'termination', 'payment', 'liability', 'indemnity',
  'force_majeure', 'dispute_resolution', 'compliance', 'intellectual_property', 'general',
]

const DOC_TYPES = [
  'generic', 'nda', 'sales', 'service', 'vendor', 'jv', 'property_lease', 'employment', 'sop_resolution',
]

const inputBase = "w-full rounded-lg bg-secondary text-foreground px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
const inputClass = `${inputBase} border border-border`
const textareaClass = `${inputClass} min-h-[100px] resize-none`

export function ClauseLibraryPage() {
  const { t } = useI18n()
  const { panelCollapsed, togglePanel } = useSidebar()
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)

  const [clauses, setClauses] = useState<Clause[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [riskFilter, setRiskFilter] = useState('')

  const [editMode, setEditMode] = useState<'create' | 'edit' | null>(null)
  const [editingClause, setEditingClause] = useState<Clause | null>(null)
  const [formTitle, setFormTitle] = useState('')
  const [formContent, setFormContent] = useState('')
  const [formCategory, setFormCategory] = useState('general')
  const [formRisk, setFormRisk] = useState('low')
  const [formLanguage, setFormLanguage] = useState('both')
  const [formTags, setFormTags] = useState('')
  const [formDocTypes, setFormDocTypes] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

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

  useEffect(() => {
    const timer = setTimeout(fetchClauses, 300)
    return () => clearTimeout(timer)
  }, [fetchClauses])

  function resetForm() {
    setEditMode(null)
    setEditingClause(null)
    setFormTitle('')
    setFormContent('')
    setFormCategory('general')
    setFormRisk('low')
    setFormLanguage('both')
    setFormTags('')
    setFormDocTypes([])
  }

  function startCreate() {
    resetForm()
    setEditMode('create')
  }

  function startEdit(clause: Clause) {
    setEditMode('edit')
    setEditingClause(clause)
    setFormTitle(clause.title)
    setFormContent(clause.content)
    setFormCategory(clause.category)
    setFormRisk(clause.risk_level)
    setFormLanguage(clause.language)
    setFormTags(clause.tags.join(', '))
    setFormDocTypes(clause.applicable_doc_types)
  }

  async function handleSave() {
    if (!formTitle.trim() || !formContent.trim()) return
    setSaving(true)
    try {
      const body = {
        title: formTitle,
        content: formContent,
        category: formCategory,
        risk_level: formRisk,
        language: formLanguage,
        tags: formTags.split(',').map(s => s.trim()).filter(Boolean),
        applicable_doc_types: formDocTypes,
      }
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

  async function handleDelete(id: string) {
    if (!confirm('Delete this clause?')) return
    try {
      await apiFetch(`/clause-library/${id}`, { method: 'DELETE' })
      fetchClauses()
    } catch {
      alert('Failed to delete clause')
    }
  }

  function toggleDocType(dt: string) {
    setFormDocTypes(prev => prev.includes(dt) ? prev.filter(d => d !== dt) : [...prev, dt])
  }

  // --- Filter/Form panel content (shared between mobile + desktop) ---
  function renderPanel() {
    if (editMode) {
      return (
        <div className="px-5 py-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs font-semibold">{editMode === 'create' ? t('clauseLibrary.create') : t('clauseLibrary.edit')}</h2>
            <button onClick={resetForm} className="text-muted-foreground hover:text-foreground"><X className="h-3.5 w-3.5" /></button>
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-medium">Title <span className="text-red-400">*</span></label>
            <input className={inputClass} value={formTitle} onChange={e => setFormTitle(e.target.value)} placeholder="Clause title" />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-medium">{t('clauseLibrary.content')} <span className="text-red-400">*</span></label>
            <textarea className={textareaClass} value={formContent} onChange={e => setFormContent(e.target.value)} placeholder="Clause text..." />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1.5">
              <label className="text-[10px] font-medium">{t('clauseLibrary.category')}</label>
              <select className={inputClass} value={formCategory} onChange={e => setFormCategory(e.target.value)}>
                {CATEGORIES.map(c => <option key={c} value={c}>{t(`clauseCategory.${c}`)}</option>)}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-[10px] font-medium">{t('clauseLibrary.risk')}</label>
              <select className={inputClass} value={formRisk} onChange={e => setFormRisk(e.target.value)}>
                <option value="low">{t('risk.low')}</option>
                <option value="medium">{t('risk.medium')}</option>
                <option value="high">{t('risk.high')}</option>
              </select>
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-medium">{t('clauseLibrary.docTypes')}</label>
            <div className="flex flex-wrap gap-1.5">
              {DOC_TYPES.map(dt => (
                <button
                  key={dt}
                  onClick={() => toggleDocType(dt)}
                  className={`text-[9px] px-2 py-0.5 rounded-full border transition-colors ${
                    formDocTypes.includes(dt) ? 'bg-primary/20 border-primary/40 text-primary' : 'border-border text-muted-foreground hover:border-foreground/30'
                  }`}
                >
                  {dt}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-medium">{t('clauseLibrary.tags')}</label>
            <input className={inputClass} value={formTags} onChange={e => setFormTags(e.target.value)} placeholder="tag1, tag2, ..." />
          </div>
          <div className="flex gap-2 pt-1">
            <Button size="sm" className="flex-1 text-xs" onClick={handleSave} disabled={saving || !formTitle.trim() || !formContent.trim()}>
              {saving ? 'Saving...' : t('clauseLibrary.save')}
            </Button>
            <Button size="sm" variant="outline" className="text-xs" onClick={resetForm}>
              {t('clauseLibrary.cancel')}
            </Button>
          </div>
        </div>
      )
    }

    return (
      <div className="px-5 py-4 space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
          <input
            className={`${inputClass} pl-8`}
            placeholder={t('clauseLibrary.search')}
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] font-medium">{t('clauseLibrary.category')}</label>
          <select className={inputClass} value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)}>
            <option value="">{t('clauseLibrary.allCategories')}</option>
            {CATEGORIES.map(c => <option key={c} value={c}>{t(`clauseCategory.${c}`)}</option>)}
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="text-[10px] font-medium">{t('clauseLibrary.risk')}</label>
          <select className={inputClass} value={riskFilter} onChange={e => setRiskFilter(e.target.value)}>
            <option value="">{t('clauseLibrary.allRisks')}</option>
            <option value="low">{t('risk.low')}</option>
            <option value="medium">{t('risk.medium')}</option>
            <option value="high">{t('risk.high')}</option>
          </select>
        </div>
        <Button size="sm" className="w-full text-xs" onClick={startCreate}>
          <Plus className="mr-1.5 h-3 w-3" /> {t('clauseLibrary.create')}
        </Button>
      </div>
    )
  }

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
              <div>
                <h1 className="text-sm font-semibold">{t('clauseLibrary.title')}</h1>
              </div>
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

      {/* Main content — clause cards */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <p className="text-xs text-muted-foreground">Loading...</p>
          </div>
        ) : clauses.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64">
            <Library className="h-10 w-10 text-muted-foreground/40 mb-3" />
            <p className="text-sm text-muted-foreground">{t('clauseLibrary.empty')}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 max-w-[900px]">
            {clauses.map(clause => {
              const risk = RISK_STYLE[clause.risk_level] || RISK_STYLE.low
              return (
                <div key={clause.id} className={`rounded-lg border p-4 space-y-2.5 ${risk.bg}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-xs font-semibold truncate">{clause.title}</h3>
                      <div className="flex items-center gap-1.5 mt-1">
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{t(`clauseCategory.${clause.category}`)}</span>
                        <span className={`text-[9px] font-bold uppercase ${risk.color}`}>{risk.label}</span>
                        {clause.is_global && (
                          <span className="flex items-center gap-0.5 text-[9px] text-primary">
                            <Globe className="h-2.5 w-2.5" /> {t('clauseLibrary.global')}
                          </span>
                        )}
                      </div>
                    </div>
                    {!clause.is_global && (
                      <div className="flex items-center gap-1 shrink-0">
                        <button onClick={() => startEdit(clause)} className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted/50">
                          <Pencil className="h-3 w-3" />
                        </button>
                        <button onClick={() => handleDelete(clause.id)} className="p-1 rounded text-muted-foreground hover:text-red-400 hover:bg-red-500/10">
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    )}
                  </div>
                  <p className="text-[10px] text-muted-foreground line-clamp-3">{clause.content}</p>
                  {clause.applicable_doc_types.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {clause.applicable_doc_types.map(dt => (
                        <span key={dt} className="text-[8px] px-1.5 py-0.5 rounded-full border border-border text-muted-foreground">{dt}</span>
                      ))}
                    </div>
                  )}
                  {clause.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {clause.tags.map(tag => (
                        <span key={tag} className="text-[8px] px-1.5 py-0.5 rounded-full bg-primary/10 text-primary">{tag}</span>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
