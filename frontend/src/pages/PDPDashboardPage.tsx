import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldAlert, Database, AlertTriangle, CheckCircle, Loader2, UserCheck } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'

interface Readiness {
  readiness_score: number
  status: {
    dpo_appointed: boolean
    dpo_name: string | null
    dpo_email: string | null
    breach_plan_exists: boolean
  }
  inventory_count: number
  dpia_required: number
  dpia_completed: number
  incident_count: number
}

export function PDPDashboardPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [readiness, setReadiness] = useState<Readiness | null>(null)
  const [loading, setLoading] = useState(true)
  const [appointing, setAppointing] = useState(false)
  const [dpoName, setDpoName] = useState('')
  const [dpoEmail, setDpoEmail] = useState('')
  const [showAppointForm, setShowAppointForm] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiFetch('/pdp/readiness')
      setReadiness(await res.json())
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleAppoint = async () => {
    if (!dpoName.trim() || !dpoEmail.trim()) return
    setAppointing(true)
    try {
      await apiFetch('/pdp/compliance-status', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dpo_appointed: true, dpo_name: dpoName.trim(), dpo_email: dpoEmail.trim() }),
      })
      setShowAppointForm(false)
      loadData()
    } catch {
      // error
    } finally {
      setAppointing(false)
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
  }

  const r = readiness

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        <div>
          <h1 className="text-xl font-extrabold tracking-tight">{t('pdp.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('pdp.subtitle')}</p>
        </div>

        {/* Readiness Score */}
        <div className="flex items-center gap-6 rounded-lg border border-border p-6">
          <div className="relative w-24 h-24 shrink-0">
            <svg className="w-24 h-24 -rotate-90" viewBox="0 0 36 36">
              <path className="text-secondary" strokeWidth="3" stroke="currentColor" fill="none" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
              <path className={r && r.readiness_score >= 70 ? 'text-green-500' : r && r.readiness_score >= 40 ? 'text-amber-500' : 'text-red-500'} strokeWidth="3" stroke="currentColor" fill="none" strokeDasharray={`${r?.readiness_score || 0}, 100`} d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center text-lg font-bold">{Math.round(r?.readiness_score || 0)}%</span>
          </div>
          <div>
            <h2 className="text-sm font-semibold">{t('pdp.readinessScore')}</h2>
            <p className="text-xs text-muted-foreground mt-1">{t('pdp.readinessDesc')}</p>
          </div>
        </div>

        {/* Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* DPO Status */}
          <div className={`rounded-lg border p-4 ${r?.status.dpo_appointed ? 'border-green-500/30 bg-green-500/5' : 'border-amber-500/30 bg-amber-500/5'}`}>
            <div className="flex items-center gap-2 mb-2">
              <UserCheck className={`h-5 w-5 ${r?.status.dpo_appointed ? 'text-green-500' : 'text-amber-500'}`} />
              <h3 className="text-sm font-semibold">{t('pdp.dpoStatus')}</h3>
            </div>
            {r?.status.dpo_appointed ? (
              <div className="text-xs space-y-1">
                <p className="text-green-600 dark:text-green-400 font-medium">{t('pdp.dpoAppointed')}</p>
                <p className="text-muted-foreground">{r.status.dpo_name} ({r.status.dpo_email})</p>
              </div>
            ) : (
              <div>
                <p className="text-xs text-amber-600 dark:text-amber-400 mb-2">{t('pdp.dpoNotAppointed')}</p>
                {!showAppointForm ? (
                  <Button size="sm" variant="outline" onClick={() => setShowAppointForm(true)}>{t('pdp.appointDpo')}</Button>
                ) : (
                  <div className="space-y-2">
                    <input type="text" value={dpoName} onChange={e => setDpoName(e.target.value)} placeholder={t('pdp.dpoName')} className="w-full rounded-lg border border-border bg-secondary px-3 py-1.5 text-xs text-foreground" />
                    <input type="email" value={dpoEmail} onChange={e => setDpoEmail(e.target.value)} placeholder={t('pdp.dpoEmail')} className="w-full rounded-lg border border-border bg-secondary px-3 py-1.5 text-xs text-foreground" />
                    <div className="flex gap-2">
                      <Button size="sm" onClick={handleAppoint} disabled={appointing}>{appointing ? <Loader2 className="h-3 w-3 animate-spin" /> : t('pdp.appoint')}</Button>
                      <Button size="sm" variant="outline" onClick={() => setShowAppointForm(false)}>{t('pdp.cancel')}</Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Breach Plan */}
          <div className={`rounded-lg border p-4 ${r?.status.breach_plan_exists ? 'border-green-500/30 bg-green-500/5' : 'border-amber-500/30 bg-amber-500/5'}`}>
            <div className="flex items-center gap-2 mb-2">
              <ShieldAlert className={`h-5 w-5 ${r?.status.breach_plan_exists ? 'text-green-500' : 'text-amber-500'}`} />
              <h3 className="text-sm font-semibold">{t('pdp.breachPlan')}</h3>
            </div>
            <p className={`text-xs ${r?.status.breach_plan_exists ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-400'}`}>
              {r?.status.breach_plan_exists ? t('pdp.breachPlanExists') : t('pdp.breachPlanMissing')}
            </p>
          </div>

          {/* Inventory */}
          <div className="rounded-lg border border-border p-4 cursor-pointer hover:bg-muted/30 transition-colors" onClick={() => navigate('/pdp/inventory')}>
            <div className="flex items-center gap-2 mb-2">
              <Database className="h-5 w-5 text-primary" />
              <h3 className="text-sm font-semibold">{t('pdp.dataInventory')}</h3>
            </div>
            <p className="text-2xl font-bold">{r?.inventory_count || 0}</p>
            <p className="text-xs text-muted-foreground">{t('pdp.processingActivities')}</p>
            {r && r.dpia_required > 0 && (
              <p className="text-xs text-muted-foreground mt-1">DPIA: {r.dpia_completed}/{r.dpia_required} {t('pdp.completed')}</p>
            )}
          </div>

          {/* Incidents */}
          <div className="rounded-lg border border-border p-4 cursor-pointer hover:bg-muted/30 transition-colors" onClick={() => navigate('/pdp/incidents')}>
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              <h3 className="text-sm font-semibold">{t('pdp.incidents')}</h3>
            </div>
            <p className="text-2xl font-bold">{r?.incident_count || 0}</p>
            <p className="text-xs text-muted-foreground">{t('pdp.totalIncidents')}</p>
          </div>
        </div>

        {/* Checklist */}
        <div className="rounded-lg border border-border p-4">
          <h3 className="text-sm font-semibold mb-3">{t('pdp.complianceChecklist')}</h3>
          <div className="space-y-2">
            {[
              { done: r?.status.dpo_appointed, label: t('pdp.checkDpo'), points: 20 },
              { done: r?.status.breach_plan_exists, label: t('pdp.checkBreachPlan'), points: 20 },
              { done: (r?.inventory_count || 0) > 0, label: t('pdp.checkInventory'), points: 30 },
              { done: r?.dpia_required === 0 || (r?.dpia_completed || 0) > 0, label: t('pdp.checkDpia'), points: 30 },
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                {item.done ? <CheckCircle className="h-4 w-4 text-green-500" /> : <div className="h-4 w-4 rounded-full border-2 border-muted-foreground" />}
                <span className={item.done ? 'text-foreground' : 'text-muted-foreground'}>{item.label}</span>
                <span className="text-muted-foreground ml-auto">{item.points} pts</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
