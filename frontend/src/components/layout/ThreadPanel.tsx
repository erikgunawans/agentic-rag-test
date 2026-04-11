import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ThreadList } from '@/components/chat/ThreadList'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'

export function ThreadPanel() {
  const { t } = useI18n()
  const {
    threads,
    activeThreadId,
    loadingThreads,
    handleSelectThread,
    handleCreateThread,
    handleDeleteThread,
  } = useChatContext()

  return (
    <div className="flex h-full w-60 shrink-0 flex-col border-r border-border bg-sidebar">
      {/* Header */}
      <div className="p-4">
        <h1 className="text-sm font-bold text-sidebar-foreground">{t('sidebar.title')}</h1>
        <p className="text-xs text-muted-foreground">{t('sidebar.subtitle')}</p>
      </div>

      {/* New Chat button */}
      <div className="px-3 pb-3">
        <Button onClick={handleCreateThread} className="w-full gap-2" size="sm">
          <Plus className="h-4 w-4" />
          {t('chat.newChat')}
        </Button>
      </div>

      {/* Recent conversations label */}
      <div className="px-4 pb-2">
        <span className="text-[10px] font-semibold tracking-wider text-muted-foreground">
          {t('sidebar.recentConversations')}
        </span>
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-hidden">
        <ThreadList
          threads={threads}
          activeThreadId={activeThreadId}
          onSelect={handleSelectThread}
          onCreate={handleCreateThread}
          onDelete={handleDeleteThread}
          loading={loadingThreads}
        />
      </div>
    </div>
  )
}
