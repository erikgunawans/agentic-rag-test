/**
 * Phase 19 / STATUS-01 / D-24 / D-26 — Agent run status chip.
 *
 * Renders a sticky header chip showing the current agent run state:
 *   working | waiting_for_user | complete (auto-fades after 3000ms) | error
 *
 * When agentStatus === null, renders a sr-only aria-live container so
 * screen readers receive the next state change announcement (UI-SPEC L147).
 *
 * Rules:
 *   - NO glass/blur (CLAUDE.md persistent-panel rule)
 *   - Rendered in ChatPage, NOT AppLayout (UI-SPEC L455)
 *   - sticky top-0 z-10 applied by ChatPage wrapper (not this component)
 */
import { useEffect } from 'react'
import { MessageCircleQuestion, CheckCircle2, AlertCircle } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { cn } from '@/lib/utils'
import type { AgentStatus } from '@/hooks/useChatState'

function ChipIcon({ status }: { status: AgentStatus }) {
  if (status === 'working') {
    return <span className="h-1 w-1 rounded-full bg-primary animate-pulse" aria-hidden="true" />
  }
  if (status === 'waiting_for_user') {
    return <MessageCircleQuestion size={14} className="text-purple-600 dark:text-purple-400" aria-hidden="true" />
  }
  if (status === 'complete') {
    return <CheckCircle2 size={14} className="text-green-600 dark:text-green-400" aria-hidden="true" />
  }
  return <AlertCircle size={14} className="text-red-600 dark:text-red-400" aria-hidden="true" />
}

export function AgentStatusChip() {
  const { t } = useI18n()
  const { agentStatus, setAgentStatus } = useChatContext()

  // Auto-fade: on complete, set agentStatus to null after 3000ms (UI-SPEC L139).
  // Cleanup clears the timer if the component unmounts or status changes before it fires.
  useEffect(() => {
    if (agentStatus === 'complete') {
      const timer = setTimeout(() => setAgentStatus(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [agentStatus, setAgentStatus])

  if (agentStatus === null) {
    // UI-SPEC L147: keep aria-live container in DOM for reliable screen reader announcements.
    return <div role="status" aria-live="polite" className="sr-only" />
  }

  const labelKey = `agentStatus.${
    agentStatus === 'waiting_for_user' ? 'waitingForUser' : agentStatus
  }` as const

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={t(labelKey)}
      className={cn(
        'inline-flex items-center gap-2 px-2 py-1 rounded-full',
        'border border-current/20 transition-all duration-200',
        agentStatus === 'working' && 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300',
        agentStatus === 'waiting_for_user' && 'bg-purple-50 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300',
        agentStatus === 'complete' && 'bg-green-50 dark:bg-green-950/40 text-green-700 dark:text-green-300',
        agentStatus === 'error' && 'bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300',
      )}
    >
      <ChipIcon status={agentStatus} />
      <span className="text-sm font-semibold">{t(labelKey)}</span>
    </div>
  )
}
