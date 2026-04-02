export interface ModelOption {
  value: string
  label: string
  description: string
}

export const LLM_MODELS: ModelOption[] = [
  { value: 'openai/gpt-4o-mini', label: 'GPT-4o Mini', description: 'Fast & cheap — great default' },
  { value: 'openai/gpt-4o', label: 'GPT-4o', description: 'Most capable OpenAI model' },
  { value: 'anthropic/claude-3-haiku', label: 'Claude 3 Haiku', description: 'Fast Anthropic model' },
  { value: 'anthropic/claude-3.5-sonnet', label: 'Claude 3.5 Sonnet', description: 'Anthropic flagship' },
  { value: 'google/gemini-flash-1.5', label: 'Gemini Flash 1.5', description: 'Fast Google model' },
  { value: 'meta-llama/llama-3.1-8b-instruct', label: 'Llama 3.1 8B', description: 'Open-source, very fast' },
]

// Only 1536-dim models — required to match the pgvector column size
export const EMBEDDING_MODELS: ModelOption[] = [
  { value: 'text-embedding-3-small', label: 'text-embedding-3-small', description: '1536 dims · fast & cheap (recommended)' },
  { value: 'text-embedding-ada-002', label: 'text-embedding-ada-002', description: '1536 dims · legacy OpenAI model' },
]
