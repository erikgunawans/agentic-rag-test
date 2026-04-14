import type { Message } from './database.types'

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
