import { cn } from '@/lib/utils';

export type AnalysisDepth = 'quick' | 'standard' | 'deep';

interface AnalysisDepthControlProps {
  value: AnalysisDepth;
  onChange?: (value: AnalysisDepth) => void;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const options: { value: AnalysisDepth; label: string }[] = [
  { value: 'quick', label: 'Quick' },
  { value: 'standard', label: 'Standard' },
  { value: 'deep', label: 'Deep' },
];

const sizeConfig = {
  sm: {
    wrapper: 'h-8 p-[3px] gap-0.5',
    button: 'min-w-16 text-[11px]',
  },
  md: {
    wrapper: 'h-10 p-1 gap-[3px]',
    button: 'min-w-20 text-[13px]',
  },
  lg: {
    wrapper: 'h-12 p-[5px] gap-1',
    button: 'min-w-24 text-sm',
  },
} as const;

export function AnalysisDepthControl({
  value,
  onChange,
  size = 'md',
  className,
}: AnalysisDepthControlProps) {
  const sizes = sizeConfig[size];

  return (
    <div
      className={cn(
        'inline-flex items-center rounded-xl bg-bg-deep border border-border-subtle w-fit',
        sizes.wrapper,
        className,
      )}
    >
      {options.map((option) => {
        const isActive = value === option.value;
        return (
          <button
            key={option.value}
            onClick={() => onChange?.(option.value)}
            className={cn(
              'flex items-center justify-center rounded-[10px] transition-all duration-200 h-full font-semibold cursor-pointer',
              sizes.button,
              isActive
                ? 'bg-bg-surface text-slate-100 shadow-[0_1px_4px_rgba(0,0,0,0.3)]'
                : 'bg-transparent text-text-faint hover:text-slate-300',
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
