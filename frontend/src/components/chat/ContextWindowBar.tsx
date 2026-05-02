/**
 * Phase 12 / CTX-04 / CTX-05 / CTX-06 — slim context-window usage bar.
 *
 * Renders a 4px (h-1) track + fill + Xk / Yk (Z%) label above the chat input.
 * Color shifts at 60% (emerald→amber) and 80% (amber→rose) per the PRD.
 *
 * Hidden when usage is null OR contextWindow is null OR usage.total is null —
 * mount/unmount via JSX so the bar takes ZERO vertical space until the first
 * usage event lands (CTX-05 / D-P12-09).
 *
 * D-P12-07: lives inside MessageInput's existing max-w-2xl container.
 */

interface UsagePayload {
  prompt: number | null
  completion: number | null
  total: number | null
}

interface ContextWindowBarProps {
  usage: UsagePayload | null
  contextWindow: number | null
}

function formatTokens(n: number): string {
  // Specifics: <1k → raw integer; >=1k → Math.round(n/1000) + 'k'
  if (n < 1000) return String(n)
  return `${Math.round(n / 1000)}k`
}

function pickColorClass(percent: number): string {
  // D-P12-10: emerald (0–59), amber (60–79), rose (80–100+).
  if (percent >= 0.8) return 'bg-rose-500'
  if (percent >= 0.6) return 'bg-amber-500'
  return 'bg-emerald-500'
}

export function ContextWindowBar({ usage, contextWindow }: ContextWindowBarProps) {
  // CTX-05 / CTX-06 / D-P12-09: hidden until first usage event arrives.
  if (usage === null || contextWindow === null || usage.total === null) {
    return null
  }
  const total = usage.total
  const rawPercent = total / contextWindow
  const widthPercent = Math.min(rawPercent, 1.0) * 100   // clamped for visual fill
  const labelPercent = (rawPercent * 100).toFixed(0)     // raw for label (may exceed 100)
  const fillColor = pickColorClass(rawPercent)

  return (
    <div className="mb-2" data-testid="ctx-bar">
      <div
        data-testid="ctx-track"
        className="h-1 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800"
      >
        <div
          data-testid="ctx-fill"
          className={`h-1 rounded-full transition-all duration-300 ease-out ${fillColor}`}
          style={{ width: `${widthPercent}%` }}
        />
      </div>
      <div
        data-testid="ctx-label"
        className="mt-1 text-[11px] tabular-nums text-muted-foreground"
      >
        {formatTokens(total)} / {formatTokens(contextWindow)} ({labelPercent}%)
      </div>
    </div>
  )
}
