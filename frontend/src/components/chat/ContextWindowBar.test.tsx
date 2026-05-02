import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ContextWindowBar } from './ContextWindowBar'

describe('ContextWindowBar (Phase 12 / CTX-04..06)', () => {
  it('renders nothing when usage is null', () => {
    const { container } = render(
      <ContextWindowBar usage={null} contextWindow={128000} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when contextWindow is null', () => {
    const { container } = render(
      <ContextWindowBar
        usage={{ prompt: 100, completion: 50, total: 150 }}
        contextWindow={null}
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when total is null', () => {
    const { container } = render(
      <ContextWindowBar
        usage={{ prompt: 100, completion: null, total: null }}
        contextWindow={128000}
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('formats label as Xk / Yk (Z%) for thousands', () => {
    render(
      <ContextWindowBar
        usage={{ prompt: 45000, completion: 0, total: 45000 }}
        contextWindow={128000}
      />
    )
    expect(screen.getByText(/45k\s*\/\s*128k\s*\(35%\)/)).toBeInTheDocument()
  })

  it('formats label with raw integer for sub-1k numerator', () => {
    render(
      <ContextWindowBar
        usage={{ prompt: 523, completion: 0, total: 523 }}
        contextWindow={128000}
      />
    )
    expect(screen.getByText(/523\s*\/\s*128k\s*\(0%\)/)).toBeInTheDocument()
  })

  it('uses emerald-500 fill at 35%', () => {
    const { container } = render(
      <ContextWindowBar
        usage={{ prompt: 0, completion: 0, total: 44800 }}
        contextWindow={128000}
      />
    )
    const fill = container.querySelector('[data-testid="ctx-fill"]')
    expect(fill?.className).toContain('bg-emerald-500')
  })

  it('uses amber-500 fill at 65%', () => {
    const { container } = render(
      <ContextWindowBar
        usage={{ prompt: 0, completion: 0, total: 83200 }}
        contextWindow={128000}
      />
    )
    const fill = container.querySelector('[data-testid="ctx-fill"]')
    expect(fill?.className).toContain('bg-amber-500')
  })

  it('uses amber-500 fill at exactly 60%', () => {
    const { container } = render(
      <ContextWindowBar
        usage={{ prompt: 0, completion: 0, total: 76800 }}
        contextWindow={128000}
      />
    )
    const fill = container.querySelector('[data-testid="ctx-fill"]')
    expect(fill?.className).toContain('bg-amber-500')
    expect(fill?.className).not.toContain('bg-emerald-500')
  })

  it('uses rose-500 fill at 90%', () => {
    const { container } = render(
      <ContextWindowBar
        usage={{ prompt: 0, completion: 0, total: 115200 }}
        contextWindow={128000}
      />
    )
    const fill = container.querySelector('[data-testid="ctx-fill"]')
    expect(fill?.className).toContain('bg-rose-500')
  })

  it('uses rose-500 fill at exactly 80%', () => {
    const { container } = render(
      <ContextWindowBar
        usage={{ prompt: 0, completion: 0, total: 102400 }}
        contextWindow={128000}
      />
    )
    const fill = container.querySelector('[data-testid="ctx-fill"]')
    expect(fill?.className).toContain('bg-rose-500')
    expect(fill?.className).not.toContain('bg-amber-500')
  })

  it('width style scales with percentage', () => {
    const { container } = render(
      <ContextWindowBar
        usage={{ prompt: 0, completion: 0, total: 44800 }}
        contextWindow={128000}
      />
    )
    const fill = container.querySelector(
      '[data-testid="ctx-fill"]'
    ) as HTMLElement
    expect(fill.style.width).toBe('35%')
  })

  it('bar height uses h-1 (4px)', () => {
    const { container } = render(
      <ContextWindowBar
        usage={{ prompt: 0, completion: 0, total: 44800 }}
        contextWindow={128000}
      />
    )
    const track = container.querySelector('[data-testid="ctx-track"]')
    const fill = container.querySelector('[data-testid="ctx-fill"]')
    expect(track?.className).toContain('h-1')
    expect(fill?.className).toContain('h-1')
  })

  it('track has zinc-neutral background', () => {
    const { container } = render(
      <ContextWindowBar
        usage={{ prompt: 0, completion: 0, total: 44800 }}
        contextWindow={128000}
      />
    )
    const track = container.querySelector(
      '[data-testid="ctx-track"]'
    ) as HTMLElement
    expect(track.className).toMatch(/bg-zinc-200/)
    expect(track.className).toMatch(/dark:bg-zinc-800/)
  })

  it('label uses tabular-nums for stable digit width', () => {
    const { container } = render(
      <ContextWindowBar
        usage={{ prompt: 0, completion: 0, total: 44800 }}
        contextWindow={128000}
      />
    )
    const label = container.querySelector(
      '[data-testid="ctx-label"]'
    ) as HTMLElement
    expect(label.className).toMatch(/tabular-nums/)
  })

  it('clamps fill width at 100% when total exceeds contextWindow', () => {
    const { container } = render(
      <ContextWindowBar
        usage={{ prompt: 0, completion: 0, total: 150000 }}
        contextWindow={128000}
      />
    )
    const fill = container.querySelector(
      '[data-testid="ctx-fill"]'
    ) as HTMLElement
    expect(fill.style.width).toBe('100%')
    expect(fill.className).toContain('bg-rose-500')
    const label = container.querySelector(
      '[data-testid="ctx-label"]'
    ) as HTMLElement
    expect(label.textContent).toMatch(/150k\s*\/\s*128k\s*\(117%\)/)
  })
})
