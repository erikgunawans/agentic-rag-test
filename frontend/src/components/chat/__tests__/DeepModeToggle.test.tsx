/**
 * Phase 17 / DEEP-01 / DEEP-03 — Vitest tests for Deep Mode toggle
 *
 * Tests assert:
 * - Toggle is hidden when deep_mode_enabled=false (D-16 dark-launch invariant)
 * - Toggle visible when deep_mode_enabled=true
 * - Toggle starts off (aria-pressed="false")
 * - Click toggles state
 * - Send action passes deep_mode=true through when toggle is on
 * - Send omits deepMode when toggle is off (DEEP-03 byte-identical payload)
 * - Toggle resets to off after send (per-message semantic, D-24)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { I18nProvider } from '@/i18n/I18nContext'
import { MessageInput } from '../MessageInput'
import { _resetPublicSettingsCacheForTests } from '@/hooks/usePublicSettings'

// Mock supabase to avoid any auth network calls
vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'test-token' } } }),
    },
  },
}))

// Mock useChatContext so MessageInput can render without a real ChatProvider
vi.mock('@/contexts/ChatContext', () => ({
  useChatContext: vi.fn(),
}))
import { useChatContext } from '@/contexts/ChatContext'
const mockUseChatContext = useChatContext as ReturnType<typeof vi.fn>

// Mock usePublicSettings to control deep_mode_enabled flag
vi.mock('@/hooks/usePublicSettings', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/hooks/usePublicSettings')>()
  return {
    ...actual,
    usePublicSettings: vi.fn(),
  }
})
import { usePublicSettings } from '@/hooks/usePublicSettings'
const mockUsePublicSettings = usePublicSettings as ReturnType<typeof vi.fn>

function makeChatContextValue(overrides: Record<string, unknown> = {}) {
  return {
    webSearchEnabled: false,
    setWebSearchEnabled: vi.fn(),
    usage: null,
    ...overrides,
  }
}

function renderMessageInput(onSend = vi.fn()) {
  return {
    onSend,
    ...render(
      <I18nProvider>
        <MessageInput onSend={onSend} disabled={false} />
      </I18nProvider>
    ),
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  _resetPublicSettingsCacheForTests()
  mockUseChatContext.mockReturnValue(makeChatContextValue())
})

describe('Deep Mode Toggle — MessageInput (Phase 17 DEEP-01)', () => {
  it('toggle is hidden when deep_mode_enabled=false', () => {
    mockUsePublicSettings.mockReturnValue({
      contextWindow: 128000,
      deepModeEnabled: false,
      error: null,
    })
    renderMessageInput()
    expect(screen.queryByTestId('deep-mode-toggle')).toBeNull()
  })

  it('toggle is visible when deep_mode_enabled=true', () => {
    mockUsePublicSettings.mockReturnValue({
      contextWindow: 128000,
      deepModeEnabled: true,
      error: null,
    })
    renderMessageInput()
    expect(screen.getByTestId('deep-mode-toggle')).toBeInTheDocument()
  })

  it('toggle starts with aria-pressed=false', () => {
    mockUsePublicSettings.mockReturnValue({
      contextWindow: 128000,
      deepModeEnabled: true,
      error: null,
    })
    renderMessageInput()
    const toggle = screen.getByTestId('deep-mode-toggle')
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
  })

  it('clicking toggle flips aria-pressed to true, then back to false', () => {
    mockUsePublicSettings.mockReturnValue({
      contextWindow: 128000,
      deepModeEnabled: true,
      error: null,
    })
    renderMessageInput()
    const toggle = screen.getByTestId('deep-mode-toggle')
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
  })

  it('send with toggle ON calls onSend with deepMode: true', async () => {
    mockUsePublicSettings.mockReturnValue({
      contextWindow: 128000,
      deepModeEnabled: true,
      error: null,
    })
    const onSend = vi.fn()
    renderMessageInput(onSend)

    // Enable toggle
    const toggle = screen.getByTestId('deep-mode-toggle')
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'true')

    // Type something
    const textarea = screen.getByRole('textbox')
    fireEvent.change(textarea, { target: { value: 'hi' } })

    // Click send button (data-testid for language-agnostic lookup)
    const sendBtn = screen.getByTestId('send-button')
    fireEvent.click(sendBtn)

    await waitFor(() => {
      expect(onSend).toHaveBeenCalled()
      // onSend must be called with (content, { deepMode: true })
      const args = onSend.mock.calls[0]
      expect(args[0]).toBe('hi')
      expect(args[1]).toMatchObject({ deepMode: true })
    })
  })

  it('send with toggle OFF does not include deepMode: true', async () => {
    mockUsePublicSettings.mockReturnValue({
      contextWindow: 128000,
      deepModeEnabled: true,
      error: null,
    })
    const onSend = vi.fn()
    renderMessageInput(onSend)

    // Toggle stays OFF — no click
    const textarea = screen.getByRole('textbox')
    fireEvent.change(textarea, { target: { value: 'hello' } })

    const sendBtn = screen.getByTestId('send-button')
    fireEvent.click(sendBtn)

    await waitFor(() => {
      expect(onSend).toHaveBeenCalled()
      const args = onSend.mock.calls[0]
      // Second arg absent OR does not have deepMode: true
      if (args.length > 1 && args[1] !== undefined) {
        expect(args[1]).not.toHaveProperty('deepMode', true)
      }
    })
  })

  it('toggle resets to aria-pressed=false after send (per-message semantic D-24)', async () => {
    mockUsePublicSettings.mockReturnValue({
      contextWindow: 128000,
      deepModeEnabled: true,
      error: null,
    })
    const onSend = vi.fn()
    renderMessageInput(onSend)

    // Enable toggle
    const toggle = screen.getByTestId('deep-mode-toggle')
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'true')

    // Type and send
    const textarea = screen.getByRole('textbox')
    fireEvent.change(textarea, { target: { value: 'hi' } })
    const sendBtn = screen.getByTestId('send-button')
    fireEvent.click(sendBtn)

    await waitFor(() => {
      expect(toggle).toHaveAttribute('aria-pressed', 'false')
    })
  })
})
