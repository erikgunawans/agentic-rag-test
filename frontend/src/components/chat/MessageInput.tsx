import { useState } from 'react'
import { Send, X, GitFork } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'

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
    <div className="border-t border-border/50 p-4 glass">
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
      <div className="flex gap-2 items-end">
        <textarea
          className="flex-1 resize-none rounded-lg border border-border bg-secondary px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring min-h-[40px] max-h-[200px]"
          placeholder={t('chat.placeholder')}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
        />
        <Button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          size="icon"
          aria-label={t('chat.send')}
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
