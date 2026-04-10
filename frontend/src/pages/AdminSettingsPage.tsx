import { useCallback, useEffect, useState } from 'react'
import { Save, Shield } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { LLM_MODELS, EMBEDDING_MODELS } from '@/lib/models'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { ColumnHeader } from '@/components/shared/ColumnHeader'
import { useSidebar } from '@/layouts/SidebarContext'

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

function AdminSidebar() {
  return (
    <div className="flex flex-col h-full">
      <ColumnHeader title="Admin" subtitle="Configuration" rightIcon="none" />
    </div>
  )
}

export function AdminSettingsPage() {
  const { setSidebar, clearSidebar } = useSidebar()
  const [settings, setSettings] = useState<SystemSettings | null>(null)
  const [form, setForm] = useState<Partial<SystemSettings>>({})
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSettings = useCallback(async () => {
    const res = await apiFetch('/admin/settings')
    if (!res.ok) {
      setError('Failed to load settings. Are you an admin?')
      return
    }
    const data: SystemSettings = await res.json()
    setSettings(data)
    setForm(data)
  }, [])

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
      if (!res.ok) throw new Error('Save failed')
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      await loadSettings()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    setSidebar(<AdminSidebar />, 260)
    return () => clearSidebar()
  }, [setSidebar, clearSidebar])

  const isDirty = settings !== null && JSON.stringify(form) !== JSON.stringify(settings)

  function updateField<K extends keyof SystemSettings>(key: K, value: SystemSettings[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="flex items-center gap-3 mb-6">
        <Shield className="h-4 w-4 text-amber-600" />
        <h1 className="text-sm font-semibold">Global Configuration</h1>
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
          Admin Only
        </span>
      </div>
        <div className="mx-auto max-w-2xl space-y-8">

          {/* LLM Model */}
          <section className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold">LLM Model</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                The model used for chat responses (via OpenRouter).
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

          {/* Embedding Model */}
          <section className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold">Embedding Model</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Used to embed documents and queries for similarity search.
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

          {/* RAG Tuning */}
          <section className="space-y-4">
            <div>
              <h2 className="text-sm font-semibold">RAG Configuration</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Controls retrieval-augmented generation behavior.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-medium">Top K Results</label>
                <input
                  type="number"
                  value={form.rag_top_k ?? 5}
                  onChange={(e) => updateField('rag_top_k', parseInt(e.target.value) || 5)}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  min={1}
                  max={20}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">Similarity Threshold</label>
                <input
                  type="number"
                  step="0.05"
                  value={form.rag_similarity_threshold ?? 0.3}
                  onChange={(e) => updateField('rag_similarity_threshold', parseFloat(e.target.value) || 0.3)}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  min={0}
                  max={1}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">Chunk Size</label>
                <input
                  type="number"
                  value={form.rag_chunk_size ?? 500}
                  onChange={(e) => updateField('rag_chunk_size', parseInt(e.target.value) || 500)}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  min={100}
                  max={4000}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">Chunk Overlap</label>
                <input
                  type="number"
                  value={form.rag_chunk_overlap ?? 50}
                  onChange={(e) => updateField('rag_chunk_overlap', parseInt(e.target.value) || 50)}
                  className="w-full rounded-md border px-3 py-2 text-sm"
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
                  <p className="text-sm font-medium">Hybrid Search</p>
                  <p className="text-xs text-muted-foreground">Combine vector + full-text search with RRF</p>
                </div>
              </label>
              {form.rag_hybrid_enabled && (
                <div className="space-y-1 pl-7">
                  <label className="text-xs font-medium">RRF K Constant</label>
                  <input
                    type="number"
                    value={form.rag_rrf_k ?? 60}
                    onChange={(e) => updateField('rag_rrf_k', parseInt(e.target.value) || 60)}
                    className="w-32 rounded-md border px-3 py-2 text-sm"
                    min={1}
                  />
                </div>
              )}
            </div>
          </section>

          <Separator />

          {/* Tool Calling */}
          <section className="space-y-4">
            <div>
              <h2 className="text-sm font-semibold">Tool Calling</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Controls web search, database queries, and document search tools.
              </p>
            </div>
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={form.tools_enabled ?? true}
                onChange={(e) => updateField('tools_enabled', e.target.checked)}
              />
              <div>
                <p className="text-sm font-medium">Enable Tools</p>
                <p className="text-xs text-muted-foreground">Allow the LLM to call tools during chat</p>
              </div>
            </label>
            {form.tools_enabled && (
              <div className="space-y-1 pl-7">
                <label className="text-xs font-medium">Max Tool Iterations</label>
                <input
                  type="number"
                  value={form.tools_max_iterations ?? 5}
                  onChange={(e) => updateField('tools_max_iterations', parseInt(e.target.value) || 5)}
                  className="w-32 rounded-md border px-3 py-2 text-sm"
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
                <p className="text-sm font-medium">Enable Sub-Agents</p>
                <p className="text-xs text-muted-foreground">Route queries to specialized agents via orchestrator</p>
              </div>
            </label>
          </section>

          {/* Error & Save */}
          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button onClick={handleSave} disabled={!isDirty || saving} className="w-full">
            <Save className="mr-2 h-4 w-4" />
            {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Configuration'}
          </Button>

        </div>
    </div>
  )
}
