import { Send, Plus, FileText, Mic, Globe } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'

interface InputActionBarProps {
  onSend: () => void
  disabled: boolean
  showVersion?: boolean
  webSearchEnabled: boolean
  onToggleWebSearch: () => void
}

export function InputActionBar({
  onSend,
  disabled,
  showVersion,
  webSearchEnabled,
  onToggleWebSearch,
}: InputActionBarProps) {
  const { t } = useI18n()

  return (
    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-border/50">
      <button className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
        <Plus className="h-4 w-4" />
      </button>
      <button className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
        <FileText className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={onToggleWebSearch}
        className={`h-8 px-2 rounded-lg flex items-center gap-1 text-xs transition-colors ${
          webSearchEnabled
            ? 'bg-primary/10 text-primary hover:bg-primary/15'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
        }`}
        aria-pressed={webSearchEnabled}
        title={t('chat.webSearchTooltip')}
      >
        <Globe className="h-4 w-4" />
        <span>{t('chat.webSearchToggle')}</span>
      </button>
      <div className="flex-1" />
      {showVersion && (
        <span className="text-xs text-muted-foreground">{t('welcome.version')}</span>
      )}
      <button className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
        <Mic className="h-4 w-4" />
      </button>
      <button
        onClick={onSend}
        disabled={disabled}
        className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-all disabled:opacity-50 hover:shadow-[var(--glow-sm)] active:scale-[0.98]"
      >
        <Send className="h-4 w-4" />
      </button>
    </div>
  )
}
