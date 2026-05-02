import { supabase } from './supabase'
import type { Todo } from './database.types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string).trim()

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token

  // Don't set Content-Type for FormData — browser sets it with the correct boundary
  const isFormData = options.body instanceof FormData

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || 'Request failed')
  }

  return response
}

/**
 * Phase 17 / TODO-07 / D-21: Hydrate the Plan Panel on thread reload.
 * Calls GET /threads/{thread_id}/todos which returns the current agent_todos rows
 * ordered by position ASC. Called once on thread mount / thread switch.
 * RLS-scoped via Bearer token; server returns [] for cross-user requests (D-27).
 */
export async function fetchThreadTodos(
  thread_id: string,
  token: string,
): Promise<{ todos: Todo[] }> {
  const res = await fetch(`${API_BASE}/threads/${thread_id}/todos`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) {
    // Non-2xx: return empty rather than crashing the UI (T-17-16 mitigation)
    return { todos: [] }
  }
  return res.json() as Promise<{ todos: Todo[] }>
}
