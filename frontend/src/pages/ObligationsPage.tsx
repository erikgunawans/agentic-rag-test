import { useCallback, useEffect, useState } from 'react'
import { ClipboardList, Plus, RefreshCw, CheckCircle, AlertTriangle, Clock, XCircle, Loader2 } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'

interface Obligation {
  id: string
  document_id: string | null
  analysis_id: string | null
  party: string
  obligation_text: string
  obligation_type: string
  deadline: string | null
  recurrence: string | null
  status: string
  priority: string
  reminder_days: number
  notes: string | null
  contract_title: string | null
  created_at: string
  updated_at: string
}

interface Summary {
  active: number
  completed: number
  overdue: number
  upcoming: number
  cancelled: number
  total: number
}

const STATUS_STYLE: Record<string, { color: string; bg: string; icon: typeof CheckCircle }> = {
  active: { color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/30', icon: Clock },
  upcoming: { color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30', icon: AlertTriangle },
  overdue: { color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30', icon: XCircle },
  completed: { color: 'text-green-400', bg: 'bg-green-500/10 border-green-500/30', icon: CheckCircle },
  cancelled: { color: 'text-muted-foreground', bg: 'bg-secondary border-border', icon: XCircle },
}

const PRIORITY_STYLE: Record<string, string> = {
  critical: 'text-red-400',
  high: 'text-amber-400',
  medium: 'text-foreground',
  low: 'text-muted-foreground',
}

export function ObligationsPage() {
  const { t } = useI18n()
  const [obligations, setObligations] = useState<Obligation[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [updatingId, setUpdatingId] = useState<string | null>(null)

  const loadObligations = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (statusFilter) params.set('status', statusFilter)
      const res = await apiFetch(`/obligations?${params}`)
      const data = await res.json()
      setObligations(data.data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('obligations.error.load'))
    } finally {
      setLoading(false)
    }
  }, [statusFilter, t])

  const loadSummary = useCallback(async () => {
    try {
      const res = await apiFetch('/obligations/summary')
      const data: Summary = await res.json()
      setSummary(data)
    } catch {
      // silent
    }
  }, [])

  useEffect(() => { loadObligations() }, [loadObligations])
  useEffect(() => { loadSummary() }, [loadSummary])

  async function handleCheckDeadlines() {
    try {
      await apiFetch('/obligations/check-deadlines', { method: 'POST' })
      await loadObligations()
      await loadSummary()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to check deadlines')
    }
  }

  async function handleStatusChange(id: string, newStatus: string) {
    setUpdatingId(id)
    try {
      await apiFetch(`/obligations/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
      })
      await loadObligations()
      await loadSummary()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to update')
    } finally {
      setUpdatingId(null)
    }
  }

  function formatDeadline(iso: string | null): string {
    if (!iso) return '\u2014'
    const d = new Date(iso)
    const now = new Date()
    const diff = Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
    const dateStr = d.toLocaleDateString('id-ID', { year: 'numeric', month: 'short', day: 'numeric' })
    if (diff < 0) return `${dateStr} (${Math.abs(diff)}d overdue)`
    if (diff === 0) return `${dateStr} (today)`
    if (diff <= 7) return `${dateStr} (${diff}d left)`
    return dateStr
  }

  const statuses = ['', 'active', 'upcoming', 'overdue', 'completed', 'cancelled']

  return (
    <div className="flex-1 flex flex-col overflow-y-auto">
      <div className="max-w-5xl w-full mx-auto p-8 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold flex items-center gap-2">
              <ClipboardList className="h-5 w-5 text-primary" />
              {t('obligations.title')}
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">{t('obligations.subtitle')}</p>
          </div>
          <Button variant="outline" size="sm" className="gap-1.5" onClick={handleCheckDeadlines}>
            <RefreshCw className="h-3.5 w-3.5" />
            {t('obligations.checkDeadlines')}
          </Button>
        </div>

        {/* Summary cards */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {(['active', 'upcoming', 'overdue', 'completed', 'cancelled'] as const).map((s) => {
              const style = STATUS_STYLE[s]
              const Icon = style.icon
              return (
                <button
                  key={s}
                  onClick={() => setStatusFilter(statusFilter === s ? '' : s)}
                  className={`rounded-lg border p-3 text-left transition-colors ${
                    statusFilter === s ? style.bg : 'border-border hover:bg-secondary/50'
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <Icon className={`h-3.5 w-3.5 ${style.color}`} />
                    <span className="text-[10px] font-medium text-muted-foreground uppercase">{t(`obligations.status.${s}`)}</span>
                  </div>
                  <p className={`text-xl font-bold mt-1 ${style.color}`}>{summary[s]}</p>
                </button>
              )
            })}
          </div>
        )}

        {/* Status filter tabs */}
        <div className="flex gap-2">
          {statuses.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                statusFilter === s
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-muted-foreground hover:text-foreground'
              }`}
            >
              {s ? t(`obligations.status.${s}`) : t('obligations.filter.all')}
            </button>
          ))}
        </div>

        {error && (
          <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {/* Table */}
        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : obligations.length === 0 ? (
          <div className="text-center py-12">
            <ClipboardList className="h-10 w-10 mx-auto text-muted-foreground/25 mb-3" strokeWidth={1.5} />
            <p className="text-sm text-muted-foreground">{t('obligations.empty')}</p>
            <p className="text-xs text-muted-foreground mt-1">{t('obligations.emptyHint')}</p>
          </div>
        ) : (
          <div className="rounded-lg border border-border overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-secondary/50">
                  <th className="text-left px-4 py-2.5 font-semibold">{t('obligations.col.status')}</th>
                  <th className="text-left px-4 py-2.5 font-semibold">{t('obligations.col.party')}</th>
                  <th className="text-left px-4 py-2.5 font-semibold">{t('obligations.col.obligation')}</th>
                  <th className="text-left px-4 py-2.5 font-semibold">{t('obligations.col.deadline')}</th>
                  <th className="text-left px-4 py-2.5 font-semibold">{t('obligations.col.priority')}</th>
                  <th className="text-left px-4 py-2.5 font-semibold">{t('obligations.col.contract')}</th>
                  <th className="text-left px-4 py-2.5 font-semibold">{t('obligations.col.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {obligations.map((ob) => {
                  const style = STATUS_STYLE[ob.status] || STATUS_STYLE.active
                  const Icon = style.icon
                  return (
                    <tr key={ob.id} className="border-t border-border/50 hover:bg-accent/30 transition-colors">
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold ${style.bg} ${style.color}`}>
                          <Icon className="h-3 w-3" />
                          {ob.status}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 font-medium">{ob.party}</td>
                      <td className="px-4 py-2.5 max-w-[300px]">
                        <p className="truncate">{ob.obligation_text}</p>
                        {ob.notes && <p className="text-[10px] text-muted-foreground truncate mt-0.5">{ob.notes}</p>}
                      </td>
                      <td className="px-4 py-2.5 whitespace-nowrap">
                        <span className={ob.status === 'overdue' ? 'text-red-400 font-medium' : ''}>
                          {formatDeadline(ob.deadline)}
                        </span>
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`text-[10px] font-bold uppercase ${PRIORITY_STYLE[ob.priority] || ''}`}>
                          {ob.priority}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground max-w-[150px] truncate">
                        {ob.contract_title || '\u2014'}
                      </td>
                      <td className="px-4 py-2.5">
                        {ob.status !== 'completed' && ob.status !== 'cancelled' && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-[10px] h-6 px-2"
                            disabled={updatingId === ob.id}
                            onClick={() => handleStatusChange(ob.id, 'completed')}
                          >
                            <CheckCircle className="h-3 w-3 mr-1" />
                            {t('obligations.markComplete')}
                          </Button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
