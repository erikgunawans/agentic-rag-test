import { useState } from 'react'
import { ShieldCheck, X, Clock, CheckCircle, ShieldAlert, ShieldX } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useI18n } from '@/i18n/I18nContext'
import { Button } from '@/components/ui/button'
import { DropZone } from '@/components/shared/DropZone'
import { EmptyState } from '@/components/shared/EmptyState'

type Framework = 'ojk' | 'international' | 'gdpr' | 'custom'
type Scope = 'legal' | 'risks' | 'missing' | 'regulatory'

const inputClass = "w-full rounded-lg border border-border bg-secondary text-foreground px-3 py-2 text-xs placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"

interface RecentItem { id: string; title: string; framework: string; time: string; status: 'pass' | 'review' | 'fail' }
const MOCK_RECENT: RecentItem[] = [
  { id: '1', title: 'Kontrak-Layanan.pdf', framework: 'OJK', time: '3h ago', status: 'pass' },
  { id: '2', title: 'NDA-Draft.docx', framework: 'GDPR', time: '1d ago', status: 'review' },
  { id: '3', title: 'Employment-Contract.pdf', framework: 'International', time: '4d ago', status: 'fail' },
  { id: '4', title: 'Perjanjian-Sewa.pdf', framework: 'OJK', time: '1w ago', status: 'pass' },
]
const STATUS_ICON = { pass: CheckCircle, review: ShieldAlert, fail: ShieldX }
const STATUS_COLOR = { pass: 'text-green-400', review: 'text-amber-400', fail: 'text-red-400' }

export function ComplianceCheckPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const [framework, setFramework] = useState<Framework>('ojk')
  const [scopes, setScopes] = useState<Set<Scope>>(new Set(['legal']))

  function toggleScope(scope: Scope) {
    setScopes((prev) => {
      const next = new Set(prev)
      if (next.has(scope)) next.delete(scope)
      else next.add(scope)
      return next
    })
  }

  return (
    <div className="flex h-full">
      {/* Column 2 — Form (75%) + History (25%) */}
      <div className="flex w-[300px] shrink-0 flex-col border-r border-border/50">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border/50 shrink-0">
          <div>
            <h1 className="text-sm font-semibold">{t('compliance.title')}</h1>
            <p className="text-[10px] text-muted-foreground">Check regulatory compliance</p>
          </div>
          <button onClick={() => navigate('/')} className="text-muted-foreground hover:text-foreground transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 overflow-y-auto" style={{ flex: '3 1 0' }}>
          <div className="px-5 py-4 space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium">{t('compliance.document')} <span className="text-red-400">*</span></label>
              <DropZone />
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
              <textarea className={`${inputClass} min-h-[80px] resize-none`} placeholder={t('compliance.context')} />
            </div>

            <Button className="w-full text-xs" disabled>
              <ShieldCheck className="mr-2 h-3.5 w-3.5" />
              {t('compliance.run')}
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex flex-col border-t border-border/50" style={{ flex: '1 1 0' }}>
          <div className="flex items-center justify-between px-5 py-2.5 shrink-0">
            <div className="flex items-center gap-1.5">
              <Clock className="h-3 w-3 text-muted-foreground" />
              <span className="text-[10px] font-semibold text-muted-foreground">{t('compliance.history')}</span>
            </div>
            <span className="text-[10px] text-primary cursor-pointer hover:underline">View all →</span>
          </div>
          <div className="flex-1 overflow-y-auto min-h-0 px-3 pb-2 space-y-0.5">
            {MOCK_RECENT.map((item) => {
              const StatusIcon = STATUS_ICON[item.status]
              return (
                <div key={item.id} className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-muted/50 transition-colors cursor-pointer">
                  <ShieldCheck className="h-4 w-4 shrink-0 text-[var(--feature-compliance)]" />
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-medium truncate">{item.title}</p>
                    <p className="text-[9px] text-muted-foreground">{item.framework} · {item.time}</p>
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
        <EmptyState icon={ShieldCheck} title="Upload a document and run compliance check" subtitle="The compliance report will appear here" />
      </div>
    </div>
  )
}
