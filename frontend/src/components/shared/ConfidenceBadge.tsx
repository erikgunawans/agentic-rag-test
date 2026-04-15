interface ConfidenceBadgeProps {
  score: number
  reviewStatus?: string
}

const LEVEL_STYLE: Record<string, { color: string; bg: string }> = {
  high: { color: 'text-green-600 dark:text-green-400', bg: 'bg-green-500/10 border-green-500/30' },
  medium: { color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30' },
  low: { color: 'text-red-600 dark:text-red-400', bg: 'bg-red-500/10 border-red-500/30' },
}

const REVIEW_STYLE: Record<string, { color: string; bg: string }> = {
  auto_approved: { color: 'text-green-600 dark:text-green-400', bg: 'bg-green-500/10 border-green-500/30' },
  pending_review: { color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-500/10 border-amber-500/30' },
  approved: { color: 'text-green-600 dark:text-green-400', bg: 'bg-green-500/10 border-green-500/30' },
  rejected: { color: 'text-red-600 dark:text-red-400', bg: 'bg-red-500/10 border-red-500/30' },
}

const REVIEW_LABEL: Record<string, string> = {
  auto_approved: 'AUTO-APPROVED',
  pending_review: 'PENDING REVIEW',
  approved: 'APPROVED',
  rejected: 'REJECTED',
}

function getLevel(score: number): string {
  if (score >= 0.85) return 'high'
  if (score >= 0.6) return 'medium'
  return 'low'
}

export function ConfidenceBadge({ score, reviewStatus }: ConfidenceBadgeProps) {
  const level = getLevel(score)
  const style = LEVEL_STYLE[level]
  const review = reviewStatus ? REVIEW_STYLE[reviewStatus] : null

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${style.bg} ${style.color}`}>
        {Math.round(score * 100)}%
      </span>
      {review && reviewStatus !== 'auto_approved' && (
        <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold ${review.bg} ${review.color}`}>
          {REVIEW_LABEL[reviewStatus!]}
        </span>
      )}
    </div>
  )
}
