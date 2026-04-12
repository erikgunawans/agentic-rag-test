import { useState } from 'react'
import { Scale, X, Clock, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { DropZone } from '@/components/shared/DropZone'
import { EmptyState } from '@/components/shared/EmptyState'

type AnalysisType = 'risk' | 'obligations' | 'clauses' | 'missing'
type Law = 'indonesia' | 'singapore' | 'international' | 'custom'
type Depth = 'quick' | 'standard' | 'deep'

const inputClass = "w-full rounded-lg border border-border bg-secondary text-foreground px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"

interface RecentItem { id: string; title: string; depth: string; risk: string; time: string; status: 'low' | 'medium' | 'high' }
const MOCK_RECENT: RecentItem[] = [
  { id: '1', title: 'Kontrak-Kerja.pdf', depth: 'Deep', risk: 'High Risk', time: '2h ago', status: 'high' },
  { id: '2', title: 'NDA-Final.docx', depth: 'Standard', risk: 'Low Risk', time: '1d ago', status: 'low' },
  { id: '3', title: 'Perjanjian-Sewa.pdf', depth: 'Quick', risk: 'Medium Risk', time: '3d ago', status: 'medium' },
  { id: '4', title: 'Lisensi-Software.docx', depth: 'Deep', risk: 'Low Risk', time: '1w ago', status: 'low' },
]
const STATUS_ICON = { low: CheckCircle, medium: AlertTriangle, high: XCircle }
const STATUS_COLOR = { low: 'text-green-400', medium: 'text-amber-400', high: 'text-red-400' }

export function ContractAnalysisPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [types, setTypes] = useState<Set<AnalysisType>>(new Set(['risk']))
  const [law, setLaw] = useState<Law>('indonesia')
  const [depth, setDepth] = useState<Depth>('standard')

  function toggleType(type: AnalysisType) {
    setTypes((prev) => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  return (
    <div className="flex h-full">
      {/* Column 2 — Form (75%) + History (25%) */}
      <div className="flex w-[360px] shrink-0 flex-col border-r border-border/50">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
          <div>
            <h1 className="text-sm font-semibold">{t('analysis.title')}</h1>
            <p className="text-[10px] text-muted-foreground">Identify risks and key clauses</p>
          </div>
          <button onClick={() => navigate('/')} className="text-muted-foreground hover:text-foreground transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 overflow-y-auto" style={{ flex: '3 1 0' }}>
          <div className="px-5 py-4 space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('analysis.document')} <span className="text-red-400">*</span></label>
              <DropZone />
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
              <textarea className={`${inputClass} min-h-[80px] resize-none`} placeholder={t('analysis.context')} />
            </div>

            <Button className="w-full text-xs" disabled>
              <Scale className="mr-2 h-3.5 w-3.5" />
              {t('analysis.run')}
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex flex-col border-t border-border/50" style={{ flex: '1 1 0' }}>
          <div className="flex items-center justify-between px-5 py-2.5 shrink-0">
            <div className="flex items-center gap-1.5">
              <Clock className="h-3 w-3 text-muted-foreground" />
              <span className="text-[10px] font-semibold text-muted-foreground">{t('analysis.history')}</span>
            </div>
            <span className="text-[10px] text-primary cursor-pointer hover:underline">View all →</span>
          </div>
          <div className="flex-1 overflow-y-auto min-h-0 px-3 pb-2 space-y-0.5">
            {MOCK_RECENT.map((item) => {
              const StatusIcon = STATUS_ICON[item.status]
              return (
                <div key={item.id} className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/50 transition-colors cursor-pointer">
                  <Scale className="h-4 w-4 shrink-0 text-[var(--feature-analysis)]" />
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-medium truncate">{item.title}</p>
                    <p className="text-[9px] text-muted-foreground">{item.depth} · {item.risk} · {item.time}</p>
                  </div>
                  <StatusIcon className={`h-3.5 w-3.5 shrink-0 ${STATUS_COLOR[item.status]}`} />
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Column 3 — Results (blank for now) */}
      <div className="flex-1 flex flex-col items-center justify-center">
        <EmptyState icon={Scale} title="Upload a contract and run analysis" subtitle="The risk assessment will appear here" />
      </div>
    </div>
  )
}
