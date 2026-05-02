import { Search, Database, MessageCircle, Loader2, Brain } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'

const AGENT_CONFIG: Record<string, { icon: typeof Search; label: string }> = {
  research: { icon: Search, label: 'Research Agent' },
  data_analyst: { icon: Database, label: 'Data Analyst' },
  general: { icon: MessageCircle, label: 'General Assistant' },
}

interface AgentBadgeProps {
  agent: string
  displayName?: string
  active?: boolean
}

export function AgentBadge({ agent, displayName, active = false }: AgentBadgeProps) {
  const config = AGENT_CONFIG[agent] || { icon: MessageCircle, label: displayName || agent }
  const Icon = config.icon
  const label = displayName || config.label

  if (active) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        <span>{label} is working...</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1.5 text-xs text-muted-foreground mb-1">
      <Icon className="h-3 w-3" />
      <span>{label}</span>
    </div>
  )
}

/**
 * Phase 17 / DEEP-04 / D-23: Deep Mode badge for assistant messages
 * generated via the deep-mode loop (messages.deep_mode=true).
 *
 * Styling: subtle purple-accent text + Brain icon, NOT a loud chip.
 * Uses 2026 Calibrated Restraint design tokens — no glass/backdrop-blur.
 */
export function DeepModeBadge() {
  const { t } = useI18n()
  return (
    <span
      data-testid="deep-mode-badge"
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium"
      style={{
        backgroundColor: 'oklch(0.55 0.22 290 / 0.12)',
        color: 'oklch(0.55 0.22 290)',
      }}
    >
      <Brain className="h-3 w-3" aria-hidden="true" />
      {t('chat.deepMode.badge')}
    </span>
  )
}
