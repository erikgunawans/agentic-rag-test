import { Plus, Trash2, MessageSquare } from 'lucide-react'
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

export function ThreadList({
  threads,
  activeThreadId,
  onSelect,
  onCreate,
  onDelete,
  loading,
}: ThreadListProps) {
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
          <div className="p-2 space-y-1">
            {threads.map((thread) => (
              <div
                key={thread.id}
                className={`group flex items-center gap-2 rounded-md px-3 py-2 cursor-pointer transition-colors ${
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
      </ScrollArea>
    </div>
  )
}
