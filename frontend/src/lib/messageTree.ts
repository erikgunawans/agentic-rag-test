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

  while (true) {
    const children = childrenMap.get(parentId)
    if (!children || children.length === 0) break

    // At a fork point, use the stored selection; otherwise take the first child
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

/** Returns a Set of message IDs that have more than one child (fork points). */
export function getForkPoints(childrenMap: Map<string | null, Message[]>): Set<string> {
  const forks = new Set<string>()
  for (const [parentId, children] of childrenMap) {
    if (parentId !== null && children.length > 1) {
      forks.add(parentId)
    }
  }
  return forks
}
