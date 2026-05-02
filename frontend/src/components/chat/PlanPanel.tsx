/**
 * Phase 17 / TODO-06 / TODO-07 / D-20 / D-22 / D-25 / D-26
 *
 * Plan Panel sidebar — displays the per-thread agent planning todo list.
 * Real-time updates from todos_updated SSE events via useChatContext.
 * Thread-reload hydration from GET /threads/{id}/todos (in useChatState useEffect).
 *
 * Visibility rule (D-22):
 *   visible when (a) isCurrentMessageDeepMode is true, OR (b) todos.length > 0.
 *   Hidden on non-deep-mode threads with no saved todos.
 *
 * Status indicators (D-25):
 *   pending     → zinc Circle dot
 *   in_progress → purple Loader2 with animate-spin
 *   completed   → green CheckCircle2
 *
 * CLAUDE.md rule: NO backdrop-blur / glass — this is a persistent sidebar panel.
 * Solid surface only (bg-background / bg-white / bg-card).
 *
 * Collapse behavior: local useState toggle (ChevronRight/ChevronDown button),
 * matching the affordance pattern used by other sidebar panels.
 */

import { useState } from 'react'
import { Circle, Loader2, CheckCircle2, ChevronDown, ChevronRight } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { cn } from '@/lib/utils'
import type { TodoStatus } from '@/lib/database.types'

// ---------------------------------------------------------------------------
// Status indicator sub-component (D-25)
// ---------------------------------------------------------------------------
function StatusIcon({ status }: { status: TodoStatus }) {
  if (status === 'completed') {
    return (
      <CheckCircle2
        size={16}
        className="text-green-500 shrink-0"
        data-testid="status-completed"
      />
    )
  }
  if (status === 'in_progress') {
    return (
      <Loader2
        size={16}
        className="animate-spin text-purple-500 shrink-0"
        data-testid="status-in-progress"
      />
    )
  }
  return (
    <Circle
      size={16}
      className="text-zinc-400 shrink-0"
      data-testid="status-pending"
    />
  )
}

// ---------------------------------------------------------------------------
// PlanPanel
// ---------------------------------------------------------------------------
export function PlanPanel() {
  const { t } = useI18n()
  const { todos, isCurrentMessageDeepMode } = useChatContext()
  const [collapsed, setCollapsed] = useState(false)

  // D-22: visibility rule — show if deep mode is active OR thread has todos
  const visible = isCurrentMessageDeepMode || todos.length > 0
  if (!visible) return null

  // Sort by position (D-04)
  const sortedTodos = [...todos].sort((a, b) => a.position - b.position)

  return (
    <aside
      data-testid="plan-panel"
      // NO backdrop-blur — CLAUDE.md persistent-panel rule (D-20)
      // Solid surface only
      className={cn(
        'flex flex-col w-72 shrink-0 border-l border-border/50',
        'bg-background',
      )}
      aria-label={t('planPanel.title')}
    >
      {/* Header with collapse toggle */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <h3 className="text-sm font-semibold text-foreground">{t('planPanel.title')}</h3>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? 'expand' : 'collapse'}
          className="flex h-6 w-6 items-center justify-center rounded hover:bg-accent transition-colors text-muted-foreground"
        >
          {collapsed ? (
            <ChevronRight size={14} />
          ) : (
            <ChevronDown size={14} />
          )}
        </button>
      </div>

      {/* Content — hidden when collapsed */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {sortedTodos.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('planPanel.empty')}</p>
          ) : (
            <ol className="space-y-2">
              {sortedTodos.map((todo) => (
                <li key={todo.id} className="flex items-start gap-2">
                  <StatusIcon status={todo.status} />
                  <span
                    className={cn(
                      'text-sm leading-tight',
                      todo.status === 'completed' && 'line-through text-muted-foreground',
                    )}
                  >
                    {todo.content}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </aside>
  )
}
