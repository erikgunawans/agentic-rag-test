/**
 * Phase 21 / Plan 21-05 / HIL-02
 * Vitest tests for HarnessBanner — paused state title rendering.
 *
 * RED phase: HarnessBanner does not yet branch on harnessRun.status === 'paused'.
 *
 * Test coverage:
 *   1. paused state ID-default → "Menunggu respons Anda — Smoke Echo"
 *   2. paused state EN locale → "Awaiting your response — Smoke Echo"
 *   3. paused state still shows the cancel button (paused IS in ACTIVE_STATUSES)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { I18nProvider } from '@/i18n/I18nContext'
import { HarnessBanner } from '../HarnessBanner'
import type {
  HarnessRunSlice,
  BatchProgressSlice,
} from '@/hooks/useChatState'

// ---------------------------------------------------------------------------
// Mock useChatContext — HarnessBanner reads harnessRun + batchProgress + activeThreadId
// ---------------------------------------------------------------------------
const mockChatContext = {
  harnessRun: null as HarnessRunSlice,
  batchProgress: null as BatchProgressSlice,
  activeThreadId: 'thread-test-123' as string | null,
}

vi.mock('@/contexts/ChatContext', () => ({
  useChatContext: () => mockChatContext,
}))

// Mock apiFetch (HarnessBanner uses it for cancel only; never invoked in these tests)
vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
}))

const HARNESS_RUN_PAUSED: HarnessRunSlice = {
  id: 'run-paused',
  harnessType: 'smoke-echo',
  status: 'paused',
  currentPhase: 2,
  phaseCount: 4,
  phaseName: 'ask-label',
  errorDetail: null,
}

function renderBanner() {
  return render(
    <I18nProvider>
      <HarnessBanner />
    </I18nProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.setItem('locale', 'id')
  mockChatContext.harnessRun = null
  mockChatContext.batchProgress = null
  mockChatContext.activeThreadId = 'thread-test-123'
})

describe('HarnessBanner — paused state (Phase 21 / Plan 21-05 / HIL-02)', () => {
  it('1: paused status renders ID-default title "Menunggu respons Anda — Smoke Echo"', () => {
    mockChatContext.harnessRun = HARNESS_RUN_PAUSED
    localStorage.setItem('locale', 'id')

    renderBanner()

    const banner = screen.getByTestId('harness-banner')
    expect(banner.textContent ?? '').toContain('Menunggu respons Anda — Smoke Echo')
  })

  it('2: paused status renders EN title "Awaiting your response — Smoke Echo"', () => {
    mockChatContext.harnessRun = HARNESS_RUN_PAUSED
    localStorage.setItem('locale', 'en')

    renderBanner()

    const banner = screen.getByTestId('harness-banner')
    expect(banner.textContent ?? '').toContain('Awaiting your response — Smoke Echo')
  })

  it('3: paused state keeps the cancel button visible (paused IS in ACTIVE_STATUSES)', () => {
    mockChatContext.harnessRun = HARNESS_RUN_PAUSED

    renderBanner()

    // Cancel button must still be in the DOM — paused is an active state
    expect(screen.queryByTestId('harness-banner-cancel')).not.toBeNull()
  })
})
