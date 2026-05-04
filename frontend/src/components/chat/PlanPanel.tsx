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
 * CLAUDE.md rule: persistent panel — solid surface only (bg-background / bg-white / bg-card). No glass.
 *
 * Collapse behavior: local useState toggle (ChevronRight/ChevronDown button),
 * matching the affordance pattern used by other sidebar panels.
 *
 * Phase 20 / PANEL-01 / PANEL-04 / D-11 / D-12:
 *   Locked variant — when harnessRun.status IN ('pending','running','paused'):
 *     - Lock icon (lucide, 16px, text-primary) with shim Tooltip
 *     - Harness-type label (pre-translated via t('harness.type.<harnessType>'))
 *     - Cancel button → shadcn Dialog confirmation → POST /threads/{id}/harness/cancel
 *     - paused arm renders identically to running (Phase 21 forward-compat)
 *   Surface stays solid bg-background (CLAUDE.md persistent-panel rule).
 */

import { useState } from 'react'
import { Circle, Loader2, CheckCircle2, ChevronDown, ChevronRight, Lock, X } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { cn } from '@/lib/utils'
import type { TodoStatus } from '@/lib/database.types'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { apiFetch } from '@/lib/api'

// ---------------------------------------------------------------------------
// Constant: active harness statuses (Phase 20 PANEL-04 / UI-SPEC L118)
// paused is included for Phase 21 forward-compat — renders identically to running
// ---------------------------------------------------------------------------
const ACTIVE_HARNESS_STATUSES = new Set(['pending', 'running', 'paused'])

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
  const { todos, isCurrentMessageDeepMode, harnessRun, activeThreadId } = useChatContext()
  const [collapsed, setCollapsed] = useState(false)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  // Phase 20 PANEL-04: locked variant when harness is active
  const isLocked = harnessRun != null && ACTIVE_HARNESS_STATUSES.has(harnessRun.status)
  const harnessLabelKey = harnessRun ? `harness.type.${harnessRun.harnessType}` : ''
  const harnessLabel = harnessRun ? (t(harnessLabelKey) || harnessRun.harnessType) : ''

  async function onConfirmCancel() {
    if (!harnessRun || !activeThreadId) return
    setCancelling(true)
    try {
      await apiFetch(`/chat/threads/${activeThreadId}/harness/cancel`, { method: 'POST' })
    } catch {
      // Non-fatal — UI re-renders on next SSE harness_phase_error event
    } finally {
      setCancelling(false)
      setCancelOpen(false)
    }
  }

  // D-22: visibility rule — show if deep mode is active OR thread has todos OR harness active
  const visible = isCurrentMessageDeepMode || todos.length > 0 || isLocked
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
      {/* Header with collapse toggle — locked or unlocked variant */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50 gap-2">
        {isLocked ? (
          <>
            <Tooltip>
              <TooltipTrigger asChild>
                <Lock
                  size={16}
                  className="text-primary shrink-0"
                  data-testid="harness-lock-icon"
                  aria-label={t('harness.lock.tooltip')}
                />
              </TooltipTrigger>
              <TooltipContent>{t('harness.lock.tooltip')}</TooltipContent>
            </Tooltip>
            <h3 className="text-sm font-semibold text-foreground truncate">{harnessLabel}</h3>
            <div className="flex-1" />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setCancelOpen(true)}
              data-testid="harness-cancel-button"
              className="h-8 px-3 gap-1"
            >
              <X size={14} />
              <span>{t('common.cancel')}</span>
            </Button>
            <button
              type="button"
              onClick={() => setCollapsed((c) => !c)}
              aria-label={collapsed ? 'expand' : 'collapse'}
              className="flex h-6 w-6 items-center justify-center rounded hover:bg-accent transition-colors text-muted-foreground"
            >
              {collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
            </button>
          </>
        ) : (
          <>
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
          </>
        )}
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

      {/* Cancel harness confirmation dialog (Phase 20 PANEL-04 / D-03) */}
      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {t('harness.cancel.confirmTitle').replace('{harnessType}', harnessLabel)}
            </DialogTitle>
            <DialogDescription>{t('harness.cancel.confirmBody')}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCancelOpen(false)}
              disabled={cancelling}
            >
              {t('harness.cancel.keepRunning')}
            </Button>
            <Button
              variant="destructive"
              onClick={onConfirmCancel}
              disabled={cancelling}
              data-testid="harness-cancel-confirm"
            >
              {t('harness.cancel.confirmAction')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  )
}
