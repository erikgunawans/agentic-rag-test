import type { LucideIcon } from 'lucide-react'
import { FileSearch } from 'lucide-react'

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  subtitle: string
}

export function EmptyState({ icon: Icon = FileSearch, title, subtitle }: EmptyStateProps) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 mesh-bg">
      <div className="flex flex-col items-center gap-4 max-w-sm text-center animate-fade-in-up">
        <div className="relative flex h-20 w-20 items-center justify-center">
          <div className="pulse-ring h-20 w-20" />
          <div className="pulse-ring h-20 w-20" style={{ animationDelay: '1s' }} />
          <div className="pulse-ring h-20 w-20" style={{ animationDelay: '2s' }} />
          <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20">
            <Icon className="h-8 w-8 text-primary/60" />
          </div>
        </div>
        <div>
          <h2 className="text-base font-semibold text-foreground">{title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
        </div>
      </div>
    </div>
  )
}
