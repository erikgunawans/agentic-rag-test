import { useState } from 'react'
import { X, GitFork } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { InputActionBar } from './InputActionBar'

interface MessageInputProps {
  onSend: (message: string) => void
  disabled: boolean
  forkParentId?: string | null
  onCancelFork?: () => void
}

export function MessageInput({ onSend, disabled, forkParentId, onCancelFork }: MessageInputProps) {
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
    <div className="shrink-0 p-4">
      <div className="mx-auto max-w-2xl rounded-2xl border bg-card p-4 shadow-[var(--shadow-md)] transition-shadow focus-within:shadow-[var(--glow-primary)]">
        {forkParentId && (
          <div className="flex items-center gap-2 mb-2 rounded-md bg-primary/10 px-3 py-1.5 text-xs text-primary">
            <GitFork className="h-3.5 w-3.5" />
            <span>{t('branch.forkMode')}</span>
            <button
              onClick={onCancelFork}
              className="ml-auto hover:text-foreground transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
        <textarea
          className="w-full resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none min-h-[40px] max-h-[200px]"
          placeholder={t('chat.placeholder')}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
        />
        <InputActionBar onSend={handleSend} disabled={disabled || !value.trim()} />
      </div>
    </div>
  )
}
