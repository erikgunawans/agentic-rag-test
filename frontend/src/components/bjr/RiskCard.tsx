import { AlertTriangle, Shield, CheckCircle } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'

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

const LEVEL_STYLE: Record<string, { color: string; bg: string }> = {
  critical: { color: 'text-red-600 dark:text-red-400', bg: 'bg-red-500/10 border-red-500/30' },
  high: { color: 'text-red-600 dark:text-red-400', bg: 'bg-red-500/10 border-red-500/30' },
  medium: { color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30' },
  low: { color: 'text-green-600 dark:text-green-400', bg: 'bg-green-500/10 border-green-500/30' },
}

const STATUS_ICON: Record<string, typeof AlertTriangle> = {
  open: AlertTriangle,
  mitigated: Shield,
  accepted: CheckCircle,
  closed: CheckCircle,
}

interface RiskCardProps {
  risk: Risk
  onUpdateStatus?: (riskId: string, status: string) => void
}

export function RiskCard({ risk, onUpdateStatus }: RiskCardProps) {
  const { t } = useI18n()
  const style = LEVEL_STYLE[risk.risk_level] || LEVEL_STYLE.medium
  const StatusIcon = STATUS_ICON[risk.status] || AlertTriangle

  return (
    <div className={`rounded-lg border p-3 ${style.bg}`}>
      <div className="flex items-start gap-2">
        <StatusIcon className={`h-4 w-4 mt-0.5 shrink-0 ${style.color}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{risk.risk_title}</span>
            {risk.is_global && (
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground bg-secondary px-1.5 py-0.5 rounded">
                {t('bjr.globalRisk')}
              </span>
            )}
            <span className={`text-[10px] font-semibold uppercase tracking-wider ${style.color}`}>
              {risk.risk_level}
            </span>
          </div>
          {risk.description && (
            <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{risk.description}</p>
          )}
          {risk.mitigation && (
            <p className="mt-1 text-xs">
              <span className="font-medium">{t('bjr.mitigation')}:</span> {risk.mitigation}
            </p>
          )}
          <div className="mt-2 flex items-center gap-3 text-[10px] text-muted-foreground">
            {risk.owner_role && <span>{risk.owner_role}</span>}
            {onUpdateStatus && risk.status === 'open' && (
              <button
                onClick={() => onUpdateStatus(risk.id, 'mitigated')}
                className="text-primary hover:underline"
              >
                {t('bjr.markMitigated')}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
