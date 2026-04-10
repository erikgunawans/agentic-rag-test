import { useState } from 'react'
import { Plus, FileText, Send } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ChatInputCardProps {
  onSend: (message: string) => void
  disabled?: boolean
}

export function ChatInputCard({ onSend, disabled }: ChatInputCardProps) {
  const [value, setValue] = useState('')
  const [isFocused, setIsFocused] = useState(false)

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

  const isSendDisabled = disabled || !value.trim()

  return (
    <div className="w-full max-w-[820px]">
      <div
        className={cn(
          'bg-bg-elevated rounded-[20px] p-5 border transition-all duration-200',
          isFocused
            ? 'border-border-accent shadow-[0_0_0_1px_var(--border-accent),0_0_40px_var(--accent-glow)]'
            : 'border-border-subtle shadow-[0_4px_24px_rgba(0,0,0,0.3)]'
        )}
      >
        <textarea
          className="w-full bg-transparent border-none outline-none resize-none text-[15px] text-foreground leading-relaxed min-h-[50px] placeholder:text-text-faint"
          placeholder="What would you like to know?"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          disabled={disabled}
        />

        {/* Bottom toolbar */}
        <div className="flex items-center justify-between mt-3">
          {/* Left buttons */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="flex items-center justify-center w-9 h-9 bg-bg-surface rounded-[10px] text-muted-foreground hover:bg-bg-hover hover:text-foreground transition-colors"
            >
              <Plus size={18} />
            </button>
            <button
              type="button"
              className="flex items-center justify-center w-9 h-9 bg-bg-surface rounded-[10px] text-muted-foreground hover:bg-bg-hover hover:text-foreground transition-colors"
            >
              <FileText size={18} />
            </button>
          </div>

          {/* Right side */}
          <div className="flex items-center gap-2.5">
            <div className="h-7 px-3 flex items-center border border-border-subtle rounded-full text-[12px] text-text-faint">
              RAG v1.0
            </div>
            <button
              type="button"
              onClick={handleSend}
              disabled={isSendDisabled}
              className={cn(
                'flex items-center justify-center w-9 h-9 rounded-[10px] text-white transition-all',
                isSendDisabled
                  ? 'bg-accent-primary/50 cursor-not-allowed'
                  : 'bg-accent-primary hover:bg-[#8B6EFD] hover:shadow-[0_4px_16px_rgba(124,92,252,0.5)]'
              )}
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
