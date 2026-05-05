import type { ToolCallRecord } from '@/lib/database.types'
import type { SubAgentState } from './SubAgentPanel'

/**
 * Type guard — checks if a ToolCallRecord carries sub_agent_state with a
 * minimally-correct shape. Used by ToolCallList router to branch rendering.
 */
export function hasSubAgentState(
  call: ToolCallRecord,
): call is ToolCallRecord & { sub_agent_state: SubAgentState } {
  if (!call.sub_agent_state) return false
  const s = call.sub_agent_state as Record<string, unknown>
  return typeof s.mode === 'string' && Array.isArray(s.explorer_tool_calls)
}
