import { useState } from 'react'
import { MessageSquare, Plus, Search, Trash2, Settings } from 'lucide-react'
import { ColumnHeader } from '@/components/shared/ColumnHeader'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'
import type { Thread } from '@/lib/database.types'

interface ChatSidebarProps {
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
    .filter(([, t]) => t.length > 0)
    .map(([label, t]) => ({ label, threads: t }))
}

function formatTimestamp(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())

  if (date >= today) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function getUserInitials(email: string | undefined): string {
  if (!email) return '??'
  return email.slice(0, 2).toUpperCase()
}

export function ChatSidebar({
  threads,
  activeThreadId,
  onSelect,
  onCreate,
  onDelete,
  loading,
}: ChatSidebarProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const { user, role } = useAuth()

  const filteredThreads = searchQuery
    ? threads.filter((t) =>
        t.title.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : threads

  const groups = groupThreadsByDate(filteredThreads)

  return (
    <div className="flex flex-col h-full">
      {/* 1. Column Header */}
      <ColumnHeader
        title="Knowledge Hub"
        subtitle="Chat History"
        rightIcon="chevron-left"
      />

      {/* 2. New Chat Button */}
      <div className="px-4 py-3">
        <button
          onClick={onCreate}
          disabled={loading}
          className={cn(
            'flex w-full items-center justify-center gap-2 h-11 rounded-xl',
            'bg-accent-primary text-white text-sm font-semibold',
            'hover:bg-[#8B6EFD] hover:shadow-[0_4px_20px_rgba(124,92,252,0.4)]',
            'transition-all duration-200',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <Plus size={16} />
          New Chat
        </button>
      </div>

      {/* 3. Search Bar */}
      <div className="px-3 py-2">
        <div
          className={cn(
            'flex items-center gap-2 h-9 px-3',
            'bg-bg-elevated rounded-[10px] border border-border-subtle'
          )}
        >
          <Search size={16} className="shrink-0 text-text-faint" />
          <input
            type="text"
            placeholder="Search conversations..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={cn(
              'flex-1 bg-transparent text-[13px] text-foreground',
              'placeholder:text-text-faint outline-none'
            )}
          />
        </div>
      </div>

      {/* 4. Conversation List */}
      <div className="flex-1 overflow-y-auto scrollbar-kh">
        {filteredThreads.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-text-faint">
            {searchQuery ? 'No matching conversations' : 'No conversations yet'}
          </div>
        ) : (
          <div className="py-1">
            {groups.map((group) => (
              <div key={group.label}>
                {/* Group Label */}
                <div className="text-[11px] font-semibold text-text-faint uppercase tracking-wider px-4 py-2">
                  {group.label}
                </div>

                {/* Thread Items */}
                {group.threads.map((thread) => (
                  <div
                    key={thread.id}
                    onClick={() => onSelect(thread.id)}
                    className={cn(
                      'group flex items-center gap-2.5 h-[52px] px-4 cursor-pointer',
                      'transition-colors',
                      thread.id === activeThreadId
                        ? 'bg-bg-hover'
                        : 'hover:bg-bg-hover'
                    )}
                  >
                    <MessageSquare size={16} className="shrink-0 text-slate-400" />
                    <span className="flex-1 text-[13px] font-medium text-foreground truncate">
                      {thread.title}
                    </span>
                    <span className="text-[11px] text-text-faint shrink-0">
                      {formatTimestamp(thread.updated_at || thread.created_at)}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        onDelete(thread.id)
                      }}
                      className={cn(
                        'hidden group-hover:flex items-center justify-center shrink-0',
                        'text-text-faint hover:text-destructive transition-colors'
                      )}
                      aria-label="Delete thread"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 5. User Profile Footer */}
      <div className="h-[72px] shrink-0 border-t border-border-subtle px-4 flex items-center gap-3">
        {/* Avatar */}
        <div className="flex items-center justify-center w-9 h-9 rounded-full bg-slate-700 shrink-0">
          <span className="text-[13px] font-semibold text-foreground">
            {getUserInitials(user?.email ?? undefined)}
          </span>
        </div>

        {/* User Info */}
        <div className="flex flex-col min-w-0 flex-1">
          <span className="text-[13px] font-semibold text-foreground truncate">
            {user?.email ?? 'Unknown'}
          </span>
          <span className="text-[11px] text-muted-foreground">
            {role}
          </span>
        </div>

        {/* Settings Button */}
        <button
          className={cn(
            'ml-auto flex items-center justify-center shrink-0',
            'text-muted-foreground hover:text-foreground transition-colors'
          )}
          aria-label="Settings"
        >
          <Settings size={20} />
        </button>
      </div>
    </div>
  )
}
