import { Sparkles } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { MessageView } from '@/components/chat/MessageView'
import { MessageInput } from '@/components/chat/MessageInput'
import { SuggestionCards } from '@/components/chat/SuggestionCards'
import { deriveDisplayName } from '@/components/layout/UserAvatar'

export function ChatPage() {
  const { user } = useAuth()
  const { t } = useI18n()
  const {
    activeThreadId,
    messages,
    allMessages,
    forkParentId,
    isStreaming,
    streamingContent,
    activeTools,
    toolResults,
    activeAgent,
    handleSendMessage,
    handleSendFirstMessage,
    handleSwitchBranch,
    handleForkAt,
    handleCancelFork,
  } = useChatContext()

  const displayName = user?.email ? deriveDisplayName(user.email) : ''
  const isWelcome = !activeThreadId

  function handleSend(content: string) {
    if (isWelcome) {
      handleSendFirstMessage(content)
    } else {
      handleSendMessage(content)
    }
  }

  return (
    <div className="flex flex-1 min-h-0 flex-col">
      {isWelcome ? (
        <div className="flex flex-1 flex-col items-center justify-center px-4 relative overflow-hidden">
          <div className="absolute top-[15%] left-[10%] h-48 w-48 rounded-full bg-primary/5 blur-3xl animate-float-slow" />
          <div className="absolute bottom-[20%] right-[15%] h-36 w-36 rounded-full bg-[var(--feature-management)]/5 blur-3xl animate-float-delay" />
          <div className="flex w-full max-w-2xl flex-col items-center gap-6 animate-fade-in-up relative z-10">
            <Sparkles className="h-10 w-10 text-primary animate-glow-pulse rounded-full" />
            <div className="text-center">
              <h1 className="text-xl sm:text-3xl font-extrabold tracking-tight text-foreground">
                {t('welcome.greeting').split('{name}')[0]}
                <span className="gradient-text">{displayName}</span>
              </h1>
              <p className="mt-3 text-sm text-muted-foreground">
                {t('welcome.subtitle')}
              </p>
            </div>
          </div>
        </div>
      ) : (
        <MessageView
          messages={messages}
          allMessages={allMessages}
          streamingContent={streamingContent}
          isStreaming={isStreaming}
          activeTools={activeTools}
          toolResults={toolResults}
          activeAgent={activeAgent}
          onFork={handleForkAt}
          onSwitchBranch={handleSwitchBranch}
        />
      )}

      <MessageInput
        onSend={handleSend}
        disabled={isStreaming}
        forkParentId={isWelcome ? null : forkParentId}
        onCancelFork={handleCancelFork}
        showVersion={isWelcome}
      />

      {isWelcome && (
        <div className="shrink-0 pb-6 px-4 flex justify-center relative z-10">
          <div className="w-full max-w-2xl">
            <SuggestionCards />
          </div>
        </div>
      )}
    </div>
  )
}
