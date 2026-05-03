import { useState } from 'react'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { usePublicSettings } from '@/hooks/usePublicSettings'
import { InputActionBar } from './InputActionBar'
import { FileUploadButton } from './FileUploadButton'

interface WelcomeInputProps {
  // Phase 17 / DEEP-01 / D-24 (form duplication rule — CLAUDE.md):
  // WelcomeInput mirrors MessageInput; also accepts optional opts for deepMode.
  onSend: (message: string, opts?: { deepMode?: boolean }) => void
  disabled: boolean
}

export function WelcomeInput({ onSend, disabled }: WelcomeInputProps) {
  const [value, setValue] = useState('')
  // Phase 17 / DEEP-01 / D-24: per-message deep mode toggle (same as MessageInput).
  const [deepMode, setDeepMode] = useState(false)
  const { t } = useI18n()
  const { webSearchEnabled, setWebSearchEnabled } = useChatContext()
  // Phase 17 / DEEP-03: read feature flag from /settings/public.
  const { deepModeEnabled } = usePublicSettings()

  function handleSend() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
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
    <div className="w-full rounded-2xl border bg-card p-4 shadow-[var(--shadow-md)] transition-shadow focus-within:shadow-[var(--glow-primary)] gradient-border-animated">
      <textarea
        className="w-full resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none min-h-[60px]"
        placeholder={t('chat.placeholder')}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        rows={2}
      />
      {/* Phase 20 / Plan 20-10 / UPL-04 (form-duplication rule per CLAUDE.md):
          FileUploadButton mirrors the MessageInput slot. The relative wrapper
          positions the in-flight progress card (absolute bottom-full). */}
      <div className="relative">
        <FileUploadButton />
        <InputActionBar
          onSend={handleSend}
          disabled={disabled || !value.trim()}
          showVersion
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
