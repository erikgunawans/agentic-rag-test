import { useState } from 'react'
import { useI18n } from '@/i18n/I18nContext'
import { InputActionBar } from './InputActionBar'

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
      <InputActionBar onSend={handleSend} disabled={disabled || !value.trim()} showVersion />
    </div>
  )
}
