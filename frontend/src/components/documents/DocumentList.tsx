import { Trash2, FileText, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'
import type { Document } from '@/lib/database.types'

interface DocumentListProps {
  documents: Document[]
  onDelete: (id: string) => void
}

const STATUS_STYLES: Record<Document['status'], string> = {
  pending: 'bg-muted text-muted-foreground',
  processing: 'bg-yellow-500/10 text-yellow-400',
  completed: 'bg-green-500/10 text-green-400',
  failed: 'bg-red-500/10 text-red-400',
}

const CATEGORY_STYLES: Record<string, string> = {
  technical: 'bg-blue-500/10 text-blue-400',
  legal: 'bg-purple-500/10 text-purple-400',
  business: 'bg-orange-500/10 text-orange-400',
  academic: 'bg-teal-500/10 text-teal-400',
  personal: 'bg-pink-500/10 text-pink-400',
  other: 'bg-gray-500/10 text-gray-400',
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function DocumentList({ documents, onDelete }: DocumentListProps) {
  const { t } = useI18n()

  if (documents.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-8">
        {t('docList.empty')}
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {documents.map((doc) => {
        const meta = doc.status === 'completed' ? doc.metadata : null
        const visibleTags = meta?.tags?.slice(0, 3) ?? []
        const extraTags = (meta?.tags?.length ?? 0) - visibleTags.length

        return (
          <div
            key={doc.id}
            className="rounded-lg border p-3 text-sm transition-all duration-200 hover:shadow-[var(--shadow-sm)] hover:border-border/80"
          >
            <div className="flex items-start gap-3">
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{doc.filename}</p>
                {meta?.title && meta.title !== doc.filename && (
                  <p className="text-xs text-foreground/70 truncate mt-0.5">{meta.title}</p>
                )}
                <p className="text-xs text-muted-foreground mt-0.5">
                  {formatBytes(doc.file_size)}
                  {doc.status === 'completed' && doc.chunk_count != null
                    ? ` · ${t('docList.chunks', { count: String(doc.chunk_count) })}`
                    : ''}
                  {doc.status === 'failed' && doc.error_msg
                    ? ` · ${doc.error_msg}`
                    : ''}
                </p>
                {meta && visibleTags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {visibleTags.map((tag) => (
                      <span
                        key={tag}
                        className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                      >
                        {tag}
                      </span>
                    ))}
                    {extraTags > 0 && (
                      <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                        {t('docList.more', { count: String(extraTags) })}
                      </span>
                    )}
                  </div>
                )}
                {meta?.summary && (
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{meta.summary}</p>
                )}
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                {meta?.category && (
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${CATEGORY_STYLES[meta.category] ?? CATEGORY_STYLES.other}`}
                  >
                    {meta.category}
                  </span>
                )}
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[doc.status]}`}
                >
                  {doc.status === 'processing' && (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  )}
                  {doc.status}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => onDelete(doc.id)}
                  aria-label={t('docList.delete')}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
