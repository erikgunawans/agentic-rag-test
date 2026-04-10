import { cn } from '@/lib/utils';

interface SectionLabelProps {
  children: React.ReactNode;
  required?: boolean;
  className?: string;
}

export function SectionLabel({ children, required = false, className }: SectionLabelProps) {
  return (
    <div className={cn('flex items-center gap-2 mb-2', className)}>
      <span className="text-[11px] font-semibold text-text-faint uppercase tracking-[0.08em]">
        {children}
      </span>
      {required && (
        <span className="text-[11px] text-text-faint ml-auto">
          (Required)
        </span>
      )}
    </div>
  );
}
