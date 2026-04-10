import { useCallback, useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import { apiFetch } from '@/lib/api'
import { useDocumentRealtime } from '@/hooks/useDocumentRealtime'
import { FileUpload } from '@/components/documents/FileUpload'
import { DocumentList } from '@/components/documents/DocumentList'
import { ColumnHeader } from '@/components/shared/ColumnHeader'
import { useSidebar } from '@/layouts/SidebarContext'
import type { Document } from '@/lib/database.types'

function DocumentsSidebar() {
  return (
    <div className="flex flex-col h-full">
      <ColumnHeader title="Documents" subtitle="Upload & manage" rightIcon="none" />
    </div>
  )
}

export function DocumentsPage() {
  const { setSidebar, clearSidebar } = useSidebar()
  const [documents, setDocuments] = useState<Document[]>([])
  const [userId, setUserId] = useState<string | undefined>()

  useEffect(() => {
    setSidebar(<DocumentsSidebar />, 260)
    return () => clearSidebar()
  }, [setSidebar, clearSidebar])

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUserId(data.session?.user.id)
    })
  }, [])

  const loadDocuments = useCallback(async () => {
    const res = await apiFetch('/documents')
    const data: Document[] = await res.json()
    setDocuments(data)
  }, [])

  useEffect(() => {
    loadDocuments()
  }, [loadDocuments])

  const handleRealtimeUpdate = useCallback((updated: Document) => {
    setDocuments((prev) =>
      prev.map((d) => (d.id === updated.id ? { ...d, ...updated } : d)),
    )
  }, [])

  useDocumentRealtime(userId, handleRealtimeUpdate)

  async function handleDelete(id: string) {
    await apiFetch(`/documents/${id}`, { method: 'DELETE' })
    setDocuments((prev) => prev.filter((d) => d.id !== id))
  }

  async function handleUploaded() {
    await loadDocuments()
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-2xl space-y-6">
        <div>
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-text-faint mb-3">
            Upload Document
          </h2>
          <FileUpload onUploaded={handleUploaded} />
        </div>

        <div>
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-text-faint mb-3">
            Your Documents
          </h2>
          <DocumentList documents={documents} onDelete={handleDelete} />
        </div>
      </div>
    </div>
  )
}
