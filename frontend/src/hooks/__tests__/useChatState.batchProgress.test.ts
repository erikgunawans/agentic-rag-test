/**
 * Phase 21 / Plan 21-05 / D-09 / BATCH-04 / BATCH-06
 * Unit tests for the batchProgress slice in useChatState.
 *
 * RED phase: batchProgress slice + reducer arms not yet wired.
 * Tests cover:
 *   1. harness_batch_item_start seeds total
 *   2. harness_batch_item_complete increments completed
 *   3. harness_phase_complete clears batchProgress
 *   4. Thread switch resets batchProgress
 *   5. Resume-replay preserves existing completed counter (WARNING-6 regression)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useChatState } from '../useChatState'

// ---------------------------------------------------------------------------
// Mock heavy dependencies that block hook rendering (mirror useChatState.test.ts)
// ---------------------------------------------------------------------------
vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: 'test-token' } } }),
    },
    from: vi.fn().mockReturnValue({
      select: vi.fn().mockReturnValue({
        eq: vi.fn().mockReturnValue({
          order: vi.fn().mockResolvedValue({ data: [], error: null }),
        }),
      }),
    }),
  },
}))

vi.mock('@/lib/api', () => ({
  apiFetch: vi.fn(),
  fetchThreadTodos: vi.fn().mockResolvedValue({ todos: [] }),
}))

import { apiFetch } from '@/lib/api'
const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>

// ---------------------------------------------------------------------------
// Helper: build an SSE ReadableStream from a list of events
// ---------------------------------------------------------------------------
function buildSSEStream(events: Array<Record<string, unknown>>): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
      }
      controller.close()
    },
  })
}

function mockStreamResponse(events: Array<Record<string, unknown>>) {
  const stream = buildSSEStream(events)
  const mockResponse = new Response(stream, { status: 200 })
  mockApiFetch.mockResolvedValueOnce(mockResponse)
}

// Default apiFetch mock for non-stream calls (threads, files, todos, harness/active)
function setupDefaultApiFetch() {
  mockApiFetch.mockImplementation((path: string) => {
    if (typeof path === 'string' && path.includes('/harness/active')) {
      return Promise.resolve(new Response(JSON.stringify({ harnessRun: null }), { status: 200 }))
    }
    if (
      typeof path === 'string' &&
      (path.includes('/files') || path.includes('/todos') || path.includes('/threads'))
    ) {
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
  })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
describe('useChatState — batchProgress slice (Phase 21 / Plan 21-05)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupDefaultApiFetch()
  })

  it('1: harness_batch_item_start seeds total (and completed=0 from initial null)', async () => {
    const { result } = renderHook(() => useChatState())

    await act(async () => {
      await result.current.handleSelectThread('thread-batch-1')
    })

    // Stream a single batch_item_start event
    mockStreamResponse([
      { type: 'harness_batch_item_start', harness_run_id: 'run-1', phase_index: 3, phase_name: 'batch-process', item_index: 0, items_total: 5, task_id: 't-0', batch_index: 0 },
      { type: 'done', done: true },
    ])

    await act(async () => {
      await result.current.handleSendMessage('go')
    })

    expect(result.current.batchProgress).not.toBeNull()
    expect(result.current.batchProgress?.total).toBe(5)
    expect(result.current.batchProgress?.completed).toBe(0)
  })

  it('2: harness_batch_item_complete increments completed', async () => {
    const { result } = renderHook(() => useChatState())

    await act(async () => {
      await result.current.handleSelectThread('thread-batch-2')
    })

    mockStreamResponse([
      { type: 'harness_batch_item_start', harness_run_id: 'run-1', phase_index: 3, phase_name: 'batch-process', item_index: 0, items_total: 5, task_id: 't-0', batch_index: 0 },
      { type: 'harness_batch_item_complete', harness_run_id: 'run-1', phase_index: 3, phase_name: 'batch-process', item_index: 0, items_total: 5, task_id: 't-0', status: 'ok', batch_index: 0 },
      { type: 'done', done: true },
    ])

    await act(async () => {
      await result.current.handleSendMessage('go')
    })

    expect(result.current.batchProgress).not.toBeNull()
    expect(result.current.batchProgress?.total).toBe(5)
    expect(result.current.batchProgress?.completed).toBe(1)
  })

  it('3: harness_phase_complete clears batchProgress AND advances harnessRun.currentPhase (no regression)', async () => {
    const { result } = renderHook(() => useChatState())

    await act(async () => {
      await result.current.handleSelectThread('thread-batch-3')
    })

    // Pre-seed harnessRun so we can verify currentPhase advances
    await act(async () => {
      result.current.setHarnessRun({
        id: 'run-1',
        harnessType: 'smoke-echo',
        status: 'running',
        currentPhase: 3,
        phaseCount: 4,
        phaseName: 'batch-process',
        errorDetail: null,
      })
    })

    mockStreamResponse([
      { type: 'harness_batch_item_start', harness_run_id: 'run-1', phase_index: 3, phase_name: 'batch-process', item_index: 0, items_total: 3, task_id: 't-0', batch_index: 0 },
      { type: 'harness_batch_item_complete', harness_run_id: 'run-1', phase_index: 3, phase_name: 'batch-process', item_index: 0, items_total: 3, task_id: 't-0', status: 'ok', batch_index: 0 },
      { type: 'harness_phase_complete', harness_run_id: 'run-1', phase_index: 3, phase_name: 'batch-process' },
      { type: 'done', done: true },
    ])

    await act(async () => {
      await result.current.handleSendMessage('go')
    })

    // batchProgress cleared on phase boundary
    expect(result.current.batchProgress).toBeNull()
    // Existing harness_phase_complete behavior preserved — currentPhase bumped from 3 → 4
    expect(result.current.harnessRun?.currentPhase).toBe(4)
  })

  it('4: thread switch resets batchProgress to null', async () => {
    const { result } = renderHook(() => useChatState())

    await act(async () => {
      await result.current.handleSelectThread('thread-batch-4a')
    })

    // Stream events to seed batchProgress
    mockStreamResponse([
      { type: 'harness_batch_item_start', harness_run_id: 'run-1', phase_index: 3, phase_name: 'batch-process', item_index: 0, items_total: 4, task_id: 't-0', batch_index: 0 },
      { type: 'harness_batch_item_complete', harness_run_id: 'run-1', phase_index: 3, phase_name: 'batch-process', item_index: 0, items_total: 4, task_id: 't-0', status: 'ok', batch_index: 0 },
      { type: 'done', done: true },
    ])

    await act(async () => {
      await result.current.handleSendMessage('go')
    })

    expect(result.current.batchProgress).not.toBeNull()

    // Switch to a different thread → batchProgress should reset to null
    await act(async () => {
      await result.current.handleSelectThread('thread-batch-4b')
    })

    await waitFor(() => {
      expect(result.current.batchProgress).toBeNull()
    })
  })

  it('5: resume-replay preserves existing completed counter (WARNING-6 regression)', async () => {
    const { result } = renderHook(() => useChatState())

    await act(async () => {
      await result.current.handleSelectThread('thread-batch-5')
    })

    // Sequence: 1 start (total=15) → 10 complete events → 1 SECOND start (mimics resume replay)
    const events: Array<Record<string, unknown>> = [
      { type: 'harness_batch_item_start', harness_run_id: 'run-1', phase_index: 3, phase_name: 'batch-process', item_index: 0, items_total: 15, task_id: 't-0', batch_index: 0 },
    ]
    for (let i = 0; i < 10; i++) {
      events.push({
        type: 'harness_batch_item_complete',
        harness_run_id: 'run-1',
        phase_index: 3,
        phase_name: 'batch-process',
        item_index: i,
        items_total: 15,
        task_id: `t-${i}`,
        status: 'ok',
        batch_index: 0,
      })
    }
    // Resume replay: a second start event after 10 completions
    events.push({
      type: 'harness_batch_item_start',
      harness_run_id: 'run-1',
      phase_index: 3,
      phase_name: 'batch-process',
      item_index: 10,
      items_total: 15,
      task_id: 't-10',
      batch_index: 2,
    })
    events.push({ type: 'done', done: true })

    mockStreamResponse(events)

    await act(async () => {
      await result.current.handleSendMessage('go')
    })

    // After the second start, completed must be 10 (NOT reset to 0); total unchanged at 15
    expect(result.current.batchProgress).not.toBeNull()
    expect(result.current.batchProgress?.completed).toBe(10)
    expect(result.current.batchProgress?.total).toBe(15)
  })
})
