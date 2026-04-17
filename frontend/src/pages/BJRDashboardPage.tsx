import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Scale, Plus, Loader2, CheckCircle, Clock, Shield } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { RiskCard } from '@/components/bjr/RiskCard'
import { useI18n } from '@/i18n/I18nContext'

interface Decision {
  id: string
  title: string
  description: string | null
  decision_type: string
  current_phase: string
  status: string
  risk_level: string | null
  bjr_score: number
  user_email: string
  created_at: string
}

interface Summary {
  total_decisions: number
  by_phase: Record<string, number>
  average_bjr_score: number
  risk_distribution: Record<string, number>
  open_risks: number
}

interface Risk {
  id: string
  risk_title: string
  description: string | null
  risk_level: string
  mitigation: string | null
  status: string
  owner_role: string | null
  is_global: boolean
}

const PHASE_STYLE: Record<string, { color: string; icon: typeof Clock }> = {
  pre_decision: { color: 'text-blue-600 dark:text-blue-400', icon: Clock },
  decision: { color: 'text-amber-600 dark:text-amber-400', icon: Scale },
  post_decision: { color: 'text-purple-600 dark:text-purple-400', icon: Shield },
  completed: { color: 'text-green-600 dark:text-green-400', icon: CheckCircle },
}

const TYPE_LABELS: Record<string, string> = {
  investment: 'Investasi',
  procurement: 'Pengadaan',
  partnership: 'Kemitraan',
  divestment: 'Divestasi',
  capex: 'Capex',
  policy: 'Kebijakan',
  other: 'Lainnya',
}

export function BJRDashboardPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [globalRisks, setGlobalRisks] = useState<Risk[]>([])
  const [loading, setLoading] = useState(true)
  const [phaseFilter, setPhaseFilter] = useState('')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [creating, setCreating] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newType, setNewType] = useState('other')
  const [newRisk, setNewRisk] = useState('medium')

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (phaseFilter) params.set('phase', phaseFilter)
      const [decisionsRes, summaryRes, risksRes] = await Promise.all([
        apiFetch(`/bjr/decisions?${params}`),
        apiFetch('/bjr/summary'),
        apiFetch('/bjr/risks?status=open'),
      ])
      const [decisionsData, summaryData, risksData] = await Promise.all([
        decisionsRes.json(),
        summaryRes.json(),
        risksRes.json(),
      ])
      setDecisions(decisionsData.data || [])
      setSummary(summaryData)
      setGlobalRisks((risksData.data || []).filter((r: Risk) => r.is_global))
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [phaseFilter])

  useEffect(() => { loadData() }, [loadData])

  const handleCreate = async () => {
    if (!newTitle.trim()) return
    setCreating(true)
    try {
      const res = await apiFetch('/bjr/decisions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newTitle.trim(),
          decision_type: newType,
          risk_level: newRisk,
        }),
      })
      const data = await res.json()
      navigate(`/bjr/decisions/${data.id}`)
    } catch {
      // error
    } finally {
      setCreating(false)
    }
  }

  const phases = ['', 'pre_decision', 'decision', 'post_decision', 'completed']

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-[340px] shrink-0 border-r border-border bg-sidebar overflow-y-auto p-4 space-y-4 hidden lg:block">
        <Button className="w-full" onClick={() => setShowCreateForm(true)}>
          <Plus className="h-4 w-4 mr-2" />
          {t('bjr.newDecision')}
        </Button>

        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            {t('bjr.filterPhase')}
          </p>
          <div className="space-y-1">
            {phases.map(p => (
              <button
                key={p}
                onClick={() => setPhaseFilter(p)}
                className={`w-full text-left rounded-md px-3 py-1.5 text-xs transition-colors ${
                  phaseFilter === p ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                }`}
              >
                {p ? t(`bjr.phase.${p}`) : t('bjr.allPhases')}
                {summary && p && (
                  <span className="float-right text-muted-foreground">{summary.by_phase[p] || 0}</span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Standing Risks */}
        {globalRisks.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
              {t('bjr.standingRisks')}
            </p>
            <div className="space-y-2">
              {globalRisks.map(r => <RiskCard key={r.id} risk={r} />)}
            </div>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-extrabold tracking-tight">{t('bjr.title')}</h1>
              <p className="text-sm text-muted-foreground">{t('bjr.subtitle')}</p>
            </div>
            <Button className="lg:hidden" onClick={() => setShowCreateForm(true)}>
              <Plus className="h-4 w-4 mr-2" />
              {t('bjr.newDecision')}
            </Button>
          </div>

          {/* Summary Cards */}
          {summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="rounded-lg border border-border p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{t('bjr.totalDecisions')}</p>
                <p className="text-2xl font-bold">{summary.total_decisions}</p>
              </div>
              <div className="rounded-lg border border-border p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{t('bjr.avgScore')}</p>
                <p className="text-2xl font-bold">{summary.average_bjr_score}%</p>
              </div>
              <div className="rounded-lg border border-border p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{t('bjr.completed')}</p>
                <p className="text-2xl font-bold text-green-600 dark:text-green-400">{summary.by_phase.completed || 0}</p>
              </div>
              <div className="rounded-lg border border-border p-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{t('bjr.openRisks')}</p>
                <p className="text-2xl font-bold text-amber-600 dark:text-amber-400">{summary.open_risks}</p>
              </div>
            </div>
          )}

          {/* Decision List */}
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : decisions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Scale className="h-12 w-12 mb-3 opacity-30" />
              <p className="text-sm">{t('bjr.noDecisions')}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {decisions.map(d => {
                const PhaseInfo = PHASE_STYLE[d.current_phase] || PHASE_STYLE.pre_decision
                const PhaseIcon = PhaseInfo.icon
                return (
                  <button
                    key={d.id}
                    onClick={() => navigate(`/bjr/decisions/${d.id}`)}
                    className="w-full text-left rounded-lg border border-border p-4 hover:bg-muted/30 transition-colors"
                  >
                    <div className="flex items-start gap-3">
                      <PhaseIcon className={`h-5 w-5 mt-0.5 shrink-0 ${PhaseInfo.color}`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium truncate">{d.title}</span>
                          <span className="text-[10px] font-medium text-muted-foreground bg-secondary px-1.5 py-0.5 rounded">
                            {TYPE_LABELS[d.decision_type] || d.decision_type}
                          </span>
                          {d.risk_level && (
                            <span className={`text-[10px] font-semibold uppercase ${
                              d.risk_level === 'high' || d.risk_level === 'critical' ? 'text-red-500' :
                              d.risk_level === 'medium' ? 'text-amber-500' : 'text-green-500'
                            }`}>
                              {d.risk_level}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                          <span className={PhaseInfo.color}>{t(`bjr.phase.${d.current_phase}`)}</span>
                          <span>{d.user_email}</span>
                          <span>{new Date(d.created_at).toLocaleDateString('id-ID')}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 rounded-full bg-secondary overflow-hidden">
                          <div
                            className="h-full rounded-full bg-primary transition-all"
                            style={{ width: `${d.bjr_score}%` }}
                          />
                        </div>
                        <span className="text-xs font-medium w-8 text-right">{Math.round(d.bjr_score)}%</span>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Create Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowCreateForm(false)}>
          <div className="w-full max-w-md rounded-xl border border-border bg-background p-6 shadow-lg" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold mb-4">{t('bjr.newDecision')}</h3>
            <div className="space-y-3">
              <input
                type="text"
                value={newTitle}
                onChange={e => setNewTitle(e.target.value)}
                placeholder={t('bjr.decisionTitle')}
                className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
                autoFocus
              />
              <select
                value={newType}
                onChange={e => setNewType(e.target.value)}
                className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground"
              >
                {Object.entries(TYPE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
              <select
                value={newRisk}
                onChange={e => setNewRisk(e.target.value)}
                className="w-full rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <Button variant="outline" size="sm" onClick={() => setShowCreateForm(false)}>{t('bjr.cancel')}</Button>
              <Button size="sm" onClick={handleCreate} disabled={creating || !newTitle.trim()}>
                {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : t('bjr.create')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
