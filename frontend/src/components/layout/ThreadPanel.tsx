import { useState } from 'react'
import { Plus, Search, PanelLeftClose } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ThreadList } from '@/components/chat/ThreadList'
import { useI18n } from '@/i18n/I18nContext'
import { useAuth } from '@/contexts/AuthContext'
import { useChatContext } from '@/contexts/ChatContext'
import { deriveDisplayName } from './UserAvatar'

interface ThreadPanelProps {
  collapsed: boolean
  onToggleCollapse: () => void
}

export function ThreadPanel({ collapsed, onToggleCollapse }: ThreadPanelProps) {
  const { t } = useI18n()
  const { user } = useAuth()
  const {
    threads,
    activeThreadId,
    handleSelectThread,
    handleCreateThread,
    handleDeleteThread,
  } = useChatContext()
  const [searchQuery, setSearchQuery] = useState('')

  const filteredThreads = searchQuery
    ? threads.filter((thread) =>
        thread.title.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : threads

  const displayName = user?.email ? deriveDisplayName(user.email) : ''

  // When collapsed, render nothing — the toggle lives in the IconRail
  if (collapsed) {
    return null
  }

  return (
    <div className="flex h-full w-[340px] shrink-0 flex-col border-r border-border glass dot-grid transition-all duration-200">
      <div className="flex items-center justify-between p-4">
        <div>
          <img src="/lexcore-full-dark.svg" alt="LexCore" className="h-7" />
          <p className="text-xs text-muted-foreground mt-1">{t('sidebar.chatHistory')}</p>
        </div>
        <button
          onClick={onToggleCollapse}
          className="flex items-center justify-center h-8 w-8 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors focus-ring"
          title="Collapse sidebar"
        >
          <PanelLeftClose className="h-4 w-4" />
        </button>
      </div>

      <div className="px-3 pb-3">
        <Button onClick={handleCreateThread} className="w-full gap-2 h-10" size="sm">
          <Plus className="h-4 w-4" />
          {t('chat.newChat')}
        </Button>
      </div>

      <div className="px-3 pb-3">
        <div className="flex items-center gap-2 rounded-md border border-border bg-secondary px-2 py-2 shadow-[var(--shadow-xs)]">
          <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <input
            type="text"
            placeholder={t('sidebar.searchPlaceholder')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-transparent text-xs text-foreground placeholder:text-muted-foreground focus:outline-none"
          />
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        <ThreadList
          threads={filteredThreads}
          activeThreadId={activeThreadId}
          onSelect={handleSelectThread}
          onDelete={handleDeleteThread}
        />
      </div>

      <div className="border-t border-border/50 p-3">
        <div className="flex items-center gap-2">
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-foreground truncate">{displayName}</p>
            <p className="text-[10px] text-muted-foreground">{t('sidebar.role')}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
