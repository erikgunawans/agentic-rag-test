import { useCallback, useEffect, useState } from 'react'
import { Save, Shield } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { LLM_MODELS, EMBEDDING_MODELS } from '@/lib/models'
import { Button } from '@/components/ui/button'
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
}

export function AdminSettingsPage() {
  const { t } = useI18n()
  const [settings, setSettings] = useState<SystemSettings | null>(null)
  const [form, setForm] = useState<Partial<SystemSettings>>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-2xl space-y-8">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-amber-500" />
          <h1 className="text-lg font-semibold">{t('admin.title')}</h1>
          <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-400">
            {t('admin.badge')}
          </span>
        </div>

          <section className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold">{t('admin.llm.title')}</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {t('admin.llm.description')}
              </p>
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

          <Separator />

          <section className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold">{t('admin.embedding.title')}</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {t('admin.embedding.description')}
              </p>
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

          <Separator />

          <section className="space-y-4">
            <div>
              <h2 className="text-sm font-semibold">{t('admin.rag.title')}</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {t('admin.rag.description')}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-medium">{t('admin.rag.topK')}</label>
                <input
                  type="number"
                  value={form.rag_top_k ?? 5}
                  onChange={(e) => updateField('rag_top_k', parseInt(e.target.value) || 5)}
                  className="w-full rounded-md border bg-secondary text-foreground px-3 py-2 text-sm"
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
                  className="w-full rounded-md border bg-secondary text-foreground px-3 py-2 text-sm"
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
                  className="w-full rounded-md border bg-secondary text-foreground px-3 py-2 text-sm"
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
                  className="w-full rounded-md border bg-secondary text-foreground px-3 py-2 text-sm"
                  min={0}
                  max={500}
                />
              </div>
            </div>
            <div className="space-y-3">
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
            </div>
          </section>

          <Separator />

          <section className="space-y-4">
            <div>
              <h2 className="text-sm font-semibold">{t('admin.tools.title')}</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                {t('admin.tools.description')}
              </p>
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

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button onClick={handleSave} disabled={!isDirty || saving} className="w-full">
            <Save className="mr-2 h-4 w-4" />
            {saving ? t('admin.save.saving') : saved ? t('admin.save.saved') : t('admin.save.button')}
          </Button>

      </div>
    </div>
  )
}
