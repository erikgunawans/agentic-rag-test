/**
 * Phase 12 / HIST-02 / HIST-05 — sub-agent panel for history-reload rendering.
 *
 * Mirrors the live SSE-driven sub-agent visual style. Reads the persisted
 * sub_agent_state JSONB from a tool_calls.calls[N] entry and renders:
 *   - mode badge (explorer / analysis)
 *   - document badge (when document_id present)
 *   - reasoning text
 *   - explorer tool calls mini-list (tool name + tool_call_id)
 *
 * No backdrop-blur (CLAUDE.md design rule — persistent panel).
 */

import type { ToolCallRecord } from '@/lib/database.types'

export interface SubAgentState {
  mode: 'explorer' | 'analysis' | string
  document_id: string | null
  reasoning: string
  explorer_tool_calls: Array<{
    tool: string
    input: Record<string, unknown>
    output: Record<string, unknown> | string
    tool_call_id: string
  }>
}


interface SubAgentPanelProps {
  state: SubAgentState
}


export function SubAgentPanel({ state }: SubAgentPanelProps) {
  return (
    <div className="rounded-lg border bg-muted/40 p-3 text-sm space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-zinc-200 dark:bg-zinc-800 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide">
          {state.mode}
        </span>
        {state.document_id && (
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary">
            Doc: {state.document_id}
          </span>
        )}
      </div>
      {state.reasoning && (
        <p className="text-xs text-muted-foreground whitespace-pre-wrap">
          {state.reasoning}
        </p>
      )}
      {state.explorer_tool_calls && state.explorer_tool_calls.length > 0 && (
        <ul className="space-y-1 text-xs">
          {state.explorer_tool_calls.map((c) => (
            <li key={c.tool_call_id} className="flex items-center gap-2 text-muted-foreground">
              <span className="font-mono text-[11px]">{c.tool}</span>
              <span className="text-[10px] opacity-60">{c.tool_call_id}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}


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
