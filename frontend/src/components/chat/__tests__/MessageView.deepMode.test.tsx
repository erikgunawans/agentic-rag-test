/**
 * Phase 17 / DEEP-04 / D-23 — Vitest tests for Deep Mode badge in MessageView
 *
 * Tests assert:
 * - Badge renders on assistant messages with deep_mode=true
 * - Badge is hidden on assistant messages with deep_mode=false
 * - Badge is hidden for user messages even when deep_mode=true
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { I18nProvider } from '@/i18n/I18nContext'
import { MessageView } from '../MessageView'
import type { Message } from '@/lib/database.types'

// Mock supabase to avoid network calls in tests
vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
    },
  },
}))

// jsdom does not implement scrollIntoView — stub it globally
beforeEach(() => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn()
})

function makeMessage(overrides: Partial<Message>): Message {
  return {
    id: 'msg-1',
    thread_id: 'thread-1',
    user_id: 'user-1',
    role: 'assistant',
    content: 'Hello, this is an assistant response.',
    created_at: new Date().toISOString(),
    ...overrides,
  }
}

function renderMessageView(messages: Message[]) {
  return render(
    <I18nProvider>
      <MessageView
        messages={messages}
        allMessages={messages}
        streamingContent=""
        isStreaming={false}
      />
    </I18nProvider>
  )
}

describe('MessageView — Deep Mode badge (Phase 17 DEEP-04)', () => {
  it('renders Deep Mode badge on assistant message with deep_mode=true', () => {
    const msg = makeMessage({ role: 'assistant', deep_mode: true })
    renderMessageView([msg])
    expect(screen.getByTestId('deep-mode-badge')).toBeInTheDocument()
  })

  it('does not render Deep Mode badge on assistant message with deep_mode=false', () => {
    const msg = makeMessage({ role: 'assistant', deep_mode: false })
    renderMessageView([msg])
    expect(screen.queryByTestId('deep-mode-badge')).toBeNull()
  })

  it('does not render Deep Mode badge on assistant message without deep_mode field', () => {
    const msg = makeMessage({ role: 'assistant' })
    // deep_mode is not set
    renderMessageView([msg])
    expect(screen.queryByTestId('deep-mode-badge')).toBeNull()
  })

  it('does not render Deep Mode badge on user message even with deep_mode=true', () => {
    const msg = makeMessage({ role: 'user', content: 'User question', deep_mode: true })
    renderMessageView([msg])
    expect(screen.queryByTestId('deep-mode-badge')).toBeNull()
  })
})
