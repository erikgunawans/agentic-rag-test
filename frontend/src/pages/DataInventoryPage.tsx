import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, Database, Loader2, Archive } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'

interface InventoryItem {
  id: string
  processing_activity: string
  data_categories: string[]
  lawful_basis: string
  purposes: string[]
  data_subjects: string[]
  retention_period: string | null
  dpia_required: boolean
  dpia_status: string
  status: string
  created_at: string
}

const BASIS_LABELS: Record<string, string> = {
  consent: 'Consent',
  contract: 'Contract',
  legal_obligation: 'Legal Obligation',
  vital_interest: 'Vital Interest',
  public_task: 'Public Task',
  legitimate_interest: 'Legitimate Interest',
}

const DPIA_STYLE: Record<string, string> = {
  not_started: 'text-muted-foreground',
  in_progress: 'text-amber-500',
  completed: 'text-green-500',
}

export function DataInventoryPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [items, setItems] = useState<InventoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ processing_activity: '', data_categories: '', lawful_basis: 'contract', purposes: '', data_subjects: '' })

  const loadItems = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiFetch('/pdp/inventory')
      setItems((await res.json()).data || [])
    } catch { /* silent */ } finally { setLoading(false) }
  }, [])

  useEffect(() => { loadItems() }, [loadItems])

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => { if (e.key === 'Escape') setShowCreate(false) }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [])

  const handleCreate = async () => {
    if (!form.processing_activity.trim()) return
    setCreating(true)
    try {
      await apiFetch('/pdp/inventory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          processing_activity: form.processing_activity.trim(),
          data_categories: form.data_categories.split(',').map(s => s.trim()).filter(Boolean),
          lawful_basis: form.lawful_basis,
          purposes: form.purposes.split(',').map(s => s.trim()).filter(Boolean),
          data_subjects: form.data_subjects.split(',').map(s => s.trim()).filter(Boolean),
        }),
      })
      setShowCreate(false)
      setForm({ processing_activity: '', data_categories: '', lawful_basis: 'contract', purposes: '', data_subjects: '' })
      loadItems()
    } catch { /* error */ } finally { setCreating(false) }
  }

  const handleArchive = async (id: string) => {
    try {
      await apiFetch(`/pdp/inventory/${id}`, { method: 'DELETE' })
      loadItems()
    } catch { /* silent */ }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        <div>
          <button onClick={() => navigate('/pdp')} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mb-3">
            <ArrowLeft className="h-3.5 w-3.5" /> {t('pdp.backToDashboard')}
          </button>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-extrabold tracking-tight">{t('pdp.inventoryTitle')}</h1>
              <p className="text-sm text-muted-foreground">{t('pdp.inventorySubtitle')}</p>
            </div>
            <Button size="sm" onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4 mr-2" /> {t('pdp.addActivity')}
            </Button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <Database className="h-12 w-12 mb-3 opacity-30" />
            <p className="text-sm">{t('pdp.noInventory')}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map(item => (
              <div key={item.id} className="rounded-lg border border-border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-medium">{item.processing_activity}</h3>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {item.data_categories.map(cat => (
                        <span key={cat} className="text-[10px] bg-primary/10 text-primary px-1.5 py-0.5 rounded">{cat}</span>
                      ))}
                    </div>
                    <div className="flex items-center gap-3 mt-2 text-[10px] text-muted-foreground">
                      <span className="bg-secondary px-1.5 py-0.5 rounded">{BASIS_LABELS[item.lawful_basis] || item.lawful_basis}</span>
                      {item.retention_period && <span>{t('pdp.retention')}: {item.retention_period}</span>}
                      {item.dpia_required && (
                        <span className={DPIA_STYLE[item.dpia_status]}>DPIA: {item.dpia_status}</span>
                      )}
                      <span>{new Date(item.created_at).toLocaleDateString('id-ID')}</span>
                    </div>
                  </div>
                  <button onClick={() => handleArchive(item.id)} className="text-muted-foreground hover:text-red-500 p-1">
                    <Archive className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowCreate(false)}>
          <div className="w-full max-w-lg rounded-xl border border-border bg-background p-6 shadow-lg" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold mb-4">{t('pdp.addActivity')}</h3>
            <div className="space-y-3">
              <input type="text" value={form.processing_activity} onChange={e => setForm(f => ({ ...f, processing_activity: e.target.value }))} placeholder={t('pdp.activityPlaceholder')} className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground" autoFocus />
              <input type="text" value={form.data_categories} onChange={e => setForm(f => ({ ...f, data_categories: e.target.value }))} placeholder={t('pdp.categoriesPlaceholder')} className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground" />
              <select value={form.lawful_basis} onChange={e => setForm(f => ({ ...f, lawful_basis: e.target.value }))} className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground">
                {Object.entries(BASIS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <input type="text" value={form.purposes} onChange={e => setForm(f => ({ ...f, purposes: e.target.value }))} placeholder={t('pdp.purposesPlaceholder')} className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground" />
              <input type="text" value={form.data_subjects} onChange={e => setForm(f => ({ ...f, data_subjects: e.target.value }))} placeholder={t('pdp.subjectsPlaceholder')} className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground" />
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>{t('pdp.cancel')}</Button>
              <Button size="sm" onClick={handleCreate} disabled={creating || !form.processing_activity.trim()}>
                {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : t('pdp.create')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
