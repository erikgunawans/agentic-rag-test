import { useCallback, useEffect, useState } from 'react'
import { Clock, CheckCircle, AlertTriangle, XCircle, Loader2, ArrowLeftRight } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'

interface Snapshot {
  id: string
  document_id: string | null
  trigger_type: string
  framework: string
  scopes: string[]
  snapshot_date: string
  overall_status: string
  result: {
    summary: string
    findings: Array<{ category: string; status: string; description: string }>
    missing_provisions: string[]
    confidence_score: number
  }
  confidence_score: number | null
  regulatory_context: string | null
  created_at: string
}

interface DiffResult {
  snapshot_a: { id: string; date: string; status: string; framework: string }
  snapshot_b: { id: string; date: string; status: string; framework: string }
  status_change: boolean
  status_a: string
  status_b: string
  added_findings: Array<{ category: string; status: string; description: string }>
  removed_findings: Array<{ category: string; status: string; description: string }>
  new_missing_provisions: string[]
  resolved_missing_provisions: string[]
}

const STATUS_STYLE: Record<string, { color: string; bg: string; icon: typeof CheckCircle }> = {
  pass: { color: 'text-green-600 dark:text-green-400', bg: 'bg-green-500/10 border-green-500/30', icon: CheckCircle },
  review: { color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30', icon: AlertTriangle },
  fail: { color: 'text-red-600 dark:text-red-400', bg: 'bg-red-500/10 border-red-500/30', icon: XCircle },
}

const FRAMEWORK_LABELS: Record<string, string> = {
  ojk: 'OJK',
  gdpr: 'GDPR',
  international: 'International',
  custom: 'Custom',
}

export function ComplianceTimelinePage() {
  const { t } = useI18n()
  const [snapshots, setSnapshots] = useState<Snapshot[]>([])
  const [loading, setLoading] = useState(true)
  const [frameworkFilter, setFrameworkFilter] = useState('')
  const [selectedA, setSelectedA] = useState<string | null>(null)
  const [selectedB, setSelectedB] = useState<string | null>(null)
  const [diff, setDiff] = useState<DiffResult | null>(null)
  const [diffLoading, setDiffLoading] = useState(false)
  const [detail, setDetail] = useState<Snapshot | null>(null)

  const loadSnapshots = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (frameworkFilter) params.set('framework', frameworkFilter)
      params.set('limit', '50')
      const res = await apiFetch(`/compliance/snapshots?${params}`)
      const data = await res.json()
      setSnapshots(data.data || [])
    } catch {
      // silent
    } finally {
      setLoading(false)
    }
  }, [frameworkFilter])

  useEffect(() => { loadSnapshots() }, [loadSnapshots])

  const handleCompare = async () => {
    if (!selectedA || !selectedB) return
    setDiffLoading(true)
    setDiff(null)
    try {
      const res = await apiFetch(`/compliance/snapshots/diff?a=${selectedA}&b=${selectedB}`)
      setDiff(await res.json())
    } catch {
      // silent
    } finally {
      setDiffLoading(false)
    }
  }

  const frameworks = ['', 'ojk', 'gdpr', 'international', 'custom']

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <div className="w-[340px] shrink-0 border-r border-border bg-sidebar overflow-y-auto p-4 space-y-4 hidden lg:block">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
            {t('complianceTimeline.filterFramework')}
          </p>
          <div className="space-y-1">
            {frameworks.map(f => (
              <button
                key={f}
                onClick={() => setFrameworkFilter(f)}
                className={`w-full text-left rounded-md px-3 py-1.5 text-xs transition-colors ${
                  frameworkFilter === f ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                }`}
              >
                {f ? FRAMEWORK_LABELS[f] : t('complianceTimeline.allFrameworks')}
              </button>
            ))}
          </div>
        </div>

        {/* Compare Section */}
        {selectedA && selectedB && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
              {t('complianceTimeline.compare')}
            </p>
            <Button size="sm" className="w-full" onClick={handleCompare} disabled={diffLoading}>
              {diffLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <ArrowLeftRight className="h-4 w-4 mr-2" />}
              {t('complianceTimeline.compareSelected')}
            </Button>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          <div>
            <h1 className="text-xl font-extrabold tracking-tight">{t('complianceTimeline.title')}</h1>
            <p className="text-sm text-muted-foreground">{t('complianceTimeline.subtitle')}</p>
          </div>

          {/* Diff Result */}
          {diff && (
            <div className="rounded-lg border border-border p-4 space-y-3">
              <h3 className="text-sm font-semibold">{t('complianceTimeline.diffResult')}</h3>
              <div className="flex items-center gap-3 text-xs">
                <span className={STATUS_STYLE[diff.status_a]?.color}>{diff.status_a.toUpperCase()}</span>
                <span className="text-muted-foreground">→</span>
                <span className={STATUS_STYLE[diff.status_b]?.color}>{diff.status_b.toUpperCase()}</span>
                {diff.status_change && (
                  <span className="text-amber-500 font-medium">{t('complianceTimeline.statusChanged')}</span>
                )}
              </div>
              {diff.added_findings.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-red-500 mb-1">{t('complianceTimeline.newFindings')} ({diff.added_findings.length})</p>
                  {diff.added_findings.map((f, i) => (
                    <p key={i} className="text-xs text-muted-foreground ml-3">+ {f.category}: {f.description}</p>
                  ))}
                </div>
              )}
              {diff.removed_findings.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-green-500 mb-1">{t('complianceTimeline.resolvedFindings')} ({diff.removed_findings.length})</p>
                  {diff.removed_findings.map((f, i) => (
                    <p key={i} className="text-xs text-muted-foreground ml-3">- {f.category}: {f.description}</p>
                  ))}
                </div>
              )}
              {diff.new_missing_provisions.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-red-500 mb-1">{t('complianceTimeline.newMissing')} ({diff.new_missing_provisions.length})</p>
                  {diff.new_missing_provisions.map((p, i) => (
                    <p key={i} className="text-xs text-muted-foreground ml-3">+ {p}</p>
                  ))}
                </div>
              )}
              {diff.resolved_missing_provisions.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-green-500 mb-1">{t('complianceTimeline.resolvedMissing')} ({diff.resolved_missing_provisions.length})</p>
                  {diff.resolved_missing_provisions.map((p, i) => (
                    <p key={i} className="text-xs text-muted-foreground ml-3">- {p}</p>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Timeline */}
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : snapshots.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Clock className="h-12 w-12 mb-3 opacity-30" />
              <p className="text-sm">{t('complianceTimeline.noSnapshots')}</p>
            </div>
          ) : (
            <div className="space-y-0">
              {snapshots.map((snap, idx) => {
                const style = STATUS_STYLE[snap.overall_status] || STATUS_STYLE.review
                const StatusIcon = style.icon
                const isSelectedA = selectedA === snap.id
                const isSelectedB = selectedB === snap.id

                return (
                  <div key={snap.id} className="flex gap-4">
                    {/* Timeline line */}
                    <div className="flex flex-col items-center">
                      <div className={`w-3 h-3 rounded-full border-2 ${style.bg} ${style.color}`} />
                      {idx < snapshots.length - 1 && <div className="w-px flex-1 bg-border" />}
                    </div>

                    {/* Card */}
                    <div
                      className={`flex-1 rounded-lg border p-3 mb-3 transition-colors cursor-pointer ${
                        isSelectedA || isSelectedB
                          ? 'border-primary/50 bg-primary/5'
                          : 'border-border hover:bg-muted/30'
                      }`}
                      onClick={() => setDetail(detail?.id === snap.id ? null : snap)}
                    >
                      <div className="flex items-center gap-2">
                        <StatusIcon className={`h-4 w-4 ${style.color}`} />
                        <span className={`text-xs font-semibold uppercase ${style.color}`}>
                          {snap.overall_status}
                        </span>
                        <span className="text-[10px] bg-secondary px-1.5 py-0.5 rounded font-medium">
                          {FRAMEWORK_LABELS[snap.framework]}
                        </span>
                        <span className="text-[10px] text-muted-foreground">
                          {snap.trigger_type}
                        </span>
                        <span className="flex-1" />
                        <span className="text-[10px] text-muted-foreground">
                          {new Date(snap.snapshot_date).toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      {snap.regulatory_context && (
                        <p className="mt-1 text-xs text-muted-foreground">{snap.regulatory_context}</p>
                      )}
                      <div className="mt-2 flex items-center gap-2 text-[10px] text-muted-foreground">
                        <span>{snap.result.findings?.length || 0} findings</span>
                        <span>{snap.result.missing_provisions?.length || 0} missing</span>
                        {snap.confidence_score != null && (
                          <span>{Math.round(snap.confidence_score * 100)}% confidence</span>
                        )}
                        <span className="flex-1" />
                        <button
                          onClick={(e) => { e.stopPropagation(); setSelectedA(isSelectedA ? null : snap.id) }}
                          className={`px-2 py-0.5 rounded ${isSelectedA ? 'bg-primary text-primary-foreground' : 'bg-secondary hover:bg-muted'}`}
                        >
                          A
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setSelectedB(isSelectedB ? null : snap.id) }}
                          className={`px-2 py-0.5 rounded ${isSelectedB ? 'bg-primary text-primary-foreground' : 'bg-secondary hover:bg-muted'}`}
                        >
                          B
                        </button>
                      </div>

                      {/* Expanded detail */}
                      {detail?.id === snap.id && (
                        <div className="mt-3 pt-3 border-t border-border space-y-2">
                          <p className="text-xs">{snap.result.summary}</p>
                          {snap.result.findings?.map((f, i) => (
                            <div key={i} className="text-xs text-muted-foreground">
                              <span className="font-medium">{f.category}</span>: {f.description}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
