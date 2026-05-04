/**
 * Phase 21 / Plan 21-05 / D-09 / BATCH-04 / BATCH-06
 * Vitest tests for HarnessBanner — batchProgress suffix rendering.
 *
 * RED phase: HarnessBanner does not yet read batchProgress from context.
 *
 * Test coverage:
 *   1. null batchProgress → no suffix appended (banner shows base running text only)
 *   2. batchProgress with completed/total → ID-default text "Menganalisis klausula 3/15"
 *   3. batchProgress + EN locale → text "Analyzing clause 3/15"
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

const HARNESS_RUN_RUNNING: HarnessRunSlice = {
  id: 'run-batch',
  harnessType: 'smoke-echo',
  status: 'running',
  currentPhase: 3,
  phaseCount: 4,
  phaseName: 'batch-process',
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
  // Default: ID locale (default in I18nProvider via getInitialLocale fallback to 'id')
  localStorage.setItem('locale', 'id')
  mockChatContext.harnessRun = null
  mockChatContext.batchProgress = null
  mockChatContext.activeThreadId = 'thread-test-123'
})

describe('HarnessBanner — batchProgress suffix (Phase 21 / Plan 21-05)', () => {
  it('1: null batchProgress → no suffix appended (no "/" or "Menganalisis"/"Analyzing")', () => {
    mockChatContext.harnessRun = HARNESS_RUN_RUNNING
    mockChatContext.batchProgress = null

    renderBanner()

    const banner = screen.getByTestId('harness-banner')
    const text = banner.textContent ?? ''
    // No batch progress fragment
    expect(text).not.toMatch(/Menganalisis klausula/)
    expect(text).not.toMatch(/Analyzing clause/)
  })

  it('2: batchProgress {completed:3,total:15} renders ID-default suffix', () => {
    mockChatContext.harnessRun = HARNESS_RUN_RUNNING
    mockChatContext.batchProgress = { completed: 3, total: 15 }
    localStorage.setItem('locale', 'id')

    renderBanner()

    const banner = screen.getByTestId('harness-banner')
    expect(banner.textContent ?? '').toContain('Menganalisis klausula 3/15')
  })

  it('3: batchProgress {completed:3,total:15} renders EN suffix when locale=en', () => {
    mockChatContext.harnessRun = HARNESS_RUN_RUNNING
    mockChatContext.batchProgress = { completed: 3, total: 15 }
    localStorage.setItem('locale', 'en')

    renderBanner()

    const banner = screen.getByTestId('harness-banner')
    expect(banner.textContent ?? '').toContain('Analyzing clause 3/15')
  })
})
