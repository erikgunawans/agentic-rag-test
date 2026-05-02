import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SubAgentPanel } from './SubAgentPanel'


const baseState = {
  mode: 'explorer' as const,
  document_id: null,
  reasoning: '',
  explorer_tool_calls: [],
}


describe('SubAgentPanel', () => {
  it('renders mode badge', () => {
    render(<SubAgentPanel state={{ ...baseState, mode: 'explorer' }} />)
    expect(screen.getByText(/explorer/i)).toBeInTheDocument()
  })

  it('renders document badge when document_id is set', () => {
    render(<SubAgentPanel state={{ ...baseState, document_id: 'doc-123' }} />)
    expect(screen.getByText(/doc-123/)).toBeInTheDocument()
  })

  it('hides document badge when document_id is null', () => {
    const { container } = render(<SubAgentPanel state={{ ...baseState, document_id: null }} />)
    expect(container.textContent).not.toContain('Doc:')
  })

  it('renders reasoning text', () => {
    render(<SubAgentPanel state={{ ...baseState, reasoning: 'Looking at clauses' }} />)
    expect(screen.getByText(/Looking at clauses/)).toBeInTheDocument()
  })

  it('renders explorer tool calls list', () => {
    render(<SubAgentPanel state={{ ...baseState, explorer_tool_calls: [
      { tool: 'search_documents', input: {}, output: 'h', tool_call_id: 'c1' },
      { tool: 'web_search', input: {}, output: 'h', tool_call_id: 'c2' },
    ] }} />)
    expect(screen.getByText(/search_documents/)).toBeInTheDocument()
    expect(screen.getByText(/web_search/)).toBeInTheDocument()
  })

  it('renders zero explorer calls without crash', () => {
    const { container } = render(<SubAgentPanel state={{ ...baseState, explorer_tool_calls: [] }} />)
    expect(container).toBeDefined()
  })

  it('does not use backdrop-blur (CLAUDE.md design rule)', () => {
    const { container } = render(<SubAgentPanel state={baseState} />)
    expect(container.firstChild?.textContent).toBeDefined()
    const root = container.firstChild as HTMLElement
    expect(root.className ?? '').not.toContain('backdrop-blur')
  })

  it('uses muted/zinc-neutral background', () => {
    const { container } = render(<SubAgentPanel state={baseState} />)
    const root = container.firstChild as HTMLElement
    expect((root.className ?? '')).toMatch(/bg-(muted|zinc-)/)
  })
})
