import { describe, it, expect } from 'vitest'
import { buildInterleavedItems } from '../messageTree'
import type { Message } from '../database.types'


function mkMsg(overrides: Partial<Message>): Message {
  return {
    id: 'msg-default',
    thread_id: 't1',
    user_id: 'u1',
    role: 'assistant',
    content: '',
    parent_message_id: null,
    created_at: '2026-05-02T00:00:00Z',
    ...overrides,
  } as Message
}


describe('buildInterleavedItems', () => {
  it('flattens single-row legacy exchange to one item per call', () => {
    const msg = mkMsg({
      id: 'm1',
      content: 'thinking',
      tool_calls: {
        calls: [
          { tool: 'search_documents', input: {}, output: 'hits', tool_call_id: 'call_1' },
          { tool: 'execute_code', input: {}, output: {}, tool_call_id: 'call_2',
            code_execution_state: { code: 'print(1)', stdout: '1\n', stderr: '', exit_code: 0, execution_ms: 10, files: [], error_type: null } },
        ],
      },
    })
    const items = buildInterleavedItems([msg])
    expect(items).toHaveLength(3)
    expect(items[0]).toMatchObject({ kind: 'text', text: 'thinking' })
    expect(items[1]).toMatchObject({ kind: 'tool', toolCall: { tool: 'search_documents' } })
    expect(items[2]).toMatchObject({ kind: 'tool', toolCall: { tool: 'execute_code' } })
    if (items[2].kind === 'tool') {
      expect(items[2].toolCall.code_execution_state).toBeDefined()
    }
  })

  it('flattens 2-round exchange to interleaved sequence', () => {
    const r1 = mkMsg({
      id: 'm1', content: 'let me look that up', created_at: '2026-05-02T00:00:01Z',
      tool_calls: { calls: [{ tool: 'search_documents', input: {}, output: 'hits', tool_call_id: 'call_1' }] },
    })
    const r2 = mkMsg({
      id: 'm2', content: 'based on the search, here is the answer', created_at: '2026-05-02T00:00:02Z',
      parent_message_id: 'm1',
    })
    const items = buildInterleavedItems([r1, r2])
    expect(items).toHaveLength(3)
    expect(items[0]).toMatchObject({ kind: 'text', text: 'let me look that up' })
    expect(items[1]).toMatchObject({ kind: 'tool', toolCall: { tool: 'search_documents' } })
    expect(items[2]).toMatchObject({ kind: 'text', text: 'based on the search, here is the answer' })
  })

  it('processes rows in created_at order regardless of input order', () => {
    const r1 = mkMsg({ id: 'm1', content: 'first', created_at: '2026-05-02T00:00:01Z' })
    const r2 = mkMsg({ id: 'm2', content: 'second', created_at: '2026-05-02T00:00:02Z' })
    const items = buildInterleavedItems([r2, r1])  // reversed input
    expect(items[0]).toMatchObject({ text: 'first' })
    expect(items[1]).toMatchObject({ text: 'second' })
  })

  it('includes sub_agent_state on items that have it', () => {
    const msg = mkMsg({
      id: 'm1', content: '',
      tool_calls: { calls: [{
        tool: 'run_research_agent', input: {}, output: 'done', tool_call_id: 'call_x',
        sub_agent_state: { mode: 'explorer', document_id: null, reasoning: 'r', explorer_tool_calls: [] },
      }] },
    })
    const items = buildInterleavedItems([msg])
    expect(items).toHaveLength(1)
    if (items[0].kind === 'tool') {
      expect(items[0].toolCall.sub_agent_state).toBeDefined()
      expect((items[0].toolCall.sub_agent_state as { mode: string }).mode).toBe('explorer')
    }
  })

  it('includes code_execution_state on items that have it', () => {
    const msg = mkMsg({
      id: 'm1', content: '',
      tool_calls: { calls: [{
        tool: 'execute_code', input: {}, output: {}, tool_call_id: 'call_x',
        code_execution_state: { code: 'print(1)', stdout: '1', stderr: '', exit_code: 0, execution_ms: 1, files: [], error_type: null },
      }] },
    })
    const items = buildInterleavedItems([msg])
    expect(items).toHaveLength(1)
    if (items[0].kind === 'tool') {
      expect(items[0].toolCall.code_execution_state).toBeDefined()
    }
  })

  it('empty assistant content does not emit text item', () => {
    const msg = mkMsg({
      id: 'm1', content: '',
      tool_calls: { calls: [{ tool: 'search_documents', input: {}, output: 'h', tool_call_id: 'c1' }] },
    })
    const items = buildInterleavedItems([msg])
    expect(items).toHaveLength(1)
    expect(items[0]).toMatchObject({ kind: 'tool' })
  })

  it('user messages emit only a text item', () => {
    const msg = mkMsg({ id: 'm1', role: 'user', content: 'hi' })
    const items = buildInterleavedItems([msg])
    expect(items).toHaveLength(1)
    expect(items[0]).toMatchObject({ kind: 'text', role: 'user', text: 'hi' })
  })

  it('produces stable keys per item', () => {
    const msg = mkMsg({
      id: 'm1', content: 'hi',
      tool_calls: { calls: [{ tool: 't', input: {}, output: 'o', tool_call_id: 'c1' }] },
    })
    const items1 = buildInterleavedItems([msg])
    const items2 = buildInterleavedItems([msg])
    expect(items1[0].key).toBe(items2[0].key)
    expect(items1[1].key).toBe(items2[1].key)
    expect(items1[0].key).not.toBe(items1[1].key)
  })
})
