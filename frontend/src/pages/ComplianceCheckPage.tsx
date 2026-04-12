import { useState } from 'react'
import { ShieldCheck, ChevronLeft, ChevronRight, Clock, CheckCircle, ShieldAlert, ShieldX, Loader2 } from 'lucide-react'
import { useToolHistory, formatTimeAgo } from '@/hooks/useToolHistory'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { DropZone } from '@/components/shared/DropZone'
import { EmptyState } from '@/components/shared/EmptyState'
import { apiFetch } from '@/lib/api'

type Framework = 'ojk' | 'international' | 'gdpr' | 'custom'
type Scope = 'legal' | 'risks' | 'missing' | 'regulatory'

interface ComplianceFinding {
  category: string
  status: string
  description: string
  recommendation: string
}

interface ComplianceResult {
  overall_status: string
  summary: string
  findings: ComplianceFinding[]
  missing_provisions: string[]
}

const inputClass = "w-full rounded-lg border border-border bg-secondary text-foreground px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"

const STATUS_ICON: Record<string, typeof CheckCircle> = { pass: CheckCircle, review: ShieldAlert, fail: ShieldX }
const STATUS_COLOR: Record<string, string> = { pass: 'text-green-400', review: 'text-amber-400', fail: 'text-red-400' }

const FINDING_STYLE: Record<string, { color: string; bg: string }> = {
  pass: { color: 'text-green-400', bg: 'border-green-500/30 bg-green-500/5' },
  review: { color: 'text-amber-400', bg: 'border-amber-500/30 bg-amber-500/5' },
  fail: { color: 'text-red-400', bg: 'border-red-500/30 bg-red-500/5' },
}

const OVERALL_STYLE: Record<string, { label: string; color: string; bg: string }> = {
  pass: { label: 'COMPLIANT', color: 'text-green-400', bg: 'bg-green-500/10 border-green-500/30' },
  review: { label: 'NEEDS REVIEW', color: 'text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30' },
  fail: { label: 'NON-COMPLIANT', color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30' },
}

export function ComplianceCheckPage() {
  const { t } = useI18n()
  const { history, reload: reloadHistory } = useToolHistory('compliance')
  const [panelCollapsed, setPanelCollapsed] = useState(false)
  const [framework, setFramework] = useState<Framework>('ojk')
  const [scopes, setScopes] = useState<Set<Scope>>(new Set(['legal']))
  const [file, setFile] = useState<File | null>(null)
  const [context, setContext] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ComplianceResult | null>(null)
  const [showErrors, setShowErrors] = useState(false)

  function toggleScope(scope: Scope) {
    setScopes((prev) => {
      const next = new Set(prev)
      if (next.has(scope)) next.delete(scope)
      else next.add(scope)
      return next
    })
  }

  async function handleRun() {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('document', file)
      formData.append('framework', framework)
      formData.append('scopes', Array.from(scopes).join(','))
      if (context.trim()) formData.append('context', context)

      const response = await apiFetch('/document-tools/compliance', {
        method: 'POST',
        body: formData,
      })
      const data = await response.json()
      setResult(data)
      reloadHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Compliance check failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full">
      {/* Column 2 -- Form (75%) + History (25%) */}
      {panelCollapsed ? (
        <div className="flex h-full w-[50px] shrink-0 flex-col items-center border-r border-border/50 py-4 gap-3">
          <button
            onClick={() => setPanelCollapsed(false)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            title={t('compliance.title')}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
        </div>
      ) : (
      <div className="flex w-[340px] shrink-0 flex-col border-r border-border/50">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
          <div>
            <h1 className="text-sm font-semibold">{t('compliance.title')}</h1>
            <p className="text-[10px] text-muted-foreground">Periksa kepatuhan regulasi</p>
          </div>
          <button onClick={() => setPanelCollapsed(true)} className="text-muted-foreground hover:text-foreground transition-colors focus-ring">
            <ChevronLeft className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 overflow-y-auto" style={{ flex: '3 1 0' }}>
          <div className="px-5 py-4 space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('compliance.document')} <span className="text-red-400">*</span></label>
              <div className={showErrors && !file ? 'rounded-lg border border-red-500/50' : ''}>
                <DropZone onFileSelect={setFile} />
              </div>
              {showErrors && !file && <p className="text-[10px] text-red-400">Please upload a document</p>}
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('compliance.framework')} <span className="text-red-400">*</span></label>
              <select value={framework} onChange={(e) => setFramework(e.target.value as Framework)} className={inputClass}>
                <option value="ojk">{t('compliance.framework.ojk')}</option>
                <option value="international">{t('compliance.framework.international')}</option>
                <option value="gdpr">{t('compliance.framework.gdpr')}</option>
                <option value="custom">{t('compliance.framework.custom')}</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('compliance.scope')}</label>
              <div className="flex flex-col gap-1.5">
                {(['legal', 'risks', 'missing', 'regulatory'] as const).map((scope) => (
                  <button
                    key={scope}
                    onClick={() => toggleScope(scope)}
                    className={`rounded-lg px-3 py-2 text-xs font-medium text-left transition-colors ${
                      scopes.has(scope) ? 'bg-primary/10 text-primary border border-primary/30' : 'bg-secondary text-muted-foreground hover:text-foreground border border-transparent'
                    }`}
                  >
                    {t(`compliance.scope.${scope}`)}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('compliance.context')}</label>
              <textarea className={`${inputClass} min-h-[80px] resize-none`} placeholder={t('compliance.context')} value={context} onChange={(e) => setContext(e.target.value)} />
            </div>

            <div onClick={() => { if (!file) setShowErrors(true) }}>
              <Button className="w-full text-xs" disabled={loading || !file} onClick={handleRun}>
                {loading ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <ShieldCheck className="mr-2 h-3.5 w-3.5" />}
                {loading ? 'Checking...' : t('compliance.run')}
              </Button>
            </div>

            {error && <p className="text-xs text-red-400">{error}</p>}
          </div>
        </div>

        <div className="min-h-0 flex flex-col border-t border-border/50" style={{ flex: '1 1 0' }}>
          <div className="flex items-center justify-between px-5 py-2.5 shrink-0">
            <div className="flex items-center gap-1.5">
              <Clock className="h-3 w-3 text-muted-foreground" />
              <span className="text-[10px] font-semibold text-muted-foreground">{t('compliance.history')}</span>
            </div>
            <span className="text-[10px] text-primary cursor-pointer hover:underline">View all &rarr;</span>
          </div>
          <div className="flex-1 overflow-y-auto min-h-0 px-3 pb-2 space-y-0.5">
            {history.length === 0 ? (
              <p className="text-[10px] text-muted-foreground px-2 py-3">No checks yet</p>
            ) : history.map((item) => {
              const status = (item.result as Record<string, string> | undefined)?.overall_status ?? 'pass'
              const StatusIcon = STATUS_ICON[status] ?? CheckCircle
              return (
                <div key={item.id} className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/50 transition-colors cursor-pointer">
                  <ShieldCheck className="h-4 w-4 shrink-0 text-[var(--feature-compliance)]" />
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-medium truncate">{item.title}</p>
                    <p className="text-[9px] text-muted-foreground">{(item.input_params as Record<string, string>).framework} &middot; {formatTimeAgo(item.created_at)}</p>
                  </div>
                  <StatusIcon className={`h-3.5 w-3.5 shrink-0 ${STATUS_COLOR[status] ?? 'text-green-400'}`} />
                </div>
              )
            })}
          </div>
        </div>
      </div>
      )}

      {/* Column 3 -- Results */}
      <div className="flex-1 flex flex-col overflow-y-auto">
        {result ? (
          <div className="p-8 space-y-6">
            {/* Overall status badge */}
            <div className="flex items-center gap-4">
              <h2 className="text-lg font-semibold">Compliance Report</h2>
              {(() => {
                const style = OVERALL_STYLE[result.overall_status] || OVERALL_STYLE.review
                return (
                  <span className={`rounded-full border px-3 py-1 text-[10px] font-bold ${style.bg} ${style.color}`}>
                    {style.label}
                  </span>
                )
              })()}
            </div>
            <p className="text-xs text-muted-foreground">{result.summary}</p>

            {/* Findings */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Findings ({result.findings.length})</h3>
              {result.findings.map((finding, i) => {
                const style = FINDING_STYLE[finding.status] || FINDING_STYLE.review
                const Icon = STATUS_ICON[finding.status as keyof typeof STATUS_ICON] || ShieldAlert
                return (
                  <div key={i} className={`rounded-lg border p-4 space-y-2 ${style.bg}`}>
                    <div className="flex items-center gap-2">
                      <Icon className={`h-3.5 w-3.5 ${style.color}`} />
                      <span className="text-xs font-semibold">{finding.category}</span>
                      <span className={`text-[10px] ml-auto uppercase font-bold ${style.color}`}>{finding.status}</span>
                    </div>
                    <p className="text-xs">{finding.description}</p>
                    <p className="text-xs text-muted-foreground"><span className="font-medium">Recommendation:</span> {finding.recommendation}</p>
                  </div>
                )
              })}
            </div>

            {/* Missing provisions */}
            {result.missing_provisions.length > 0 && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 space-y-2">
                <h3 className="text-sm font-semibold text-amber-400">Missing Provisions</h3>
                <ul className="list-disc list-inside space-y-1">
                  {result.missing_provisions.map((p, i) => (
                    <li key={i} className="text-xs">{p}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center">
            <EmptyState icon={ShieldCheck} title="Upload a document and run compliance check" subtitle="The compliance report will appear here" />
          </div>
        )}
      </div>
    </div>
  )
}
