import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Lock, Save } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { LLM_MODELS, EMBEDDING_MODELS } from '@/lib/models'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'

interface UserSettings {
  llm_model: string
  embedding_model: string
  embedding_locked: boolean
}

export function SettingsPage() {
  const navigate = useNavigate()
  const [settings, setSettings] = useState<UserSettings | null>(null)
  const [llmModel, setLlmModel] = useState('')
  const [embeddingModel, setEmbeddingModel] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSettings = useCallback(async () => {
    const res = await apiFetch('/settings')
    const data: UserSettings = await res.json()
    setSettings(data)
    setLlmModel(data.llm_model)
    setEmbeddingModel(data.embedding_model)
  }, [])

  useEffect(() => {
    loadSettings()
  }, [loadSettings])

  async function handleSave() {
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      await apiFetch('/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          llm_model: llmModel,
          embedding_model: embeddingModel,
        }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
      await loadSettings()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const isDirty =
    settings !== null &&
    (llmModel !== settings.llm_model || embeddingModel !== settings.embedding_model)

  return (
    <div className="flex h-screen flex-col bg-background">
      <div className="flex items-center gap-3 border-b px-6 py-4">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)} aria-label="Back">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-sm font-semibold">Settings</h1>
      </div>

      <Separator />

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl space-y-8">

          {/* LLM Model */}
          <section className="space-y-3">
            <div>
              <h2 className="text-sm font-semibold">LLM Model</h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                The model used to generate chat responses via OpenRouter.
              </p>
            </div>
            <div className="space-y-2">
              {LLM_MODELS.map((m) => (
                <label
                  key={m.value}
                  className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                    llmModel === m.value ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                  }`}
                >
                  <input
                    type="radio"
                    name="llm_model"
                    value={m.value}
                    checked={llmModel === m.value}
                    onChange={() => setLlmModel(m.value)}
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
              <h2 className="text-sm font-semibold flex items-center gap-2">
                Embedding Model
                {settings?.embedding_locked && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                    <Lock className="h-3 w-3" />
                    Locked
                  </span>
                )}
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Used to embed documents and queries for similarity search.{' '}
                {settings?.embedding_locked ? (
                  <span className="text-amber-700 font-medium">
                    Delete all documents to switch models — mixing models corrupts similarity search.
                  </span>
                ) : (
                  'Only 1536-dimension models are supported.'
                )}
              </p>
            </div>
            <div className="space-y-2">
              {EMBEDDING_MODELS.map((m) => (
                <label
                  key={m.value}
                  className={`flex items-start gap-3 rounded-lg border p-3 transition-colors ${
                    settings?.embedding_locked
                      ? 'opacity-60 cursor-not-allowed'
                      : 'cursor-pointer hover:bg-muted/50'
                  } ${embeddingModel === m.value ? 'border-primary bg-primary/5' : ''}`}
                >
                  <input
                    type="radio"
                    name="embedding_model"
                    value={m.value}
                    checked={embeddingModel === m.value}
                    onChange={() => !settings?.embedding_locked && setEmbeddingModel(m.value)}
                    disabled={settings?.embedding_locked}
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

          {/* Save */}
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}

          <Button onClick={handleSave} disabled={!isDirty || saving} className="w-full">
            <Save className="mr-2 h-4 w-4" />
            {saving ? 'Saving…' : saved ? 'Saved!' : 'Save Settings'}
          </Button>

        </div>
      </div>
    </div>
  )
}
