import { useState } from 'react'
import { Send, Plus, FileText, Mic } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'

interface WelcomeInputProps {
  onSend: (message: string) => void
  disabled: boolean
}

export function WelcomeInput({ onSend, disabled }: WelcomeInputProps) {
  const [value, setValue] = useState('')
  const { t } = useI18n()

  function handleSend() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="w-full rounded-2xl border border-border bg-card p-4">
      <textarea
        className="w-full resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none min-h-[60px]"
        placeholder={t('chat.placeholder')}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={2}
      />
      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-border/50">
        <button className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
          <Plus className="h-4 w-4" />
        </button>
        <button className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
          <FileText className="h-4 w-4" />
        </button>
        <div className="flex-1" />
        <span className="text-xs text-muted-foreground">{t('welcome.version')}</span>
        <button className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
          <Mic className="h-4 w-4" />
        </button>
        <button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-opacity disabled:opacity-50 hover:opacity-90"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
