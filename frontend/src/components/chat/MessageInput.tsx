import { useState } from 'react'
import { X, GitFork } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { usePublicSettings } from '@/hooks/usePublicSettings'
import { ContextWindowBar } from './ContextWindowBar'
import { InputActionBar } from './InputActionBar'

interface MessageInputProps {
  // Phase 17 / DEEP-01 / D-24: onSend accepts an optional options bag.
  // When deep_mode_enabled=true and the toggle is on, { deepMode: true } is forwarded.
  // When toggle is off, either no second arg or { deepMode: false } — caller checks deepMode===true.
  onSend: (message: string, opts?: { deepMode?: boolean }) => void
  disabled: boolean
  forkParentId?: string | null
  onCancelFork?: () => void
}

export function MessageInput({ onSend, disabled, forkParentId, onCancelFork }: MessageInputProps) {
  const [value, setValue] = useState('')
  // Phase 17 / DEEP-01 / D-24: per-message deep mode toggle; resets after each send.
  const [deepMode, setDeepMode] = useState(false)
  const { t } = useI18n()
  const { webSearchEnabled, setWebSearchEnabled, usage } = useChatContext()
  // Phase 12 / CTX-04: contextWindow denominator from /settings/public.
  // Phase 17 / DEEP-03: deepModeEnabled — feature gate for the toggle button.
  // Single fetch per app load via module-level cache (D-P12-06).
  const { contextWindow, deepModeEnabled } = usePublicSettings()

  function handleSend() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    // Phase 17 / DEEP-01 / D-24: forward deepMode flag; reset toggle after send.
    onSend(trimmed, deepMode ? { deepMode: true } : undefined)
    setValue('')
    setDeepMode(false) // per-message semantic — reset for next message
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
          deepModeEnabled={deepModeEnabled}
          deepMode={deepMode}
          onToggleDeepMode={() => setDeepMode((v) => !v)}
        />
      </div>
    </div>
  )
}
