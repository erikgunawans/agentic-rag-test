import { supabase } from './supabase'

const API_BASE = import.meta.env.VITE_API_BASE_URL as string

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
