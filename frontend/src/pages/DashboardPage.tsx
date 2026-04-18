import { useState, useEffect, useCallback } from 'react'
import { LayoutDashboard, Folder, ClipboardList, FileCheck, ShieldCheck, BookOpen, Loader2 } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { apiFetch } from '@/lib/api'

interface DashboardSummary {
  documents_total: number
  documents_completed: number
  obligations_active: number
  obligations_overdue: number
  approvals_pending: number
  compliance_pass: number
  compliance_review: number
  compliance_fail: number
  regulatory_updates: number
  regulatory_unread: number
}

interface ObligationTimeline {
  id: string
  party: string
  obligation_text: string
  deadline: string
  priority: string
}

interface ComplianceTrend {
  month: string
  pass: number
  review: number
  fail: number
}

const PRIORITY_STYLE: Record<string, string> = {
  critical: 'text-red-600 dark:text-red-400 bg-red-500/10',
  high: 'text-amber-600 dark:text-amber-400 bg-amber-500/10',
  medium: 'text-foreground bg-secondary',
  low: 'text-muted-foreground bg-secondary',
}

export function DashboardPage() {
  const { t } = useI18n()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [timeline, setTimeline] = useState<ObligationTimeline[]>([])
  const [trend, setTrend] = useState<ComplianceTrend[]>([])
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [summaryRes, timelineRes, trendRes] = await Promise.allSettled([
        apiFetch('/dashboard/summary'),
        apiFetch('/dashboard/obligation-timeline'),
        apiFetch('/dashboard/compliance-trend'),
      ])
      if (summaryRes.status === 'fulfilled') {
        const raw = await summaryRes.value.json()
        setSummary({
          documents_total: raw.documents?.total ?? 0,
          documents_completed: raw.documents?.completed ?? 0,
          obligations_active: raw.obligations?.active ?? 0,
          obligations_overdue: raw.obligations?.overdue ?? 0,
          approvals_pending: raw.approvals?.pending ?? 0,
          compliance_pass: raw.compliance?.pass ?? 0,
          compliance_review: raw.compliance?.review ?? 0,
          compliance_fail: raw.compliance?.fail ?? 0,
          regulatory_updates: raw.regulatory?.updates ?? 0,
          regulatory_unread: raw.regulatory?.unread_alerts ?? 0,
        })
      }
      if (timelineRes.status === 'fulfilled') {
        const data = await timelineRes.value.json()
        setTimeline(data.data || [])
      }
      if (trendRes.status === 'fulfilled') {
        const data = await trendRes.value.json()
        setTrend(data.data || [])
      }
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  function formatDeadline(iso: string): string {
    const d = new Date(iso)
    const now = new Date()
    const diff = Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
    const dateStr = d.toLocaleDateString('id-ID', { year: 'numeric', month: 'short', day: 'numeric' })
    if (diff < 0) return `${dateStr} (${Math.abs(diff)}d overdue)`
    if (diff === 0) return `${dateStr} (today)`
    if (diff <= 7) return `${dateStr} (${diff}d left)`
    return dateStr
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const cards = [
    {
      label: 'Documents',
      value: summary?.documents_total ?? 0,
      sub: `${summary?.documents_completed ?? 0} completed`,
      icon: Folder,
      accent: 'text-cyan-600 dark:text-cyan-400',
      accentBg: 'bg-cyan-500/15 border-cyan-500/40',
    },
    {
      label: 'Obligations',
      value: summary?.obligations_active ?? 0,
      sub: `${summary?.obligations_overdue ?? 0} overdue`,
      icon: ClipboardList,
      accent: 'text-amber-600 dark:text-amber-400',
      accentBg: 'bg-amber-500/15 border-amber-500/40',
    },
    {
      label: 'Approvals',
      value: summary?.approvals_pending ?? 0,
      sub: 'pending',
      icon: FileCheck,
      accent: 'text-purple-600 dark:text-purple-400',
      accentBg: 'bg-purple-500/15 border-purple-500/40',
    },
    {
      label: 'Compliance',
      value: summary?.compliance_pass ?? 0,
      sub: `${summary?.compliance_review ?? 0} review / ${summary?.compliance_fail ?? 0} fail`,
      icon: ShieldCheck,
      accent: 'text-green-600 dark:text-green-400',
      accentBg: 'bg-green-500/15 border-green-500/40',
    },
    {
      label: 'Regulatory',
      value: summary?.regulatory_updates ?? 0,
      sub: `${summary?.regulatory_unread ?? 0} unread alerts`,
      icon: BookOpen,
      accent: 'text-red-600 dark:text-red-400',
      accentBg: 'bg-red-500/15 border-red-500/40',
    },
  ]

  // Find max for compliance trend bars
  const trendMax = Math.max(1, ...trend.map(t => t.pass + t.review + t.fail))

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-[1200px] mx-auto space-y-6">
        {/* Header */}
        <header>
          <h1 className="text-lg font-semibold flex items-center gap-2">
            <LayoutDashboard className="h-5 w-5 text-primary" />
            {t('nav.dashboard') || 'Dashboard'}
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">Overview of your legal workspace</p>
        </header>

        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {cards.map(card => {
            const Icon = card.icon
            return (
              <div key={card.label} className={`rounded-lg border p-4 ${card.accentBg}`} role="status" aria-label={`${card.label}: ${card.value} ${card.sub}`}>
                <div className="flex items-center gap-2 mb-2">
                  <Icon className={`h-4 w-4 ${card.accent}`} />
                  <span className="text-[10px] font-medium text-muted-foreground uppercase">{card.label}</span>
                </div>
                <p className={`text-2xl font-bold ${card.accent}`}>{card.value}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{card.sub}</p>
              </div>
            )
          })}
        </div>

        {/* Obligation timeline + Compliance trend */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Obligation timeline */}
          <div className="rounded-lg border border-border/50 p-4">
            <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <ClipboardList className="h-4 w-4 text-amber-600 dark:text-amber-400" />
              Upcoming Obligations
            </h2>
            {timeline.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <ClipboardList className="h-8 w-8 opacity-30 mb-2" />
                <p className="text-xs">No upcoming deadlines</p>
              </div>
            ) : (
              <div className="space-y-2">
                {timeline.map(ob => {
                  const priorityStyle = PRIORITY_STYLE[ob.priority] || PRIORITY_STYLE.medium
                  return (
                    <div key={ob.id} className="rounded-md border border-border/50 px-3 py-2.5">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-medium">{ob.party}</p>
                          <p className="text-[10px] text-muted-foreground line-clamp-2 mt-0.5">{ob.obligation_text}</p>
                        </div>
                        <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded shrink-0 ${priorityStyle}`}>
                          {ob.priority}
                        </span>
                      </div>
                      <p className="text-[9px] text-muted-foreground mt-1.5">{formatDeadline(ob.deadline)}</p>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Compliance trend */}
          <div className="rounded-lg border border-border/50 p-4">
            <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-green-600 dark:text-green-400" />
              Compliance Trend
            </h2>
            {trend.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                <ShieldCheck className="h-8 w-8 opacity-30 mb-2" />
                <p className="text-xs">No compliance data yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {trend.map(row => {
                  const total = row.pass + row.review + row.fail
                  return (
                    <div key={row.month}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] font-medium">{row.month}</span>
                        <span className="text-[9px] text-muted-foreground">{total} total</span>
                      </div>
                      <div className="flex h-4 rounded overflow-hidden bg-secondary">
                        {row.pass > 0 && (
                          <div
                            className="bg-green-500/60 transition-all"
                            style={{ width: `${(row.pass / trendMax) * 100}%` }}
                            title={`Pass: ${row.pass}`}
                          />
                        )}
                        {row.review > 0 && (
                          <div
                            className="bg-amber-500/60 transition-all"
                            style={{ width: `${(row.review / trendMax) * 100}%` }}
                            title={`Review: ${row.review}`}
                          />
                        )}
                        {row.fail > 0 && (
                          <div
                            className="bg-red-500/60 transition-all"
                            style={{ width: `${(row.fail / trendMax) * 100}%` }}
                            title={`Fail: ${row.fail}`}
                          />
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-[8px] text-green-600 dark:text-green-400">{row.pass} pass</span>
                        <span className="text-[8px] text-amber-600 dark:text-amber-400">{row.review} review</span>
                        <span className="text-[8px] text-red-600 dark:text-red-400">{row.fail} fail</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
