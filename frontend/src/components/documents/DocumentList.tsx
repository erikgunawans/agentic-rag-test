import { Trash2, FileText, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { Document } from '@/lib/database.types'

interface DocumentListProps {
  documents: Document[]
  onDelete: (id: string) => void
}

const STATUS_STYLES: Record<Document['status'], string> = {
  pending: 'bg-muted text-muted-foreground',
  processing: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentList({ documents, onDelete }: DocumentListProps) {
  if (documents.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-8">
        No documents yet. Upload one above.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => (
        <div
          key={doc.id}
          className="flex items-center gap-3 rounded-lg border p-3 text-sm"
        >
          <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
          <div className="flex-1 min-w-0">
            <p className="font-medium truncate">{doc.filename}</p>
            <p className="text-xs text-muted-foreground">
              {formatBytes(doc.file_size)}
              {doc.status === 'completed' && doc.chunk_count != null
                ? ` · ${doc.chunk_count} chunks`
                : ''}
              {doc.status === 'failed' && doc.error_msg
                ? ` · ${doc.error_msg}`
                : ''}
            </p>
          </div>
          <span
            className={`shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[doc.status]}`}
          >
            {doc.status === 'processing' && (
              <Loader2 className="h-3 w-3 animate-spin" />
            )}
            {doc.status}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0 h-7 w-7"
            onClick={() => onDelete(doc.id)}
            aria-label="Delete document"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ))}
    </div>
  )
}
