import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import {
  usePublicSettings,
  _resetPublicSettingsCacheForTests,
} from './usePublicSettings'

describe('usePublicSettings (Phase 12 / CTX-03)', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    _resetPublicSettingsCacheForTests()
    fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ context_window: 128000 }), {
        status: 200,
      }) as Response
    )
  })

  afterEach(() => {
    fetchSpy.mockRestore()
  })

  it('fetches once on first mount', async () => {
    const { result } = renderHook(() => usePublicSettings())
    await waitFor(() => expect(result.current.contextWindow).toBe(128000))
    expect(fetchSpy).toHaveBeenCalledTimes(1)
    const calledUrl = fetchSpy.mock.calls[0][0] as string
    expect(calledUrl).toMatch(/\/settings\/public$/)
  })

  it('shares fetch across multiple mounts', async () => {
    const { result: r1 } = renderHook(() => usePublicSettings())
    const { result: r2 } = renderHook(() => usePublicSettings())
    await waitFor(() => {
      expect(r1.current.contextWindow).toBe(128000)
      expect(r2.current.contextWindow).toBe(128000)
    })
    expect(fetchSpy).toHaveBeenCalledTimes(1)
  })

  it('returns null while pending', () => {
    fetchSpy.mockImplementationOnce(() => new Promise(() => {})) // never resolves
    const { result } = renderHook(() => usePublicSettings())
    expect(result.current.contextWindow).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('handles fetch failure gracefully', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('network down'))
    const { result } = renderHook(() => usePublicSettings())
    await waitFor(() => expect(result.current.error).not.toBeNull())
    expect(result.current.contextWindow).toBeNull()
    expect(result.current.error?.message).toBe('network down')
  })

  it('handles non-200 status', async () => {
    fetchSpy.mockResolvedValueOnce(
      new Response('Internal Server Error', { status: 500 }) as Response
    )
    const { result } = renderHook(() => usePublicSettings())
    await waitFor(() => expect(result.current.error).not.toBeNull())
    expect(result.current.contextWindow).toBeNull()
    expect(result.current.error?.message).toContain('500')
  })

  it('does not inject Bearer JWT', async () => {
    renderHook(() => usePublicSettings())
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled())
    const init = fetchSpy.mock.calls[0][1] as RequestInit | undefined
    const headers = (init?.headers ?? {}) as Record<string, string>
    expect(
      Object.keys(headers).map((k) => k.toLowerCase())
    ).not.toContain('authorization')
  })
})
