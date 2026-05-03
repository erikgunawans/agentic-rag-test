/**
 * Phase 19 / TASK-07 / D-25 — Sub-agent task panel.
 *
 * Renders one card per task_id in the tasks Map slice. Panel sits to the
 * right of WorkspacePanel in the chat layout flex row (UI-SPEC L157).
 *
 * Rules:
 *   - Visibility: render null when tasks.size === 0 (same as WorkspacePanel)
 *   - bg-background, NO glass/blur (CLAUDE.md persistent-panel rule)
 *   - Does NOT auto-hide on all-complete (UI-SPEC L200)
 *   - Rendered in ChatPage, NOT AppLayout (UI-SPEC L457)
 *   - SubAgentPanel.tsx is NOT modified (UI-SPEC L459)
 */
import { useState } from 'react'
import { ChevronDown, ChevronRight, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { cn } from '@/lib/utils'
import type { TaskState } from '@/hooks/useChatState'

function TaskStatusIcon({ status }: { status: TaskState['status'] }) {
  if (status === 'running') return <Loader2 size={16} className="animate-spin text-purple-500 shrink-0" aria-hidden="true" />
  if (status === 'complete') return <CheckCircle2 size={16} className="text-green-500 shrink-0" aria-hidden="true" />
  return <AlertCircle size={16} className="text-red-500 shrink-0" aria-hidden="true" />
}

function TaskCard({ task }: { task: TaskState }) {
  return (
    <li
      className="rounded-lg border bg-muted/40 p-3 text-sm space-y-2"
      aria-label={`${task.status}: ${task.description.slice(0, 60)}`}
    >
      <div className="flex items-start gap-2">
        <TaskStatusIcon status={task.status} />
        <span className="text-sm text-foreground leading-tight">{task.description}</span>
      </div>
      {task.contextFiles.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {task.contextFiles.map((p) => (
            <span
              key={p}
              title={p}
              className="rounded-full bg-zinc-200 dark:bg-zinc-800 px-2 py-1 text-[11px] max-w-[120px] truncate"
            >
              {p}
            </span>
          ))}
        </div>
      )}
      {task.toolCalls.length > 0 && (
        <ul className="space-y-1 pl-4">
          {task.toolCalls.map((c) => (
            <li key={c.toolCallId} className="flex items-center gap-2 text-muted-foreground">
              <span className="font-mono text-[11px]">{c.tool}</span>
              <span className="text-[10px] opacity-60">{c.toolCallId}</span>
            </li>
          ))}
        </ul>
      )}
      {task.status === 'complete' && task.result && (
        <p className="text-xs text-muted-foreground line-clamp-2">{task.result}</p>
      )}
      {task.status === 'error' && task.error && (
        <p className="text-xs text-red-600 dark:text-red-400 line-clamp-2">
          {task.error.detail ?? task.error.error}
        </p>
      )}
    </li>
  )
}

export function TaskPanel() {
  const { t } = useI18n()
  const { tasks } = useChatContext()
  const [collapsed, setCollapsed] = useState(false)

  // Visibility rule (UI-SPEC L159 — same pattern as WorkspacePanel)
  if (tasks.size === 0) return null

  return (
    <aside
      role="complementary"
      data-testid="task-panel"
      aria-label={t('taskPanel.title')}
      className={cn(
        'flex flex-col w-72 shrink-0 border-l border-border/50',
        'bg-background',  // CLAUDE.md persistent-panel rule — NO glass/blur
      )}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <h3 className="text-sm font-semibold text-foreground">
          {t('taskPanel.title')}{' '}
          <span className="text-muted-foreground font-normal">({tasks.size})</span>
        </h3>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? t('taskPanel.expand') : t('taskPanel.collapse')}
          className="flex h-6 w-6 items-center justify-center rounded hover:bg-accent transition-colors text-muted-foreground"
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>
      {!collapsed && (
        <div className="flex-1 overflow-y-auto px-4 py-3">
          <ul className="space-y-2">
            {[...tasks.values()].map((task) => (
              <TaskCard key={task.taskId} task={task} />
            ))}
          </ul>
        </div>
      )}
    </aside>
  )
}
