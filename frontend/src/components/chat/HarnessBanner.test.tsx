/**
 * Phase 20 / Plan 20-09 / HARN-09 / UI-SPEC L319
 * HarnessBanner co-located Vitest 3.2 tests.
 *
 * 6 cases per UI-SPEC L319:
 *   (a) renders when harnessRun.status active — assert data-testid="harness-banner" present
 *   (b) hidden (sr-only stub) when harnessRun=null — assert data-testid="harness-banner-empty" present, "harness-banner" absent
 *   (c) phase fraction copy interpolates correctly
 *   (d) Cancel button visible when active; absent in terminal state
 *   (e) Cancel button click → sets cancelOpen (dialog trigger)
 *   (f) ID + EN locale renders with correct translation
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { I18nProvider } from '@/i18n/I18nContext'
import type { HarnessRunSlice } from '@/hooks/useChatState'

// ---------------------------------------------------------------------------
// Mock useChatContext so HarnessBanner doesn't need a real ChatProvider
// ---------------------------------------------------------------------------
const mockContext = {
  harnessRun: null as HarnessRunSlice,
  activeThreadId: 'thread-banner-test' as string | null,
}

vi.mock('@/contexts/ChatContext', () => ({
  useChatContext: () => mockContext,
}))

// Mock apiFetch for cancel calls
vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn().mockResolvedValue(new Response('{}', { status: 200 })),
}))

// Import AFTER mocks are set up
import { HarnessBanner } from './HarnessBanner'

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------
function renderBanner(harnessRun: HarnessRunSlice = null, locale: 'id' | 'en' = 'id') {
  mockContext.harnessRun = harnessRun
  // I18nProvider reads locale from localStorage; set it first
  localStorage.setItem('locale', locale)
  return render(
    <I18nProvider>
      <HarnessBanner />
    </I18nProvider>,
  )
}

const RUNNING_RUN: NonNullable<HarnessRunSlice> = {
  id: 'run-1',
  harnessType: 'smoke-echo',
  status: 'running',
  currentPhase: 2,
  phaseCount: 8,
  phaseName: 'Gather Context',
  errorDetail: null,
}

const COMPLETED_RUN: NonNullable<HarnessRunSlice> = {
  ...RUNNING_RUN,
  status: 'completed',
}

const CANCELLED_RUN: NonNullable<HarnessRunSlice> = {
  ...RUNNING_RUN,
  status: 'cancelled',
  errorDetail: null,
}

const FAILED_RUN: NonNullable<HarnessRunSlice> = {
  ...RUNNING_RUN,
  status: 'failed',
  errorDetail: 'LLM timeout',
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('HarnessBanner (Phase 20 / Plan 20-09)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.setItem('locale', 'id')
  })

  // (a) Renders when harnessRun.status active
  it('(a) renders data-testid="harness-banner" when status is active', () => {
    renderBanner(RUNNING_RUN)
    expect(screen.getByTestId('harness-banner')).toBeInTheDocument()
  })

  // (b) Hidden (sr-only stub) when harnessRun=null
  it('(b) renders sr-only stub when harnessRun=null; no visible banner', () => {
    renderBanner(null)
    expect(screen.getByTestId('harness-banner-empty')).toBeInTheDocument()
    expect(screen.queryByTestId('harness-banner')).not.toBeInTheDocument()
  })

  // (c) Phase fraction interpolation — ID locale
  it('(c) phase fraction interpolates correctly in ID locale', () => {
    renderBanner(RUNNING_RUN, 'id')
    // ID: "Smoke Echo berjalan — fase 3 dari 8 (Gather Context)"
    // currentPhase=2 → displayed as n=currentPhase+1=3
    const banner = screen.getByTestId('harness-banner')
    expect(banner.textContent).toContain('3')
    expect(banner.textContent).toContain('8')
  })

  // (d) Cancel button visible when active; hidden in terminal state
  it('(d) Cancel button visible when active; hidden when completed', () => {
    renderBanner(RUNNING_RUN)
    expect(screen.getByTestId('harness-banner-cancel')).toBeInTheDocument()
  })

  it('(d) Cancel button absent in terminal (completed) state', () => {
    renderBanner(COMPLETED_RUN)
    expect(screen.queryByTestId('harness-banner-cancel')).not.toBeInTheDocument()
  })

  // (e) Cancel button click opens Dialog (sets cancelOpen)
  it('(e) Cancel button click triggers dialog visibility', () => {
    renderBanner(RUNNING_RUN)
    const cancelBtn = screen.getByTestId('harness-banner-cancel')
    fireEvent.click(cancelBtn)
    // After click, dialog confirm button should be visible in the DOM
    expect(screen.getByTestId('harness-banner-cancel-confirm')).toBeInTheDocument()
  })

  // (f) ID + EN locale renders with correct translation
  it('(f) EN locale shows English copy', () => {
    renderBanner(RUNNING_RUN, 'en')
    const banner = screen.getByTestId('harness-banner')
    // EN: "Smoke Echo running — phase 3 of 8 (Gather Context)"
    expect(banner.textContent).toContain('running')
  })

  it('(f) cancelled state shows correct terminal copy', () => {
    renderBanner(CANCELLED_RUN, 'id')
    const banner = screen.getByTestId('harness-banner')
    // ID: "Smoke Echo dibatalkan"
    expect(banner.textContent).toContain('dibatalkan')
  })

  it('(f) failed state shows correct terminal copy with detail', () => {
    renderBanner(FAILED_RUN, 'id')
    const banner = screen.getByTestId('harness-banner')
    // ID: "Smoke Echo gagal — LLM timeout"
    expect(banner.textContent).toContain('gagal')
    expect(banner.textContent).toContain('LLM timeout')
  })
})
