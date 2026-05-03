import { useAuth } from '@/contexts/AuthContext'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { useTheme } from '@/theme/ThemeContext'
import { WelcomeInput } from './WelcomeInput'
import { SuggestionCards } from './SuggestionCards'
import { deriveDisplayName } from '@/components/layout/UserAvatar'

export function WelcomeScreen() {
  const { user } = useAuth()
  const { t } = useI18n()
  const { resolvedTheme } = useTheme()
  const { handleSendFirstMessage, isStreaming } = useChatContext()

  const displayName = user?.email ? deriveDisplayName(user.email) : ''
  const logoSrc = resolvedTheme === 'light' ? '/lc-light.png' : '/lc-dark.png'

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 relative overflow-hidden">
      <div className="absolute top-[15%] left-[10%] h-48 w-48 rounded-full bg-primary/5 blur-3xl animate-float-slow" />
      <div className="absolute bottom-[20%] right-[15%] h-36 w-36 rounded-full bg-[var(--feature-management)]/5 blur-3xl animate-float-delay" />
      <div className="flex w-full max-w-2xl flex-col items-center gap-6 animate-fade-in-up relative z-10">
        <img src={logoSrc} alt="LexCore" className="h-14 w-auto" />

        <div className="text-center">
          <h1 className="text-xl sm:text-3xl font-semibold tracking-[-0.02em] text-foreground">
            {t('welcome.greeting').split('{name}')[0]}
            <span className="gradient-text">{displayName}</span>
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">
            {t('welcome.subtitle')}
          </p>
        </div>

        <WelcomeInput onSend={handleSendFirstMessage} disabled={isStreaming} />

        <SuggestionCards />
      </div>
    </div>
  )
}
