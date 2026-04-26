import { useCallback, useEffect, useState } from 'react'
import { Save, Shield, Brain, Database, Settings2, Wrench, ChevronLeft, PanelLeftClose, Menu, ShieldCheck } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { LLM_MODELS, EMBEDDING_MODELS } from '@/lib/models'
import { Button } from '@/components/ui/button'
import { useSidebar } from '@/hooks/useSidebar'
import { Separator } from '@/components/ui/separator'
import { useI18n } from '@/i18n/I18nContext'

interface SystemSettings {
  llm_model: string
  embedding_model: string
  rag_top_k: number
  rag_similarity_threshold: number
  rag_chunk_size: number
  rag_chunk_overlap: number
  rag_hybrid_enabled: boolean
  rag_rrf_k: number
  tools_enabled: boolean
  tools_max_iterations: number
  agents_enabled: boolean
  confidence_threshold: number
  // Phase 3: PII redaction & LLM provider (D-59 / D-60)
  entity_resolution_mode?: 'algorithmic' | 'llm' | 'none'
  llm_provider?: 'local' | 'cloud'
  llm_provider_fallback_enabled?: boolean
  entity_resolution_llm_provider?: 'local' | 'cloud' | null
  missed_scan_llm_provider?: 'local' | 'cloud' | null
  title_gen_llm_provider?: 'local' | 'cloud' | null
  metadata_llm_provider?: 'local' | 'cloud' | null
  fuzzy_deanon_llm_provider?: 'local' | 'cloud' | null
  pii_missed_scan_enabled?: boolean
}

interface LlmProviderStatus {
  cloud_key_configured: boolean
  local_endpoint_reachable: boolean
}

type AdminSection = 'llm' | 'embedding' | 'rag' | 'tools' | 'hitl' | 'pii'

const SECTIONS: { id: AdminSection; icon: typeof Brain; labelKey: string }[] = [
  { id: 'llm', icon: Brain, labelKey: 'admin.llm.title' },
  { id: 'embedding', icon: Database, labelKey: 'admin.embedding.title' },
  { id: 'rag', icon: Settings2, labelKey: 'admin.rag.title' },
  { id: 'tools', icon: Wrench, labelKey: 'admin.tools.title' },
  { id: 'hitl', icon: ShieldCheck, labelKey: 'admin.hitl.title' },
  { id: 'pii', icon: Shield, labelKey: 'admin.pii.title' },
]

const PER_FEATURE_OVERRIDES: { field: keyof SystemSettings; labelKey: string }[] = [
  { field: 'entity_resolution_llm_provider', labelKey: 'admin.pii.overrides.entityResolution' },
  { field: 'missed_scan_llm_provider', labelKey: 'admin.pii.overrides.missedScan' },
  { field: 'title_gen_llm_provider', labelKey: 'admin.pii.overrides.titleGen' },
  { field: 'metadata_llm_provider', labelKey: 'admin.pii.overrides.metadata' },
  { field: 'fuzzy_deanon_llm_provider', labelKey: 'admin.pii.overrides.fuzzyDeanon' },
]

const inputClass = "w-full rounded-md border bg-secondary text-foreground px-3 py-2 text-sm"

export function AdminSettingsPage() {
  const { t } = useI18n()
  const [settings, setSettings] = useState<SystemSettings | null>(null)
  const [form, setForm] = useState<Partial<SystemSettings>>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeSection, setActiveSection] = useState<AdminSection>('llm')
  const { panelCollapsed, togglePanel } = useSidebar()
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false)
  const [piiStatus, setPiiStatus] = useState<LlmProviderStatus | null>(null)

  // D-58: fetch masked status badge data for the PII section.
  // Endpoint returns booleans only; never the raw cloud key.
  useEffect(() => {
    if (activeSection !== 'pii') return
    let cancelled = false
    apiFetch('/admin/settings/llm-provider-status')
      .then((r) => r.json())
      .then((data: LlmProviderStatus) => {
        if (!cancelled) setPiiStatus(data)
      })
      .catch(() => {
        if (!cancelled) setPiiStatus({ cloud_key_configured: false, local_endpoint_reachable: false })
      })
    return () => { cancelled = true }
  }, [activeSection])

  const loadSettings = useCallback(async () => {
    const res = await apiFetch('/admin/settings')
    if (!res.ok) {
      setError(t('admin.error.load'))
      return
    }
    const data: SystemSettings = await res.json()
    setSettings(data)
    setForm(data)
  }, [t])

  useEffect(() => {
    loadSettings()
  }, [loadSettings])

  async function handleSave() {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      const res = await apiFetch('/admin/settings', {
        method: 'PATCH',
        body: JSON.stringify(form),
      })
      if (!res.ok) throw new Error(t('admin.error.save'))
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      await loadSettings()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('admin.error.save'))
    } finally {
      setSaving(false)
    }
  }

  const isDirty = settings !== null && JSON.stringify(form) !== JSON.stringify(settings)

  function updateField<K extends keyof SystemSettings>(key: K, value: SystemSettings[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <div className="flex h-full">
      {/* Mobile panel trigger */}
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
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-amber-500" />
                <div>
                  <h1 className="text-sm font-semibold">{t('admin.title')}</h1>
                  <p className="text-[10px] text-muted-foreground">Konfigurasi sistem</p>
                </div>
              </div>
              <button onClick={() => setMobilePanelOpen(false)} className="text-muted-foreground hover:text-foreground transition-colors focus-ring">
                <ChevronLeft className="h-4 w-4" />
              </button>
            </div>

            {/* Section nav */}
            <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
              {SECTIONS.map(({ id, icon: Icon, labelKey }) => (
                <button
                  key={id}
                  onClick={() => { setActiveSection(id); setMobilePanelOpen(false) }}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-xs font-medium transition-colors ${
                    activeSection === id ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5 shrink-0" />
                  {t(labelKey)}
                </button>
              ))}
            </div>

            {/* Status bar */}
            <div className="px-5 py-3 border-t border-border/50">
              <div className="flex items-center gap-2">
                <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium ${
                  isDirty ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400' : 'bg-green-500/10 text-green-600 dark:text-green-400'
                }`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${isDirty ? 'bg-amber-400' : 'bg-green-400'}`} />
                  {isDirty ? 'Unsaved changes' : 'All saved'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Column 2 — Admin nav panel */}
      {!panelCollapsed && (
      <div className="hidden md:flex w-[340px] shrink-0 flex-col border-r border-border/50 bg-sidebar">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-amber-500" />
            <div>
              <h1 className="text-sm font-semibold">{t('admin.title')}</h1>
              <p className="text-[10px] text-muted-foreground">Konfigurasi sistem</p>
            </div>
          </div>
          <button onClick={togglePanel} className="flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors focus-ring" title="Collapse sidebar">
            <PanelLeftClose className="h-4 w-4" />
          </button>
        </div>

        {/* Section nav */}
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
          {SECTIONS.map(({ id, icon: Icon, labelKey }) => (
            <button
              key={id}
              onClick={() => setActiveSection(id)}
              className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-xs font-medium transition-colors ${
                activeSection === id ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              }`}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              {t(labelKey)}
            </button>
          ))}
        </div>

        {/* Status bar */}
        <div className="px-5 py-3 border-t border-border/50">
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-medium ${
              isDirty ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400' : 'bg-green-500/10 text-green-600 dark:text-green-400'
            }`}>
              <span className={`h-1.5 w-1.5 rounded-full ${isDirty ? 'bg-amber-400' : 'bg-green-400'}`} />
              {isDirty ? 'Unsaved changes' : 'All saved'}
            </span>
          </div>
        </div>
      </div>
      )}

      {/* Column 3 — Admin content */}
      <div className="flex-1 flex flex-col overflow-y-auto">
        <div className="max-w-xl p-8 space-y-6">
          {activeSection === 'llm' && (
            <section className="space-y-4">
              <div>
                <h2 className="text-sm font-semibold">{t('admin.llm.title')}</h2>
                <p className="text-xs text-muted-foreground mt-0.5">{t('admin.llm.description')}</p>
              </div>
              <div className="space-y-2">
                {LLM_MODELS.map((m) => (
                  <label
                    key={m.value}
                    className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                      form.llm_model === m.value ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                    }`}
                  >
                    <input
                      type="radio"
                      name="llm_model"
                      value={m.value}
                      checked={form.llm_model === m.value}
                      onChange={() => updateField('llm_model', m.value)}
                      className="mt-0.5"
                    />
                    <div>
                      <p className="text-sm font-medium">{m.label}</p>
                      <p className="text-xs text-muted-foreground">{m.value} · {m.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            </section>
          )}

          {activeSection === 'embedding' && (
            <section className="space-y-4">
              <div>
                <h2 className="text-sm font-semibold">{t('admin.embedding.title')}</h2>
                <p className="text-xs text-muted-foreground mt-0.5">{t('admin.embedding.description')}</p>
              </div>
              <div className="space-y-2">
                {EMBEDDING_MODELS.map((m) => (
                  <label
                    key={m.value}
                    className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                      form.embedding_model === m.value ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                    }`}
                  >
                    <input
                      type="radio"
                      name="embedding_model"
                      value={m.value}
                      checked={form.embedding_model === m.value}
                      onChange={() => updateField('embedding_model', m.value)}
                      className="mt-0.5"
                    />
                    <div>
                      <p className="text-sm font-medium">{m.label}</p>
                      <p className="text-xs text-muted-foreground">{m.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            </section>
          )}

          {activeSection === 'rag' && (
            <section className="space-y-4">
              <div>
                <h2 className="text-sm font-semibold">{t('admin.rag.title')}</h2>
                <p className="text-xs text-muted-foreground mt-0.5">{t('admin.rag.description')}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-medium">{t('admin.rag.topK')}</label>
                  <input
                    type="number"
                    value={form.rag_top_k ?? 5}
                    onChange={(e) => updateField('rag_top_k', parseInt(e.target.value) || 5)}
                    className={inputClass}
                    min={1}
                    max={20}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium">{t('admin.rag.threshold')}</label>
                  <input
                    type="number"
                    step="0.05"
                    value={form.rag_similarity_threshold ?? 0.3}
                    onChange={(e) => updateField('rag_similarity_threshold', parseFloat(e.target.value) || 0.3)}
                    className={inputClass}
                    min={0}
                    max={1}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium">{t('admin.rag.chunkSize')}</label>
                  <input
                    type="number"
                    value={form.rag_chunk_size ?? 500}
                    onChange={(e) => updateField('rag_chunk_size', parseInt(e.target.value) || 500)}
                    className={inputClass}
                    min={100}
                    max={4000}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium">{t('admin.rag.chunkOverlap')}</label>
                  <input
                    type="number"
                    value={form.rag_chunk_overlap ?? 50}
                    onChange={(e) => updateField('rag_chunk_overlap', parseInt(e.target.value) || 50)}
                    className={inputClass}
                    min={0}
                    max={500}
                  />
                </div>
              </div>

              <Separator />

              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={form.rag_hybrid_enabled ?? true}
                  onChange={(e) => updateField('rag_hybrid_enabled', e.target.checked)}
                />
                <div>
                  <p className="text-sm font-medium">{t('admin.rag.hybrid')}</p>
                  <p className="text-xs text-muted-foreground">{t('admin.rag.hybridDesc')}</p>
                </div>
              </label>
              {form.rag_hybrid_enabled && (
                <div className="space-y-1 pl-7">
                  <label className="text-xs font-medium">{t('admin.rag.rrfK')}</label>
                  <input
                    type="number"
                    value={form.rag_rrf_k ?? 60}
                    onChange={(e) => updateField('rag_rrf_k', parseInt(e.target.value) || 60)}
                    className="w-32 rounded-md border bg-secondary text-foreground px-3 py-2 text-sm"
                    min={1}
                  />
                </div>
              )}
            </section>
          )}

          {activeSection === 'tools' && (
            <section className="space-y-4">
              <div>
                <h2 className="text-sm font-semibold">{t('admin.tools.title')}</h2>
                <p className="text-xs text-muted-foreground mt-0.5">{t('admin.tools.description')}</p>
              </div>
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={form.tools_enabled ?? true}
                  onChange={(e) => updateField('tools_enabled', e.target.checked)}
                />
                <div>
                  <p className="text-sm font-medium">{t('admin.tools.enable')}</p>
                  <p className="text-xs text-muted-foreground">{t('admin.tools.enableDesc')}</p>
                </div>
              </label>
              {form.tools_enabled && (
                <div className="space-y-1 pl-7">
                  <label className="text-xs font-medium">{t('admin.tools.maxIterations')}</label>
                  <input
                    type="number"
                    value={form.tools_max_iterations ?? 5}
                    onChange={(e) => updateField('tools_max_iterations', parseInt(e.target.value) || 5)}
                    className="w-32 rounded-md border bg-secondary text-foreground px-3 py-2 text-sm"
                    min={1}
                    max={20}
                  />
                </div>
              )}

              <Separator />

              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={form.agents_enabled ?? false}
                  onChange={(e) => updateField('agents_enabled', e.target.checked)}
                />
                <div>
                  <p className="text-sm font-medium">{t('admin.tools.agents')}</p>
                  <p className="text-xs text-muted-foreground">{t('admin.tools.agentsDesc')}</p>
                </div>
              </label>
            </section>
          )}

          {activeSection === 'hitl' && (
            <section className="space-y-4">
              <div>
                <h2 className="text-sm font-semibold">{t('admin.hitl.title')}</h2>
                <p className="text-xs text-muted-foreground mt-0.5">{t('admin.hitl.description')}</p>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">{t('admin.hitl.threshold')}</label>
                <p className="text-[10px] text-muted-foreground mb-1">{t('admin.hitl.thresholdDesc')}</p>
                <input
                  type="number"
                  step="0.05"
                  value={form.confidence_threshold ?? 0.85}
                  onChange={(e) => updateField('confidence_threshold', parseFloat(e.target.value) || 0.85)}
                  className={inputClass}
                  min={0}
                  max={1}
                />
              </div>
              <div className="rounded-lg border border-border bg-secondary/30 p-4 space-y-2">
                <p className="text-xs font-medium">{t('admin.hitl.preview')}</p>
                <div className="flex items-center gap-2 text-[10px]">
                  <span className="rounded-full border px-2 py-0.5 bg-green-500/10 border-green-500/30 text-green-600 dark:text-green-400 font-bold">
                    &ge; {((form.confidence_threshold ?? 0.85) * 100).toFixed(0)}% &rarr; AUTO-APPROVED
                  </span>
                  <span className="rounded-full border px-2 py-0.5 bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-400 font-bold">
                    &lt; {((form.confidence_threshold ?? 0.85) * 100).toFixed(0)}% &rarr; PENDING REVIEW
                  </span>
                </div>
              </div>
            </section>
          )}

          {activeSection === 'pii' && (
            <section className="space-y-4">
              <div>
                <h2 className="text-sm font-semibold">{t('admin.pii.title')}</h2>
                <p className="text-xs text-muted-foreground mt-0.5">{t('admin.pii.description')}</p>
              </div>

              {/* Status badges (D-58) — sourced from GET /admin/settings/llm-provider-status */}
              <div className="flex flex-wrap gap-2">
                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                    piiStatus?.cloud_key_configured
                      ? 'bg-green-500/10 border-green-500/30 text-green-600 dark:text-green-400'
                      : 'bg-red-500/10 border-red-500/30 text-red-600 dark:text-red-400'
                  }`}
                >
                  {piiStatus?.cloud_key_configured
                    ? t('admin.pii.cloudKey.configured')
                    : t('admin.pii.cloudKey.missing')}
                </span>
                <span
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                    piiStatus?.local_endpoint_reachable
                      ? 'bg-green-500/10 border-green-500/30 text-green-600 dark:text-green-400'
                      : 'bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-400'
                  }`}
                >
                  {piiStatus?.local_endpoint_reachable
                    ? t('admin.pii.localEndpoint.reachable')
                    : t('admin.pii.localEndpoint.unreachable')}
                </span>
              </div>

              {/* Mode (entity_resolution_mode) */}
              <div className="space-y-1">
                <label className="text-xs font-medium">{t('admin.pii.mode.label')}</label>
                <select
                  value={form.entity_resolution_mode ?? 'algorithmic'}
                  onChange={(e) =>
                    updateField('entity_resolution_mode', e.target.value as 'algorithmic' | 'llm' | 'none')
                  }
                  className={inputClass}
                >
                  <option value="algorithmic">{t('admin.pii.mode.algorithmic')}</option>
                  <option value="llm">{t('admin.pii.mode.llm')}</option>
                  <option value="none">{t('admin.pii.mode.none')}</option>
                </select>
              </div>

              {/* Global provider (llm_provider) */}
              <div className="space-y-1">
                <label className="text-xs font-medium">{t('admin.pii.provider.label')}</label>
                <select
                  value={form.llm_provider ?? 'local'}
                  onChange={(e) =>
                    updateField('llm_provider', e.target.value as 'local' | 'cloud')
                  }
                  className={inputClass}
                >
                  <option value="local">{t('admin.pii.provider.local')}</option>
                  <option value="cloud">{t('admin.pii.provider.cloud')}</option>
                </select>
              </div>

              <Separator />

              {/* Fallback toggle (llm_provider_fallback_enabled) */}
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={form.llm_provider_fallback_enabled ?? false}
                  onChange={(e) => updateField('llm_provider_fallback_enabled', e.target.checked)}
                />
                <div>
                  <p className="text-sm font-medium">{t('admin.pii.fallback.label')}</p>
                </div>
              </label>

              {/* Phase 4 forward-compat: secondary missed-PII scan (pii_missed_scan_enabled) */}
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={form.pii_missed_scan_enabled ?? true}
                  onChange={(e) => updateField('pii_missed_scan_enabled', e.target.checked)}
                />
                <div>
                  <p className="text-sm font-medium">{t('admin.pii.missedScan.label')}</p>
                </div>
              </label>

              <Separator />

              {/* Per-feature overrides (5 selects: Inherit / local / cloud) */}
              <div className="space-y-3">
                <h3 className="text-xs font-semibold">{t('admin.pii.overrides.title')}</h3>
                {PER_FEATURE_OVERRIDES.map(({ field, labelKey }) => {
                  const current = (form[field] as 'local' | 'cloud' | null | undefined) ?? null
                  const value = current === null || current === undefined ? 'inherit' : current
                  return (
                    <div key={field} className="space-y-1">
                      <label className="text-xs font-medium">{t(labelKey)}</label>
                      <select
                        value={value}
                        onChange={(e) => {
                          const v = e.target.value
                          const next = v === 'inherit' ? null : (v as 'local' | 'cloud')
                          updateField(field, next as SystemSettings[typeof field])
                        }}
                        className={inputClass}
                      >
                        <option value="inherit">{t('admin.pii.overrides.inherit')}</option>
                        <option value="local">{t('admin.pii.provider.local')}</option>
                        <option value="cloud">{t('admin.pii.provider.cloud')}</option>
                      </select>
                    </div>
                  )
                })}
              </div>
            </section>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button onClick={handleSave} disabled={!isDirty || saving} className="w-full max-w-xl">
            <Save className="mr-2 h-4 w-4" />
            {saving ? t('admin.save.saving') : saved ? t('admin.save.saved') : t('admin.save.button')}
          </Button>
        </div>
      </div>
    </div>
  )
}
