import { type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { HintChipRow } from './HintChipRow';

interface EmptyStateProps {
  icon: LucideIcon;
  line1: string;
  line2: string;
  hintChips: [
    { color: string; label: string },
    { color: string; label: string },
    { color: string; label: string },
  ];
  className?: string;
}

export function EmptyState({ icon: Icon, line1, line2, hintChips, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex-1 flex items-center justify-center relative overflow-hidden bg-bg-deep',
        className,
      )}
    >
      {/* Mesh Gradients */}
      <div className="absolute top-0 right-0 w-[600px] h-[600px] pointer-events-none bg-[radial-gradient(circle,rgba(76,29,149,0.06)_0%,transparent_70%)]" />
      <div className="absolute bottom-0 left-0 w-[500px] h-[500px] pointer-events-none bg-[radial-gradient(circle,rgba(10,31,61,0.3)_0%,transparent_70%)]" />

      {/* Empty State Content */}
      <div className="flex flex-col items-center gap-4 relative z-10">
        {/* Nested circles */}
        <div className="flex items-center justify-center rounded-full size-24 bg-accent-primary/[0.06] border border-accent-primary/[0.12]">
          <div className="flex items-center justify-center rounded-full size-[72px] bg-accent-primary/10 border border-accent-primary/[0.18]">
            <Icon className="size-8 text-accent-primary/50" />
          </div>
        </div>

        {/* Body text - 2 lines */}
        <div className="flex flex-col items-center gap-1">
          <p className="text-sm text-text-faint text-center max-w-[340px] leading-relaxed">
            {line1}
          </p>
          <p className="text-sm text-text-faint text-center max-w-[340px] leading-relaxed">
            {line2}
          </p>
        </div>

        {/* Hint chips */}
        <HintChipRow chips={hintChips} />
      </div>
    </div>
  );
}
