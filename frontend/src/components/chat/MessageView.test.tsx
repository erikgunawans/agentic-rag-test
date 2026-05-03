/**
 * Phase 19 / ASK-02 / D-27 — Vitest tests for MessageView question-bubble variant.
 *
 * 7 tests covering:
 *   1. Normal assistant bubble when message has no tool_calls
 *   2. Normal assistant bubble when ask_user tool_call has matching tool_result
 *   3. Question-bubble rendered when ask_user tool_call has no matching tool_result
 *   4. Question-bubble has border-l-[3px] border-primary visual classes
 *   5. Question-bubble has role=note and aria-label (a11y)
 *   6. MessageCircleQuestion icon present in question-bubble
 *   7. Assistant content rendered before question-bubble in DOM order
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { I18nProvider } from '@/i18n/I18nContext'
import { MessageView } from './MessageView'
import type { Message, ToolResultEvent } from '@/lib/database.types'

// Mock chat sub-components to keep tests focused on MessageView logic
vi.mock('./StreamingMessage', () => ({
  StreamingMessage: ({ content }: { content: string }) => <span>{content}</span>,
}))
vi.mock('./ThinkingIndicator', () => ({
  ThinkingIndicator: () => <span data-testid="thinking" />,
}))
vi.mock('./ToolCallCard', () => ({
  ToolCallCard: () => null,
  ToolCallList: () => null,
}))
vi.mock('./AgentBadge', () => ({
  AgentBadge: () => null,
  DeepModeBadge: () => null,
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMsg(overrides: Partial<Message> = {}): Message {
  return {
    id: 'msg-1',
    thread_id: 'thread-1',
    user_id: 'user-1',
    role: 'assistant',
    content: 'Here is my analysis.',
    created_at: new Date().toISOString(),
    parent_message_id: null,
    ...overrides,
  }
}

function renderView(
  messages: Message[],
  toolResults: ToolResultEvent[] = [],
) {
  localStorage.setItem('locale', 'en')
  return render(
    <I18nProvider>
      <MessageView
        messages={messages}
        allMessages={messages}
        streamingContent=""
        isStreaming={false}
        toolResults={toolResults}
      />
    </I18nProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.setItem('locale', 'en')
  // jsdom does not implement scrollIntoView — stub it to avoid TypeError in MessageView's useEffect
  window.HTMLElement.prototype.scrollIntoView = vi.fn()
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('MessageView — question-bubble variant', () => {
  it('renders normal assistant bubble when message has no tool_calls', () => {
    const msg = makeMsg({ tool_calls: null })
    renderView([msg])
    expect(screen.getByText('Here is my analysis.')).toBeInTheDocument()
    // No question-bubble
    expect(screen.queryByRole('note')).toBeNull()
  })

  it('renders normal bubble when ask_user tool_call has matching tool_result', () => {
    const msg = makeMsg({
      tool_calls: {
        calls: [
          {
            tool: 'ask_user',
            tool_call_id: 'call-X',
            input: { question: 'What is your deadline?' },
            output: {},
          },
        ],
      },
    })
    // Matching tool_result: tool === 'ask_user' (same as in isAskUserQuestion detection)
    const toolResults: ToolResultEvent[] = [
      { type: 'tool_result', tool: 'ask_user', tool_call_id: 'call-X' },
    ]
    renderView([msg], toolResults)
    // No question-bubble — pair complete
    expect(screen.queryByRole('note')).toBeNull()
  })

  it('renders question-bubble when ask_user tool_call has no matching tool_result', () => {
    const msg = makeMsg({
      tool_calls: {
        calls: [
          {
            tool: 'ask_user',
            tool_call_id: 'call-Y',
            input: { question: 'What is your preferred jurisdiction?' },
            output: {},
          },
        ],
      },
    })
    renderView([msg], [])  // No tool results
    // Question-bubble rendered with question text
    expect(screen.getByRole('note')).toBeInTheDocument()
    expect(screen.getByText('What is your preferred jurisdiction?')).toBeInTheDocument()
  })

  it('question-bubble has border-l-[3px] border-primary visual classes', () => {
    const msg = makeMsg({
      tool_calls: {
        calls: [
          {
            tool: 'ask_user',
            tool_call_id: 'call-Z',
            input: { question: 'Which clause should apply?' },
            output: {},
          },
        ],
      },
    })
    const { container } = renderView([msg], [])
    const bubble = container.querySelector('[role="note"]')
    expect(bubble).not.toBeNull()
    const cls = bubble?.getAttribute('class') ?? ''
    expect(cls).toContain('border-l-[3px]')
    expect(cls).toContain('border-primary')
  })

  it('question-bubble has role=note and aria-label', () => {
    const msg = makeMsg({
      tool_calls: {
        calls: [
          {
            tool: 'ask_user',
            tool_call_id: 'call-A',
            input: { question: 'Confirm the party names?' },
            output: {},
          },
        ],
      },
    })
    renderView([msg], [])
    const bubble = screen.getByRole('note')
    expect(bubble).toBeInTheDocument()
    expect(bubble.getAttribute('aria-label')).toBeTruthy()
    // English: "Question from agent"
    expect(bubble.getAttribute('aria-label')).toBe('Question from agent')
  })

  it('MessageCircleQuestion icon present in question-bubble', () => {
    const msg = makeMsg({
      tool_calls: {
        calls: [
          {
            tool: 'ask_user',
            tool_call_id: 'call-B',
            input: { question: 'Is governing law Indonesian?' },
            output: {},
          },
        ],
      },
    })
    const { container } = renderView([msg], [])
    const bubble = container.querySelector('[role="note"]')
    // MessageCircleQuestion renders as lucide-message-circle-question-mark
    const icon = bubble?.querySelector('svg.lucide-message-circle-question-mark')
    expect(icon).not.toBeNull()
  })

  it('assistant content rendered before question-bubble in DOM order', () => {
    const msg = makeMsg({
      content: 'Some intro text',
      tool_calls: {
        calls: [
          {
            tool: 'ask_user',
            tool_call_id: 'call-C',
            input: { question: 'Which court has jurisdiction?' },
            output: {},
          },
        ],
      },
    })
    renderView([msg], [])
    const contentEl = screen.getByText('Some intro text')
    const bubbleEl = screen.getByRole('note')
    // Content (inside normal message div) should come BEFORE question-bubble in DOM
    const order = contentEl.compareDocumentPosition(bubbleEl)
    expect(order & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})
