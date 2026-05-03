/**
 * Phase 19 / STATUS-01 / D-26 — Vitest tests for AgentStatusChip.
 *
 * 6 tests covering:
 *   1. Null state — sr-only aria-live container only
 *   2. Working state — pulsing dot + "Agent working" label (EN)
 *   2b. Working state — "Agen sedang bekerja" label (ID)
 *   3. waiting_for_user — MessageCircleQuestion icon + label
 *   4. complete — auto-fades after 3000ms (fake timers)
 *   5. error — persists (no auto-fade)
 *   6. ARIA attributes present in both visible and null states
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { I18nProvider } from '@/i18n/I18nContext'
import { AgentStatusChip } from './AgentStatusChip'
import type { AgentStatus } from '@/hooks/useChatState'

// Mock useChatContext so tests control agentStatus + setAgentStatus independently.
vi.mock('@/contexts/ChatContext', () => ({
  useChatContext: vi.fn(),
}))

import { useChatContext } from '@/contexts/ChatContext'

const mockUseChatContext = useChatContext as ReturnType<typeof vi.fn>

function makeContext(agentStatus: AgentStatus, setAgentStatus = vi.fn()) {
  mockUseChatContext.mockReturnValue({ agentStatus, setAgentStatus })
  return setAgentStatus
}

function renderChip(agentStatus: AgentStatus, setAgentStatus = vi.fn(), locale: 'en' | 'id' = 'en') {
  localStorage.setItem('locale', locale)
  makeContext(agentStatus, setAgentStatus)
  return render(
    <I18nProvider>
      <AgentStatusChip />
    </I18nProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()
  localStorage.setItem('locale', 'en')
})

afterEach(() => {
  vi.useRealTimers()
})

describe('AgentStatusChip', () => {
  it('renders nothing visible when agentStatus is null', () => {
    const { container } = renderChip(null)
    // Only the sr-only aria-live container should be in the DOM
    const statusEl = container.querySelector('[role="status"]')
    expect(statusEl).not.toBeNull()
    expect(statusEl?.className).toContain('sr-only')
    // No visible chip text
    expect(screen.queryByText('Agent working')).toBeNull()
    expect(screen.queryByText('Complete')).toBeNull()
  })

  it('renders pulsing dot and "Agent working" on working state (EN)', () => {
    const { container } = renderChip('working')
    // Pulsing dot: span with bg-primary + animate-pulse
    const dot = container.querySelector('.bg-primary.animate-pulse')
    expect(dot).not.toBeNull()
    // Label text
    expect(screen.getByText('Agent working')).toBeInTheDocument()
  })

  it('renders "Agen sedang bekerja" on working state (ID)', () => {
    renderChip('working', vi.fn(), 'id')
    expect(screen.getByText('Agen sedang bekerja')).toBeInTheDocument()
  })

  it('renders MessageCircleQuestion icon on waiting_for_user', () => {
    const { container } = renderChip('waiting_for_user')
    // lucide-react renders SVGs with class "lucide lucide-message-circle-question-mark"
    const iconSvg = container.querySelector('svg.lucide-message-circle-question-mark')
    expect(iconSvg).not.toBeNull()
    expect(screen.getByText('Agent waiting for your reply')).toBeInTheDocument()
  })

  it('renders CheckCircle2 and auto-fades after 3000ms on complete', () => {
    const setAgentStatus = vi.fn()
    const { container } = renderChip('complete', setAgentStatus)
    // CheckCircle2 (lucide-react class: lucide-circle-check)
    const checkIcon = container.querySelector('svg.lucide-circle-check')
    expect(checkIcon).not.toBeNull()
    // Before timer fires — setAgentStatus not yet called
    expect(setAgentStatus).not.toHaveBeenCalled()
    // Advance fake timers by 3000ms
    vi.advanceTimersByTime(3000)
    // Auto-fade fires
    expect(setAgentStatus).toHaveBeenCalledWith(null)
  })

  it('renders AlertCircle on error and persists (no auto-fade)', () => {
    const setAgentStatus = vi.fn()
    const { container } = renderChip('error', setAgentStatus)
    // AlertCircle (lucide-react class: lucide-circle-alert)
    const alertIcon = container.querySelector('svg.lucide-circle-alert')
    expect(alertIcon).not.toBeNull()
    // Advance 5000ms — no auto-fade for error
    vi.advanceTimersByTime(5000)
    expect(setAgentStatus).not.toHaveBeenCalled()
    // Chip still rendered (not null state)
    expect(container.querySelector('[role="status"]:not(.sr-only)')).not.toBeNull()
  })

  it('has role=status and aria-live=polite on container in both null and visible states', () => {
    // Null state
    const { container: nullContainer, unmount } = renderChip(null)
    const nullStatus = nullContainer.querySelector('[role="status"]')
    expect(nullStatus).not.toBeNull()
    expect(nullStatus?.getAttribute('aria-live')).toBe('polite')
    unmount()

    // Visible state
    const { container: visibleContainer } = renderChip('working')
    const visibleStatus = visibleContainer.querySelector('[role="status"]')
    expect(visibleStatus).not.toBeNull()
    expect(visibleStatus?.getAttribute('aria-live')).toBe('polite')
  })
})
