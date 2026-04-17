import { Check, Lock } from 'lucide-react'
import { useI18n } from '@/i18n/I18nContext'

const PHASES = ['pre_decision', 'decision', 'post_decision'] as const

const PHASE_ORDER: Record<string, number> = {
  pre_decision: 0,
  decision: 1,
  post_decision: 2,
  completed: 3,
}

interface PhaseProgressProps {
  currentPhase: string
  onSelectPhase?: (phase: string) => void
  selectedPhase?: string
}

export function PhaseProgress({ currentPhase, onSelectPhase, selectedPhase }: PhaseProgressProps) {
  const { t } = useI18n()
  const currentIdx = PHASE_ORDER[currentPhase] ?? 0

  return (
    <div className="flex items-center gap-2">
      {PHASES.map((phase, idx) => {
        const isComplete = idx < currentIdx || currentPhase === 'completed'
        const isCurrent = idx === currentIdx && currentPhase !== 'completed'
        const isLocked = idx > currentIdx && currentPhase !== 'completed'
        const isSelected = selectedPhase === phase

        return (
          <div key={phase} className="flex items-center gap-2">
            {idx > 0 && (
              <div className={`h-px w-8 ${isComplete ? 'bg-green-500' : 'bg-border'}`} />
            )}
            <button
              onClick={() => onSelectPhase?.(phase)}
              disabled={!onSelectPhase}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                isSelected
                  ? 'bg-primary/15 text-primary ring-1 ring-primary/30'
                  : isComplete
                    ? 'bg-green-500/10 text-green-600 dark:text-green-400'
                    : isCurrent
                      ? 'bg-primary/10 text-primary'
                      : 'bg-secondary text-muted-foreground'
              }`}
            >
              {isComplete ? (
                <Check className="h-3.5 w-3.5" />
              ) : isLocked ? (
                <Lock className="h-3.5 w-3.5" />
              ) : (
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-primary/20 text-[10px] font-bold">
                  {idx + 1}
                </span>
              )}
              {t(`bjr.phase.${phase}`)}
            </button>
          </div>
        )
      })}

      {currentPhase === 'completed' && (
        <>
          <div className="h-px w-8 bg-green-500" />
          <div className="flex items-center gap-2 rounded-lg bg-green-500/10 px-3 py-2 text-xs font-medium text-green-600 dark:text-green-400">
            <Check className="h-3.5 w-3.5" />
            {t('bjr.phase.completed')}
          </div>
        </>
      )}
    </div>
  )
}
