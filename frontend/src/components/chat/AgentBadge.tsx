import { Search, Database, MessageCircle, Loader2 } from 'lucide-react'

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
