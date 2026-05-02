import type { Message, ToolCallRecord } from './database.types'

/** Groups messages by their parent_message_id. Key `null` holds root messages. */
export function buildChildrenMap(messages: Message[]): Map<string | null, Message[]> {
  const map = new Map<string | null, Message[]>()
  for (const msg of messages) {
    const parentId = msg.parent_message_id ?? null
    if (!map.has(parentId)) map.set(parentId, [])
    map.get(parentId)!.push(msg)
  }
  return map
}

/**
 * Walks the message tree from roots, following branchSelections at fork points.
 * Returns the linear path of messages currently visible to the user.
 */
export function getActivePath(
  childrenMap: Map<string | null, Message[]>,
  branchSelections: Map<string, string>,
): Message[] {
  const path: Message[] = []
  let parentId: string | null = null
  const visited = new Set<string | null>()

  while (true) {
    if (visited.has(parentId)) break
    visited.add(parentId)
    const children = childrenMap.get(parentId)
    if (!children || children.length === 0) break

    let selected: Message = children[0]
    if (parentId !== null) {
      const selId = branchSelections.get(parentId)
      if (selId) {
        selected = children.find((c) => c.id === selId) ?? children[0]
      }
    }

    path.push(selected)
    parentId = selected.id
  }

  return path
}

/**
 * Phase 12 / HIST-04 / HIST-05 / D-P12-15 — flatten per-round messages into
 * interleaved ConversationItem[] for visually identical history reconstruction.
 *
 * Walks messages in created_at order. For each message emits:
 *   1. {kind:'text'} item if content is non-empty.
 *   2. {kind:'tool', toolCall} for each entry in tool_calls.calls[].
 *
 * The toolCall passthrough preserves sub_agent_state and code_execution_state
 * sub-keys so consumer components (ToolCallList -> SubAgentPanel /
 * CodeExecutionPanel) can branch on their presence.
 *
 * Multi-row exchanges naturally interleave: row-1 text -> row-1 tool calls ->
 * row-2 text -> row-2 tool calls -> ... — identical to live SSE order.
 *
 * Legacy single-row exchanges still work: one row with N tool_calls.calls
 * produces 1 + N items.
 */
export type ConversationItem =
  | { kind: 'text'; key: string; role: 'user' | 'assistant'; text: string; messageId: string }
  | { kind: 'tool'; key: string; role: 'assistant'; toolCall: ToolCallRecord; messageId: string }

export function buildInterleavedItems(messages: Message[]): ConversationItem[] {
  const sorted = [...messages].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  )
  const items: ConversationItem[] = []
  for (const msg of sorted) {
    if (msg.content && msg.content.length > 0) {
      items.push({
        kind: 'text',
        key: `${msg.id}-text`,
        role: msg.role,
        text: msg.content,
        messageId: msg.id,
      })
    }
    if (msg.role === 'assistant' && msg.tool_calls?.calls) {
      for (const call of msg.tool_calls.calls) {
        const callKey = call.tool_call_id ?? `${call.tool}-${items.length}`
        items.push({
          kind: 'tool',
          key: `${msg.id}-call-${callKey}`,
          role: 'assistant',
          toolCall: call,
          messageId: msg.id,
        })
      }
    }
  }
  return items
}
