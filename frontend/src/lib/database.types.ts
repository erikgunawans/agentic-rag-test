export interface Thread {
  id: string
  user_id: string
  title: string
  openai_thread_id: string | null
  last_response_id: string | null
  created_at: string
  updated_at: string
}

export interface ToolCallRecord {
  tool: string
  input: Record<string, unknown>
  output: Record<string, unknown> | string
  error?: string | null
}

export interface Message {
  id: string
  thread_id: string
  user_id: string
  role: 'user' | 'assistant'
  content: string
  tool_calls?: { agent?: string | null; calls: ToolCallRecord[] } | null
  parent_message_id?: string | null
  created_at: string
}

export interface DeltaEvent {
  type?: 'delta'
  delta: string
  done: boolean
}

export interface ToolStartEvent {
  type: 'tool_start'
  tool: string
  input?: Record<string, unknown>  // Phase 5 D-89: omitted in skeleton mode when redaction is ON
}

export interface ToolResultEvent {
  type: 'tool_result'
  tool: string
  output?: Record<string, unknown>  // Phase 5 D-89: omitted in skeleton mode when redaction is ON
}

export interface AgentStartEvent {
  type: 'agent_start'
  agent: string
  display_name: string
}

export interface AgentDoneEvent {
  type: 'agent_done'
  agent: string
}

export interface ThreadTitleEvent {
  type: 'thread_title'
  title: string
  thread_id: string
}

// Phase 5 D-88 + D-94: redaction status events.
// 'anonymizing' fires once per turn after agent_start (covers history anon + tool-loop iterations).
// 'deanonymizing' fires once per turn after the buffer completes (before de-anon runs).
// 'blocked' fires on egress filter trip (D-94) — turn aborts cleanly.
export interface RedactionStatusEvent {
  type: 'redaction_status'
  stage: 'anonymizing' | 'deanonymizing' | 'blocked'
}

export type SSEEvent =
  | DeltaEvent
  | ToolStartEvent
  | ToolResultEvent
  | AgentStartEvent
  | AgentDoneEvent
  | ThreadTitleEvent
  | RedactionStatusEvent  // Phase 5 D-88

export interface DocumentMetadata {
  title: string
  author: string | null
  date_period: string | null
  category: 'technical' | 'legal' | 'business' | 'academic' | 'personal' | 'other'
  tags: string[]
  summary: string
}

export interface DocumentToolResult {
  id: string
  tool_type: 'create' | 'compare' | 'compliance' | 'analyze'
  title: string
  input_params: Record<string, unknown>
  result?: Record<string, unknown>
  confidence_score?: number
  review_status?: 'auto_approved' | 'pending_review' | 'approved' | 'rejected'
  created_at: string
}

export interface Document {
  id: string
  user_id: string
  filename: string
  file_size: number
  mime_type: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  chunk_count: number | null
  error_msg: string | null
  content_hash: string | null
  metadata: DocumentMetadata | null
  folder_id: string | null
  created_at: string
}

export interface DocumentFolder {
  id: string
  user_id: string
  name: string
  parent_folder_id: string | null
  is_global?: boolean
  created_at: string
  updated_at: string
}
