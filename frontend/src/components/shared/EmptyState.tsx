import type { LucideIcon } from 'lucide-react'
import { FileSearch } from 'lucide-react'

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  subtitle: string
}

export function EmptyState({ icon: Icon = FileSearch, title, subtitle }: EmptyStateProps) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4">
      <div className="flex flex-col items-center gap-5 max-w-sm text-center animate-fade-in-up">
        <div>
          <Icon className="h-10 w-10 text-muted-foreground/25 mx-auto" strokeWidth={1.5} />
          <div className="mt-3 h-px w-12 mx-auto bg-gradient-to-r from-transparent via-border to-transparent" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-foreground">{title}</h2>
          <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">{subtitle}</p>
        </div>
      </div>
    </div>
  )
}
