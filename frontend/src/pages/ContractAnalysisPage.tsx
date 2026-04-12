import { useState } from 'react'
import { Scale, ChevronLeft, ChevronRight, Clock, CheckCircle, AlertTriangle, XCircle, Loader2 } from 'lucide-react'
import { useToolHistory, formatTimeAgo } from '@/hooks/useToolHistory'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { DropZone } from '@/components/shared/DropZone'
import { EmptyState } from '@/components/shared/EmptyState'
import { apiFetch } from '@/lib/api'

type AnalysisType = 'risk' | 'obligations' | 'clauses' | 'missing'
type Law = 'indonesia' | 'singapore' | 'international' | 'custom'
type Depth = 'quick' | 'standard' | 'deep'

interface AnalysisRisk {
  clause: string
  risk_level: string
  description: string
  recommendation: string
}

interface AnalysisObligation {
  party: string
  obligation: string
  deadline: string | null
}

interface AnalysisResult {
  overall_risk: string
  summary: string
  risks: AnalysisRisk[]
  obligations: AnalysisObligation[]
  critical_clauses: string[]
  missing_provisions: string[]
}

const inputClass = "w-full rounded-lg border border-border bg-secondary text-foreground px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"

const STATUS_ICON: Record<string, typeof CheckCircle> = { low: CheckCircle, medium: AlertTriangle, high: XCircle }
const STATUS_COLOR: Record<string, string> = { low: 'text-green-400', medium: 'text-amber-400', high: 'text-red-400' }

const RISK_STYLE: Record<string, { color: string; bg: string; label: string }> = {
  high: { color: 'text-red-400', bg: 'border-red-500/30 bg-red-500/5', label: 'HIGH RISK' },
  medium: { color: 'text-amber-400', bg: 'border-amber-500/30 bg-amber-500/5', label: 'MEDIUM RISK' },
  low: { color: 'text-green-400', bg: 'border-green-500/30 bg-green-500/5', label: 'LOW RISK' },
}

export function ContractAnalysisPage() {
  const { t } = useI18n()
  const { history, reload: reloadHistory } = useToolHistory('analyze')
  const [panelCollapsed, setPanelCollapsed] = useState(false)
  const [types, setTypes] = useState<Set<AnalysisType>>(new Set(['risk']))
  const [law, setLaw] = useState<Law>('indonesia')
  const [depth, setDepth] = useState<Depth>('standard')
  const [file, setFile] = useState<File | null>(null)
  const [context, setContext] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [showErrors, setShowErrors] = useState(false)

  function toggleType(type: AnalysisType) {
    setTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
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
      formData.append('analysis_types', Array.from(types).join(','))
      formData.append('law', law)
      formData.append('depth', depth)
      if (context.trim()) formData.append('context', context)

      const response = await apiFetch('/document-tools/analyze', {
        method: 'POST',
        body: formData,
      })
      const data = await response.json()
      setResult(data)
      reloadHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
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
            title={t('analysis.title')}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <Scale className="h-4 w-4 text-muted-foreground" />
        </div>
      ) : (
      <div className="flex w-[340px] shrink-0 flex-col border-r border-border/50">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
          <div>
            <h1 className="text-sm font-semibold">{t('analysis.title')}</h1>
            <p className="text-[10px] text-muted-foreground">Identify risks and key clauses</p>
          </div>
          <button onClick={() => setPanelCollapsed(true)} className="text-muted-foreground hover:text-foreground transition-colors">
            <ChevronLeft className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 overflow-y-auto" style={{ flex: '3 1 0' }}>
          <div className="px-5 py-4 space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('analysis.document')} <span className="text-red-400">*</span></label>
              <div className={showErrors && !file ? 'rounded-lg border border-red-500/50' : ''}>
                <DropZone onFileSelect={setFile} />
              </div>
              {showErrors && !file && <p className="text-[10px] text-red-400">Please upload a document</p>}
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('analysis.type')}</label>
              <div className="flex flex-col gap-1.5">
                {(['risk', 'obligations', 'clauses', 'missing'] as const).map((type) => (
                  <button
                    key={type}
                    onClick={() => toggleType(type)}
                    className={`rounded-lg px-3 py-2 text-xs font-medium text-left transition-colors ${
                      types.has(type) ? 'bg-primary/10 text-primary border border-primary/30' : 'bg-secondary text-muted-foreground hover:text-foreground border border-transparent'
                    }`}
                  >
                    {t(`analysis.type.${type}`)}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('analysis.law')}</label>
              <select value={law} onChange={(e) => setLaw(e.target.value as Law)} className={inputClass}>
                <option value="indonesia">{t('analysis.law.indonesia')}</option>
                <option value="singapore">{t('analysis.law.singapore')}</option>
                <option value="international">{t('analysis.law.international')}</option>
                <option value="custom">{t('analysis.law.custom')}</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('analysis.depth')}</label>
              <div className="grid grid-cols-3 gap-1.5">
                {(['quick', 'standard', 'deep'] as const).map((d) => (
                  <button
                    key={d}
                    onClick={() => setDepth(d)}
                    className={`rounded-lg px-2 py-2 text-xs font-medium transition-colors ${
                      depth === d ? 'bg-primary text-primary-foreground' : 'bg-secondary text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {t(`analysis.depth.${d}`)}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('analysis.context')}</label>
              <textarea className={`${inputClass} min-h-[80px] resize-none`} placeholder={t('analysis.context')} value={context} onChange={(e) => setContext(e.target.value)} />
            </div>

            <div onClick={() => { if (!file) setShowErrors(true) }}>
              <Button className="w-full text-xs" disabled={loading || !file} onClick={handleRun}>
                {loading ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Scale className="mr-2 h-3.5 w-3.5" />}
                {loading ? 'Analyzing...' : t('analysis.run')}
              </Button>
            </div>

            {error && <p className="text-xs text-red-400">{error}</p>}
          </div>
        </div>

        <div className="min-h-0 flex flex-col border-t border-border/50" style={{ flex: '1 1 0' }}>
          <div className="flex items-center justify-between px-5 py-2.5 shrink-0">
            <div className="flex items-center gap-1.5">
              <Clock className="h-3 w-3 text-muted-foreground" />
              <span className="text-[10px] font-semibold text-muted-foreground">{t('analysis.history')}</span>
            </div>
            <span className="text-[10px] text-primary cursor-pointer hover:underline">View all &rarr;</span>
          </div>
          <div className="flex-1 overflow-y-auto min-h-0 px-3 pb-2 space-y-0.5">
            {history.length === 0 ? (
              <p className="text-[10px] text-muted-foreground px-2 py-3">No analyses yet</p>
            ) : history.map((item) => {
              const risk = (item.result as Record<string, string> | undefined)?.overall_risk ?? 'low'
              const StatusIcon = STATUS_ICON[risk] ?? CheckCircle
              const params = item.input_params as Record<string, string>
              return (
                <div key={item.id} className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/50 transition-colors cursor-pointer">
                  <Scale className="h-4 w-4 shrink-0 text-[var(--feature-analysis)]" />
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-medium truncate">{item.title}</p>
                    <p className="text-[9px] text-muted-foreground">{params.depth} &middot; {risk} risk &middot; {formatTimeAgo(item.created_at)}</p>
                  </div>
                  <StatusIcon className={`h-3.5 w-3.5 shrink-0 ${STATUS_COLOR[risk] ?? 'text-green-400'}`} />
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
            {/* Overall risk badge */}
            <div className="flex items-center gap-4">
              <h2 className="text-lg font-semibold">Contract Analysis</h2>
              {(() => {
                const style = RISK_STYLE[result.overall_risk] || RISK_STYLE.medium
                return (
                  <span className={`rounded-full border px-3 py-1 text-[10px] font-bold ${style.bg} ${style.color}`}>
                    {style.label}
                  </span>
                )
              })()}
            </div>
            <p className="text-xs text-muted-foreground">{result.summary}</p>

            {/* Risks */}
            {result.risks.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-semibold">Risks ({result.risks.length})</h3>
                {result.risks.map((risk, i) => {
                  const style = RISK_STYLE[risk.risk_level] || RISK_STYLE.medium
                  const Icon = STATUS_ICON[risk.risk_level as keyof typeof STATUS_ICON] || AlertTriangle
                  return (
                    <div key={i} className={`rounded-lg border p-4 space-y-2 ${style.bg}`}>
                      <div className="flex items-center gap-2">
                        <Icon className={`h-3.5 w-3.5 ${style.color}`} />
                        <span className="text-xs font-semibold">{risk.clause}</span>
                        <span className={`text-[10px] ml-auto uppercase font-bold ${style.color}`}>{risk.risk_level}</span>
                      </div>
                      <p className="text-xs">{risk.description}</p>
                      <p className="text-xs text-muted-foreground"><span className="font-medium">Recommendation:</span> {risk.recommendation}</p>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Obligations */}
            {result.obligations.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-semibold">Key Obligations ({result.obligations.length})</h3>
                <div className="rounded-lg border border-border overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-secondary/50">
                        <th className="text-left px-4 py-2 font-semibold">Party</th>
                        <th className="text-left px-4 py-2 font-semibold">Obligation</th>
                        <th className="text-left px-4 py-2 font-semibold">Deadline</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.obligations.map((ob, i) => (
                        <tr key={i} className="border-t border-border/50">
                          <td className="px-4 py-2 font-medium">{ob.party}</td>
                          <td className="px-4 py-2">{ob.obligation}</td>
                          <td className="px-4 py-2 text-muted-foreground">{ob.deadline || 'N/A'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Critical clauses */}
            {result.critical_clauses.length > 0 && (
              <div className="rounded-lg border border-border bg-secondary/30 p-4 space-y-2">
                <h3 className="text-sm font-semibold">Critical Clauses</h3>
                <ul className="list-disc list-inside space-y-1">
                  {result.critical_clauses.map((c, i) => (
                    <li key={i} className="text-xs">{c}</li>
                  ))}
                </ul>
              </div>
            )}

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
            <EmptyState icon={Scale} title="Upload a contract and run analysis" subtitle="The risk assessment will appear here" />
          </div>
        )}
      </div>
    </div>
  )
}
