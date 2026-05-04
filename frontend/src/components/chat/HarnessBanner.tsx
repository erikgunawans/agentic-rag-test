/**
 * Phase 20 / Plan 20-09 / HARN-09 / UI-SPEC L122-141
 * HarnessBanner — sticky full-width band above the chat scroll region.
 *
 * Renders when harnessRun.status is in the active set (pending/running/paused).
 * On terminal state (completed/cancelled/failed) shows terminal copy for 3000ms,
 * then the slice is set to null by useChatState's terminal-fade useEffect.
 *
 * Surface rules (CLAUDE.md):
 *   - bg-background border-b border-border/50 px-4 py-2
 *   - NO backdrop-blur (persistent header band, not a transient overlay)
 *   - role="status" aria-live="polite" for screen reader announcements
 */
import { useState } from 'react'
import { AlertCircle, XCircle, X } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'
import { useChatContext } from '@/contexts/ChatContext'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { apiFetch } from '@/lib/api'

const ACTIVE_STATUSES = new Set(['pending', 'running', 'paused'])

export function HarnessBanner() {
  const { t } = useI18n()
  // Phase 21 / Plan 21-05 / D-09 / BATCH-04 / BATCH-06: also read batchProgress
  // so the banner can append "— Analyzing clause N/M" during llm_batch_agents phases.
  const { harnessRun, batchProgress, activeThreadId } = useChatContext()
  const [cancelOpen, setCancelOpen] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  // When harnessRun is null, keep an sr-only container in DOM so screen readers
  // can announce the next state change reliably (UI-SPEC L140 accessibility).
  if (!harnessRun) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="sr-only"
        data-testid="harness-banner-empty"
      />
    )
  }

  const harnessLabel =
    t(`harness.type.${harnessRun.harnessType}`) || harnessRun.harnessType
  const isActive = ACTIVE_STATUSES.has(harnessRun.status)
  const isCancelled = harnessRun.status === 'cancelled'
  const isFailed = harnessRun.status === 'failed'

  async function onConfirmCancel() {
    if (!activeThreadId) return
    setCancelling(true)
    try {
      await apiFetch(`/threads/${activeThreadId}/harness/cancel`, { method: 'POST' })
    } finally {
      setCancelling(false)
      setCancelOpen(false)
    }
  }

  // Build title text based on state.
  // Phase 21 / Plan 21-05 / HIL-02: when status is 'paused', use the
  // "Awaiting your response — {harnessType}" copy instead of the running fraction.
  const isPaused = harnessRun.status === 'paused'

  const baseTitle = isActive
    ? isPaused
      ? t('harness.banner.paused', { harnessType: harnessLabel })
      : t('harness.banner.running', {
          harnessType: harnessLabel,
          n: String(harnessRun.currentPhase + 1),
          m: String(harnessRun.phaseCount || '?'),
          phaseName: harnessRun.phaseName,
        })
    : isCancelled
    ? t('harness.banner.cancelled', { harnessType: harnessLabel })
    : isFailed
    ? t('harness.banner.failed', {
        harnessType: harnessLabel,
        detail: harnessRun.errorDetail ?? '',
      })
    : ''

  // Phase 21 / Plan 21-05 / D-09 / BATCH-04 / BATCH-06: append per-item batch
  // progress suffix when batchProgress is non-null. Cleared at phase boundary
  // by useChatState's harness_phase_complete reducer arm.
  const batchSuffix = batchProgress
    ? ' — ' +
      t('harness.banner.batchProgress', {
        completed: String(batchProgress.completed),
        total: String(batchProgress.total),
      })
    : ''

  const titleText = baseTitle + batchSuffix

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="harness-banner"
      className="bg-background border-b border-border/50 px-4 py-2 flex items-center gap-2"
    >
      {/* Status indicator dot / terminal icon */}
      {isActive ? (
        <span
          className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse"
          aria-hidden="true"
          data-testid="harness-banner-pulse"
        />
      ) : isCancelled ? (
        <XCircle
          size={14}
          className="text-muted-foreground"
          aria-hidden="true"
        />
      ) : (
        <AlertCircle
          size={14}
          className="text-red-600 dark:text-red-400"
          aria-hidden="true"
        />
      )}

      {/* Title text — phase fraction when active, terminal copy otherwise */}
      <span className="text-sm font-semibold text-foreground tabular-nums truncate">
        {titleText}
      </span>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Cancel button — only when active */}
      {isActive && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          data-testid="harness-banner-cancel"
          onClick={() => setCancelOpen(true)}
          className="h-6 px-2 gap-1"
        >
          <X size={12} aria-hidden="true" />
          <span>{t('common.cancel')}</span>
        </Button>
      )}

      {/* Cancel confirmation Dialog (same flow as locked PlanPanel header) */}
      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {t('harness.cancel.confirmTitle', { harnessType: harnessLabel })}
            </DialogTitle>
            <DialogDescription>
              {t('harness.cancel.confirmBody')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCancelOpen(false)}
              disabled={cancelling}
            >
              {t('harness.cancel.keepRunning')}
            </Button>
            <Button
              variant="destructive"
              onClick={onConfirmCancel}
              disabled={cancelling}
              data-testid="harness-banner-cancel-confirm"
            >
              {t('harness.cancel.confirmAction')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
