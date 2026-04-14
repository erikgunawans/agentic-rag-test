import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'
import type { DocumentToolResult } from '@/lib/database.types'

export function useToolHistory(toolType: string) {
  const [history, setHistory] = useState<DocumentToolResult[]>([])

  const load = useCallback(async () => {
    try {
      const res = await apiFetch(`/document-tools/history?tool_type=${toolType}&limit=10`)
      const data: DocumentToolResult[] = await res.json()
      setHistory(data)
    } catch {
      // silent — history is non-critical
    }
  }, [toolType])

  useEffect(() => {
    load()
  }, [load])

  return { history, reload: load }
}

export function formatTimeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  return `${Math.floor(days / 7)}w ago`
}
