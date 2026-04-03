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
  input: Record<string, unknown>
}

export interface ToolResultEvent {
  type: 'tool_result'
  tool: string
  output: Record<string, unknown>
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

export type SSEEvent = DeltaEvent | ToolStartEvent | ToolResultEvent | AgentStartEvent | AgentDoneEvent

export interface DocumentMetadata {
  title: string
  author: string | null
  date_period: string | null
  category: 'technical' | 'legal' | 'business' | 'academic' | 'personal' | 'other'
  tags: string[]
  summary: string
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
  created_at: string
}
