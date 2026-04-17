import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, AlertTriangle, Loader2, Clock, FileText } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'

interface Incident {
  id: string
  incident_date: string
  discovered_date: string
  incident_type: string
  description: string
  affected_data_categories: string[]
  estimated_records: number | null
  response_status: string
  regulator_notified_at: string | null
  subjects_notified_at: string | null
  created_at: string
}

const STATUS_STYLE: Record<string, { color: string; bg: string }> = {
  reported: { color: 'text-red-600 dark:text-red-400', bg: 'bg-red-500/10 border-red-500/30' },
  investigating: { color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30' },
  remediated: { color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-500/10 border-blue-500/30' },
  closed: { color: 'text-green-600 dark:text-green-400', bg: 'bg-green-500/10 border-green-500/30' },
}

const TYPE_LABELS: Record<string, string> = {
  unauthorized_access: 'Akses Tidak Sah',
  ransomware: 'Ransomware',
  accidental_disclosure: 'Pengungkapan Tidak Sengaja',
  data_loss: 'Kehilangan Data',
  insider_threat: 'Ancaman Internal',
}

function getDeadlineHours(discoveredDate: string): number {
  const discovered = new Date(discoveredDate).getTime()
  const deadline = discovered + 72 * 60 * 60 * 1000
  const now = Date.now()
  return Math.max(0, Math.round((deadline - now) / (60 * 60 * 1000)))
}

export function DataBreachPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ incident_type: 'unauthorized_access', description: '', affected_data_categories: '', estimated_records: '' })

  const loadIncidents = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiFetch('/pdp/incidents')
      setIncidents((await res.json()).data || [])
    } catch { /* silent */ } finally { setLoading(false) }
  }, [])

  useEffect(() => { loadIncidents() }, [loadIncidents])

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => { if (e.key === 'Escape') setShowCreate(false) }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [])

  const handleCreate = async () => {
    setCreating(true)
    try {
      await apiFetch('/pdp/incidents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          incident_date: new Date().toISOString(),
          incident_type: form.incident_type,
          description: form.description.trim(),
          affected_data_categories: form.affected_data_categories.split(',').map(s => s.trim()).filter(Boolean),
          estimated_records: form.estimated_records ? parseInt(form.estimated_records) : null,
        }),
      })
      setShowCreate(false)
      setForm({ incident_type: 'unauthorized_access', description: '', affected_data_categories: '', estimated_records: '' })
      loadIncidents()
    } catch { /* error */ } finally { setCreating(false) }
  }

  const handleGetTemplate = async (id: string) => {
    try {
      const res = await apiFetch(`/pdp/incidents/${id}/notification`)
      const data = await res.json()
      navigator.clipboard.writeText(data.template)
      alert(t('pdp.templateCopied'))
    } catch { /* error */ }
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
              <h1 className="text-xl font-extrabold tracking-tight">{t('pdp.incidentsTitle')}</h1>
              <p className="text-sm text-muted-foreground">{t('pdp.incidentsSubtitle')}</p>
            </div>
            <Button size="sm" onClick={() => setShowCreate(true)}>
              <Plus className="h-4 w-4 mr-2" /> {t('pdp.reportIncident')}
            </Button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
        ) : incidents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
            <AlertTriangle className="h-12 w-12 mb-3 opacity-30" />
            <p className="text-sm">{t('pdp.noIncidents')}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {incidents.map(inc => {
              const style = STATUS_STYLE[inc.response_status] || STATUS_STYLE.reported
              const hoursLeft = inc.response_status !== 'closed' && !inc.regulator_notified_at
                ? getDeadlineHours(inc.discovered_date)
                : null

              return (
                <div key={inc.id} className={`rounded-lg border p-4 ${style.bg}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-semibold uppercase ${style.color}`}>{inc.response_status}</span>
                        <span className="text-[10px] bg-secondary px-1.5 py-0.5 rounded">{TYPE_LABELS[inc.incident_type] || inc.incident_type}</span>
                        {hoursLeft !== null && (
                          <span className={`text-[10px] font-medium flex items-center gap-1 ${hoursLeft <= 24 ? 'text-red-500' : 'text-amber-500'}`}>
                            <Clock className="h-3 w-3" />
                            {hoursLeft}h {t('pdp.untilDeadline')}
                          </span>
                        )}
                      </div>
                      {inc.description && <p className="text-xs mt-1">{inc.description}</p>}
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {inc.affected_data_categories.map(cat => (
                          <span key={cat} className="text-[10px] bg-red-500/10 text-red-500 px-1.5 py-0.5 rounded">{cat}</span>
                        ))}
                      </div>
                      <div className="flex items-center gap-3 mt-2 text-[10px] text-muted-foreground">
                        <span>{t('pdp.incidentDate')}: {new Date(inc.incident_date).toLocaleDateString('id-ID')}</span>
                        {inc.estimated_records && <span>~{inc.estimated_records.toLocaleString()} {t('pdp.records')}</span>}
                        {inc.regulator_notified_at && <span className="text-green-500">{t('pdp.regulatorNotified')}</span>}
                      </div>
                    </div>
                    <Button size="sm" variant="outline" className="shrink-0" onClick={() => handleGetTemplate(inc.id)}>
                      <FileText className="h-3.5 w-3.5 mr-1" /> {t('pdp.notificationTemplate')}
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowCreate(false)}>
          <div className="w-full max-w-lg rounded-xl border border-border bg-background p-6 shadow-lg" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold mb-4">{t('pdp.reportIncident')}</h3>
            <div className="space-y-3">
              <select value={form.incident_type} onChange={e => setForm(f => ({ ...f, incident_type: e.target.value }))} className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground">
                {Object.entries(TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder={t('pdp.incidentDesc')} rows={3} className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground resize-none" />
              <input type="text" value={form.affected_data_categories} onChange={e => setForm(f => ({ ...f, affected_data_categories: e.target.value }))} placeholder={t('pdp.affectedCategories')} className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground" />
              <input type="number" value={form.estimated_records} onChange={e => setForm(f => ({ ...f, estimated_records: e.target.value }))} placeholder={t('pdp.estimatedRecords')} className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground" />
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>{t('pdp.cancel')}</Button>
              <Button size="sm" onClick={handleCreate} disabled={creating}>
                {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : t('pdp.report')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
