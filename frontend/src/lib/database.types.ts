export interface Thread {
  id: string
  user_id: string
  title: string
  openai_thread_id: string | null
  last_response_id: string | null
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  thread_id: string
  user_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

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
