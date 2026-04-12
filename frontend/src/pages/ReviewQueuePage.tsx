import { useCallback, useEffect, useState } from 'react'
import { ClipboardCheck, CheckCircle, XCircle, Loader2, Eye } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n/I18nContext'
import { ConfidenceBadge } from '@/components/shared/ConfidenceBadge'
import { formatTimeAgo } from '@/hooks/useToolHistory'

interface ReviewItem {
  id: string
  user_id: string
  tool_type: string
  title: string
  confidence_score: number
  review_status: string
  review_notes: string | null
  reviewed_by: string | null
  reviewed_at: string | null
  created_at: string
}

const TOOL_TYPE_LABEL: Record<string, string> = {
  create: 'Document Creation',
  compare: 'Document Comparison',
  compliance: 'Compliance Check',
  analyze: 'Contract Analysis',
}

export function ReviewQueuePage() {
  const { t } = useI18n()
  const [items, setItems] = useState<ReviewItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('pending_review')
  const [reviewingId, setReviewingId] = useState<string | null>(null)
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const inputClass = 'w-full rounded-md border bg-secondary text-foreground px-3 py-2 text-sm'

  const loadItems = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch(`/document-tools/review-queue?status=${statusFilter}`)
      const data = await res.json()
      setItems(data.data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('review.error.load'))
    } finally {
      setLoading(false)
    }
  }, [statusFilter, t])

  useEffect(() => {
    loadItems()
  }, [loadItems])

  async function handleReview(id: string, action: 'approve' | 'reject') {
    setSubmitting(true)
    try {
      await apiFetch(`/document-tools/review/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ action, notes }),
      })
      setReviewingId(null)
      setNotes('')
      await loadItems()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('review.error.action'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col overflow-y-auto">
      <div className="max-w-4xl w-full mx-auto p-8 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-lg font-semibold flex items-center gap-2">
            <ClipboardCheck className="h-5 w-5 text-primary" />
            {t('review.title')}
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">{t('review.subtitle')}</p>
        </div>

        {/* Status filter tabs */}
        <div className="flex gap-2">
          {['pending_review', 'approved', 'rejected', 'auto_approved'].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                statusFilter === status
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-muted-foreground hover:text-foreground'
              }`}
            >
              {t(`review.filter.${status}`)}
            </button>
          ))}
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-12">
            <ClipboardCheck className="h-10 w-10 mx-auto text-muted-foreground/25 mb-3" strokeWidth={1.5} />
            <p className="text-sm text-muted-foreground">{t('review.empty')}</p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => (
              <div key={item.id} className="rounded-lg border border-border p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{item.title}</p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      {TOOL_TYPE_LABEL[item.tool_type] ?? item.tool_type} &middot; {formatTimeAgo(item.created_at)}
                    </p>
                  </div>
                  <ConfidenceBadge score={item.confidence_score} reviewStatus={item.review_status} />
                </div>

                {/* Review actions for pending items */}
                {item.review_status === 'pending_review' && (
                  <div className="space-y-2">
                    {reviewingId === item.id ? (
                      <div className="space-y-2">
                        <textarea
                          className={`${inputClass} min-h-[60px] resize-none text-xs`}
                          placeholder={t('review.notesPlaceholder')}
                          value={notes}
                          onChange={(e) => setNotes(e.target.value)}
                        />
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            className="text-xs"
                            disabled={submitting}
                            onClick={() => handleReview(item.id, 'approve')}
                          >
                            <CheckCircle className="mr-1.5 h-3.5 w-3.5" />
                            {t('review.approve')}
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            className="text-xs"
                            disabled={submitting}
                            onClick={() => handleReview(item.id, 'reject')}
                          >
                            <XCircle className="mr-1.5 h-3.5 w-3.5" />
                            {t('review.reject')}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-xs"
                            onClick={() => { setReviewingId(null); setNotes('') }}
                          >
                            {t('review.cancel')}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-xs"
                        onClick={() => setReviewingId(item.id)}
                      >
                        <Eye className="mr-1.5 h-3.5 w-3.5" />
                        {t('review.reviewAction')}
                      </Button>
                    )}
                  </div>
                )}

                {/* Show review notes for reviewed items */}
                {(item.review_status === 'approved' || item.review_status === 'rejected') && item.review_notes && (
                  <div className="rounded-md bg-secondary/50 px-3 py-2">
                    <p className="text-[10px] text-muted-foreground">
                      <span className="font-medium">{t('review.notes')}:</span> {item.review_notes}
                    </p>
                    {item.reviewed_at && (
                      <p className="text-[9px] text-muted-foreground mt-0.5">
                        {t('review.reviewedAt')}: {formatTimeAgo(item.reviewed_at)}
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
