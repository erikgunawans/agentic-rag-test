import { useAuth } from '@/contexts/AuthContext'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { MessageInput } from './MessageInput'
import { SuggestionChips } from './SuggestionChips'
import { deriveDisplayName } from '@/components/layout/UserAvatar'

export function WelcomeScreen() {
  const { user } = useAuth()
  const { t } = useI18n()
  const { handleSendFirstMessage, isStreaming } = useChatContext()

  const displayName = user?.email ? deriveDisplayName(user.email) : ''

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4">
      <div className="flex w-full max-w-2xl flex-col items-center gap-6">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-2xl font-bold text-primary-foreground">
          K
        </div>

        <div className="text-center">
          <h1 className="text-2xl font-semibold text-foreground">
            {t('welcome.greeting', { name: displayName })}
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {t('welcome.subtitle')}
          </p>
        </div>

        <div className="w-full">
          <MessageInput onSend={handleSendFirstMessage} disabled={isStreaming} />
        </div>

        <SuggestionChips onSelect={handleSendFirstMessage} />
      </div>
    </div>
  )
}
