import { useState } from 'react'
import { GitCompare, ArrowLeftRight, ChevronLeft, ChevronRight, Clock, CheckCircle, XCircle, Loader2, AlertTriangle } from 'lucide-react'
import { useToolHistory, formatTimeAgo } from '@/hooks/useToolHistory'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { DropZone } from '@/components/shared/DropZone'
import { EmptyState } from '@/components/shared/EmptyState'
import { apiFetch } from '@/lib/api'

type ComparisonFocus = 'full' | 'clauses' | 'risks'

interface ComparisonDifference {
  section: string
  doc_a: string
  doc_b: string
  significance: string
}

interface ComparisonResult {
  summary: string
  differences: ComparisonDifference[]
  risk_assessment: string
  recommendation: string
}

const inputClass = "w-full rounded-lg border border-border bg-secondary text-foreground px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"


const SIG_STYLE: Record<string, { icon: typeof AlertTriangle; color: string; bg: string }> = {
  high: { icon: XCircle, color: 'text-red-400', bg: 'border-red-500/30 bg-red-500/5' },
  medium: { icon: AlertTriangle, color: 'text-amber-400', bg: 'border-amber-500/30 bg-amber-500/5' },
  low: { icon: CheckCircle, color: 'text-green-400', bg: 'border-green-500/30 bg-green-500/5' },
}

export function DocumentComparisonPage() {
  const { t } = useI18n()
  const { history, reload: reloadHistory } = useToolHistory('compare')
  const [panelCollapsed, setPanelCollapsed] = useState(false)
  const [focus, setFocus] = useState<ComparisonFocus>('full')
  const [docA, setDocA] = useState<File | null>(null)
  const [docB, setDocB] = useState<File | null>(null)
  const [context, setContext] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ComparisonResult | null>(null)
  const [showErrors, setShowErrors] = useState(false)

  async function handleCompare() {
    if (!docA || !docB) return
    setLoading(true)
    setError(null)
    try {
      const formData = new FormData()
      formData.append('doc_a', docA)
      formData.append('doc_b', docB)
      formData.append('focus', focus)
      if (context.trim()) formData.append('context', context)

      const response = await apiFetch('/document-tools/compare', {
        method: 'POST',
        body: formData,
      })
      const data = await response.json()
      setResult(data)
      reloadHistory()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Comparison failed')
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
            title={t('compare.title')}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <GitCompare className="h-4 w-4 text-muted-foreground" />
        </div>
      ) : (
      <div className="flex w-[340px] shrink-0 flex-col border-r border-border/50">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
          <div>
            <h1 className="text-sm font-semibold">{t('compare.title')}</h1>
            <p className="text-[10px] text-muted-foreground">Unggah dua dokumen untuk dibandingkan</p>
          </div>
          <button onClick={() => setPanelCollapsed(true)} className="text-muted-foreground hover:text-foreground transition-colors">
            <ChevronLeft className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 overflow-y-auto" style={{ flex: '3 1 0' }}>
          <div className="px-5 py-4 space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('compare.doc1')} <span className="text-red-400">*</span></label>
              <div className={showErrors && !docA ? 'rounded-lg border border-red-500/50' : ''}>
                <DropZone label={t('compare.doc1')} onFileSelect={setDocA} />
              </div>
              {showErrors && !docA && <p className="text-[10px] text-red-400">Please upload a document</p>}
            </div>

            <div className="flex justify-center">
              <button className="flex h-7 w-7 items-center justify-center rounded-full border border-border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors" title={t('compare.swap')} onClick={() => { const tmp = docA; setDocA(docB); setDocB(tmp) }}>
                <ArrowLeftRight className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('compare.doc2')} <span className="text-red-400">*</span></label>
              <div className={showErrors && !docB ? 'rounded-lg border border-red-500/50' : ''}>
                <DropZone label={t('compare.doc2')} onFileSelect={setDocB} />
              </div>
              {showErrors && !docB && <p className="text-[10px] text-red-400">Please upload a document</p>}
            </div>

            <div className="space-y-1.5 pt-2">
              <label className="text-xs font-medium">{t('compare.focus')}</label>
              <div className="flex flex-col gap-1.5">
                {(['full', 'clauses', 'risks'] as const).map((opt) => (
                  <button
                    key={opt}
                    onClick={() => setFocus(opt)}
                    className={`rounded-lg px-3 py-2 text-xs font-medium text-left transition-colors ${
                      focus === opt ? 'bg-primary/10 text-primary border border-primary/30' : 'bg-secondary text-muted-foreground hover:text-foreground border border-transparent'
                    }`}
                  >
                    {t(`compare.focus.${opt}`)}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium">Additional Context</label>
              <textarea className={`${inputClass} min-h-[64px] resize-none`} placeholder="Any specific areas to focus on..." value={context} onChange={(e) => setContext(e.target.value)} />
            </div>

            <div onClick={() => { if (!docA || !docB) setShowErrors(true) }}>
              <Button className="w-full text-xs" disabled={loading || !docA || !docB} onClick={handleCompare}>
                {loading ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <GitCompare className="mr-2 h-3.5 w-3.5" />}
                {loading ? 'Comparing...' : t('compare.generate')}
              </Button>
            </div>
            {showErrors && (!docA || !docB) && (
              <p className="text-[10px] text-red-400">Please upload both documents to compare</p>
            )}

            {error && <p className="text-xs text-red-400">{error}</p>}
          </div>
        </div>

        <div className="min-h-0 flex flex-col border-t border-border/50" style={{ flex: '1 1 0' }}>
          <div className="flex items-center justify-between px-5 py-2.5 shrink-0">
            <div className="flex items-center gap-1.5">
              <Clock className="h-3 w-3 text-muted-foreground" />
              <span className="text-[10px] font-semibold text-muted-foreground">{t('compare.history')}</span>
            </div>
            <span className="text-[10px] text-primary cursor-pointer hover:underline">View all &rarr;</span>
          </div>
          <div className="flex-1 overflow-y-auto min-h-0 px-3 pb-2 space-y-0.5">
            {history.length === 0 ? (
              <p className="text-[10px] text-muted-foreground px-2 py-3">No comparisons yet</p>
            ) : history.map((item) => (
              <div key={item.id} className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/50 transition-colors cursor-pointer">
                <GitCompare className="h-4 w-4 shrink-0 text-[var(--feature-management)]" />
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] font-medium truncate">{item.title}</p>
                  <p className="text-[9px] text-muted-foreground">{(item.input_params as Record<string, string>).focus} &middot; {formatTimeAgo(item.created_at)}</p>
                </div>
                <CheckCircle className="h-3.5 w-3.5 shrink-0 text-green-400" />
              </div>
            ))}
          </div>
        </div>
      </div>
      )}

      {/* Column 3 -- Results */}
      <div className="flex-1 flex flex-col overflow-y-auto">
        {result ? (
          <div className="p-8 space-y-6">
            <div>
              <h2 className="text-lg font-semibold">Comparison Results</h2>
              <p className="text-xs text-muted-foreground mt-1">{result.summary}</p>
            </div>

            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Differences</h3>
              {result.differences.map((diff, i) => {
                const style = SIG_STYLE[diff.significance] || SIG_STYLE.low
                const SigIcon = style.icon
                return (
                  <div key={i} className={`rounded-lg border p-4 space-y-2 ${style.bg}`}>
                    <div className="flex items-center gap-2">
                      <SigIcon className={`h-3.5 w-3.5 ${style.color}`} />
                      <span className="text-xs font-semibold">{diff.section}</span>
                      <span className={`text-[10px] ml-auto ${style.color}`}>{diff.significance}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-md bg-background/50 p-3">
                        <p className="text-[10px] font-semibold text-muted-foreground mb-1">Document A</p>
                        <p className="text-xs">{diff.doc_a}</p>
                      </div>
                      <div className="rounded-md bg-background/50 p-3">
                        <p className="text-[10px] font-semibold text-muted-foreground mb-1">Document B</p>
                        <p className="text-xs">{diff.doc_b}</p>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="rounded-lg border border-border bg-secondary/30 p-4 space-y-2">
              <h3 className="text-sm font-semibold">Risk Assessment</h3>
              <p className="text-xs">{result.risk_assessment}</p>
            </div>

            <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-2">
              <h3 className="text-sm font-semibold text-primary">Recommendation</h3>
              <p className="text-xs">{result.recommendation}</p>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center">
            <EmptyState icon={GitCompare} title="Unggah dua dokumen untuk dibandingkan" subtitle="Hasil perbandingan akan tampil di sini" />
          </div>
        )}
      </div>
    </div>
  )
}
