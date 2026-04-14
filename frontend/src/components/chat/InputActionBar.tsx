import { Send, Plus, FileText, Mic } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'

interface InputActionBarProps {
  onSend: () => void
  disabled: boolean
  showVersion?: boolean
}

export function InputActionBar({ onSend, disabled, showVersion }: InputActionBarProps) {
  const { t } = useI18n()

  return (
    <div className="flex items-center gap-2 mt-2 pt-2 border-t border-border/50">
      <button className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
        <Plus className="h-4 w-4" />
      </button>
      <button className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
        <FileText className="h-4 w-4" />
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
        className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-[oklch(0.55_0.18_250)] text-primary-foreground transition-all disabled:opacity-50 hover:shadow-[var(--glow-sm)]"
      >
        <Send className="h-4 w-4" />
      </button>
    </div>
  )
}
