import { useState } from 'react'
import { Plus, Trash2, MessageSquare, ChevronDown, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { Thread } from '@/lib/database.types'

interface ThreadListProps {
  threads: Thread[]
  activeThreadId: string | null
  onSelect: (threadId: string) => void
  onCreate: () => void
  onDelete: (threadId: string) => void
  loading: boolean
}

interface ThreadGroup {
  label: string
  threads: Thread[]
}

function groupThreadsByDate(threads: Thread[]): ThreadGroup[] {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 86400000)
  const weekAgo = new Date(today.getTime() - 7 * 86400000)

  const groups: Record<string, Thread[]> = {
    Today: [],
    Yesterday: [],
    'Previous 7 Days': [],
    Older: [],
  }

  for (const thread of threads) {
    const d = new Date(thread.updated_at || thread.created_at)
    if (d >= today) {
      groups['Today'].push(thread)
    } else if (d >= yesterday) {
      groups['Yesterday'].push(thread)
    } else if (d >= weekAgo) {
      groups['Previous 7 Days'].push(thread)
    } else {
      groups['Older'].push(thread)
    }
  }

  return Object.entries(groups)
    .filter(([, threads]) => threads.length > 0)
    .map(([label, threads]) => ({ label, threads }))
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
        <span>{group.label}</span>
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
                className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
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
  onCreate,
  onDelete,
  loading,
}: ThreadListProps) {
  const groups = groupThreadsByDate(threads)

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b">
        <Button onClick={onCreate} className="w-full gap-2" size="sm" disabled={loading}>
          <Plus className="h-4 w-4" />
          New Thread
        </Button>
      </div>
      <ScrollArea className="flex-1">
        {threads.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted-foreground">No threads yet</div>
        ) : (
          <div className="py-2 space-y-1">
            {groups.map((group) => (
              <CollapsibleGroup
                key={group.label}
                group={group}
                activeThreadId={activeThreadId}
                onSelect={onSelect}
                onDelete={onDelete}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  )
}
