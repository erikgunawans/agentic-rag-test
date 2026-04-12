import { useState } from 'react'
import { Plus, ChevronLeft, ChevronRight, Search, Settings } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ThreadList } from '@/components/chat/ThreadList'
import { useI18n } from '@/i18n/I18nContext'
import { useAuth } from '@/contexts/AuthContext'
import { useChatContext } from '@/contexts/ChatContext'
import { deriveDisplayName, getInitials } from './UserAvatar'

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
  const initials = user?.email ? getInitials(user.email) : ''

  if (collapsed) {
    return (
      <div className="flex h-full w-[50px] shrink-0 flex-col items-center border-r border-border glass py-4 gap-3">
        <button
          onClick={onToggleCollapse}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          title={t('sidebar.title')}
        >
          <ChevronRight className="h-4 w-4" />
        </button>
        <Button onClick={handleCreateThread} size="icon" className="h-8 w-8">
          <Plus className="h-4 w-4" />
        </Button>
        <div className="flex-1" />
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-[9px] font-semibold text-primary-foreground">
          {initials}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full w-[340px] shrink-0 flex-col border-r border-border glass dot-grid transition-all duration-200">
      <div className="flex items-center justify-between p-4">
        <div>
          <h1 className="text-sm font-bold text-sidebar-foreground">{t('sidebar.title')}</h1>
          <p className="text-xs text-muted-foreground">{t('sidebar.chatHistory')}</p>
        </div>
        <button
          onClick={onToggleCollapse}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
      </div>

      <div className="px-3 pb-3">
        <Button onClick={handleCreateThread} className="w-full gap-2" size="sm">
          <Plus className="h-4 w-4" />
          {t('chat.newChat')}
        </Button>
      </div>

      <div className="px-3 pb-3">
        <div className="flex items-center gap-2 rounded-md border border-border bg-secondary px-2 py-1.5 shadow-[var(--shadow-xs)]">
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
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-foreground truncate">{displayName}</p>
            <p className="text-[10px] text-muted-foreground">{t('sidebar.role')}</p>
          </div>
          <button className="text-muted-foreground hover:text-foreground transition-colors">
            <Settings className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  )
}
