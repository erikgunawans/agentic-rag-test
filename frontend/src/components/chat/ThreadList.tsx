import { useMemo, useState } from 'react'
import { Trash2, MessageSquare, ChevronDown, ChevronRight } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useI18n } from '@/i18n/I18nContext'
import type { Thread } from '@/lib/database.types'

interface ThreadListProps {
  threads: Thread[]
  activeThreadId: string | null
  onSelect: (threadId: string) => void
  onDelete: (threadId: string) => void
}

interface ThreadGroup {
  labelKey: string
  threads: Thread[]
}

function groupThreadsByDate(threads: Thread[]): ThreadGroup[] {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo = new Date(today.getTime() - 7 * 86400000)

  const groups: Record<string, Thread[]> = {
    'thread.today': [],
    'thread.yesterday': [],
    'thread.previous7': [],
    'thread.older': [],
  }

  for (const thread of threads) {
    const d = new Date(thread.updated_at || thread.created_at)
    if (d >= today) {
      groups['thread.today'].push(thread)
    } else if (d >= yesterday) {
      groups['thread.yesterday'].push(thread)
    } else if (d >= weekAgo) {
      groups['thread.previous7'].push(thread)
    } else {
      groups['thread.older'].push(thread)
    }
  }

  return Object.entries(groups)
    .filter(([, threads]) => threads.length > 0)
    .map(([labelKey, threads]) => ({ labelKey, threads }))
}

function CollapsibleGroup({
  group,
  activeThreadId,
  onSelect,
  onDelete,
  defaultOpen = true,
}: {
  group: ThreadGroup
  activeThreadId: string | null
  onSelect: (threadId: string) => void
  onDelete: (threadId: string) => void
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  const { t } = useI18n()

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1 px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        {open ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
        <span>{t(group.labelKey)}</span>
        <span className="ml-auto text-[10px] tabular-nums">{group.threads.length}</span>
      </button>
      {open && (
        <div className="space-y-0.5 pb-1">
          {group.threads.map((thread) => (
            <div
              key={thread.id}
              className={`group flex items-center gap-2 rounded-md px-3 py-2 cursor-pointer transition-colors mx-1 ${
                thread.id === activeThreadId
                  ? 'bg-accent text-accent-foreground'
                  : 'hover:bg-muted'
              }`}
              onClick={() => onSelect(thread.id)}
            >
              <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="flex-1 truncate text-sm">{thread.title}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete(thread.id)
                }}
                className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive focus-ring flex items-center justify-center min-w-[28px] min-h-[28px]"
                aria-label="Delete thread"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function ThreadList({
  threads,
  activeThreadId,
  onSelect,
  onDelete,
}: ThreadListProps) {
  const groups = useMemo(() => groupThreadsByDate(threads), [threads])

  return (
    <ScrollArea className="h-full">
      {threads.length === 0 ? (
        <div className="p-4 text-center text-sm text-muted-foreground">—</div>
      ) : (
        <div className="py-2 space-y-1">
          {groups.map((group) => (
            <CollapsibleGroup
              key={group.labelKey}
              group={group}
              activeThreadId={activeThreadId}
              onSelect={onSelect}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </ScrollArea>
  )
}
