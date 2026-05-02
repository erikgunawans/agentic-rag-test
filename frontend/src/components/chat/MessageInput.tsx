import { useState } from 'react'
import { X, GitFork } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { usePublicSettings } from '@/hooks/usePublicSettings'
import { ContextWindowBar } from './ContextWindowBar'
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
  const { webSearchEnabled, setWebSearchEnabled, usage } = useChatContext()
  // Phase 12 / CTX-04: contextWindow denominator from /settings/public.
  // Single fetch per app load via module-level cache (D-P12-06).
  const { contextWindow } = usePublicSettings()

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
      <div className="mx-auto max-w-2xl rounded-2xl border bg-card p-4 shadow-[var(--shadow-md)] transition-shadow focus-within:shadow-[var(--glow-primary)] gradient-border-animated">
        {/* Phase 12 / CTX-04 / D-P12-07: bar lives inside the existing
            max-w-2xl container, ABOVE the textarea. Spec deviation note:
            PRD says max-w-3xl; we reuse the existing max-w-2xl wrapper for
            visual consistency (the existing chat-input container width). */}
        <ContextWindowBar usage={usage} contextWindow={contextWindow} />
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
        <InputActionBar
          onSend={handleSend}
          disabled={disabled || !value.trim()}
          webSearchEnabled={webSearchEnabled}
          onToggleWebSearch={() => setWebSearchEnabled((v) => !v)}
        />
      </div>
    </div>
  )
}
