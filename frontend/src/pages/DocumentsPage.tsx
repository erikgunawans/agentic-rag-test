import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { MessageSquare, ArrowLeft, Settings } from 'lucide-react'
import { supabase } from '@/lib/supabase'
import { apiFetch } from '@/lib/api'
import { useDocumentRealtime } from '@/hooks/useDocumentRealtime'
import { FileUpload } from '@/components/documents/FileUpload'
import { DocumentList } from '@/components/documents/DocumentList'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import type { Document } from '@/lib/database.types'

export function DocumentsPage() {
  const navigate = useNavigate()
  const [documents, setDocuments] = useState<Document[]>([])
  const [userId, setUserId] = useState<string | undefined>()

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

  // Realtime: update a single doc's status in-place when it changes
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

  // After upload: reload list so new doc appears immediately
  async function handleUploaded() {
    await loadDocuments()
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header */}
      <div className="flex items-center gap-3 border-b px-6 py-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/')} aria-label="Back to chat">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-sm font-semibold">Documents</h1>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => navigate('/settings')} aria-label="Settings">
            <Settings className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={() => navigate('/')}>
            <MessageSquare className="mr-2 h-4 w-4" />
            Go to Chat
          </Button>
        </div>
      </div>

      <Separator />

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl space-y-6">
          <div>
            <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-3">
              Upload Document
            </h2>
            <FileUpload onUploaded={handleUploaded} />
          </div>

          <div>
            <h2 className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-3">
              Your Documents
            </h2>
            <DocumentList documents={documents} onDelete={handleDelete} />
          </div>
        </div>
      </div>
    </div>
  )
}
