import { cn } from '@/lib/utils';

interface HintChip {
  color: string;
  label: string;
}

interface HintChipRowProps {
  chips: [HintChip, HintChip, HintChip];
  className?: string;
}

export function HintChipRow({ chips, className }: HintChipRowProps) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      {chips.map((chip, index) => (
        <div
          key={index}
          className="flex items-center gap-1.5 h-[26px] px-2.5 rounded-full bg-bg-deep border border-border-subtle text-[11px] text-text-faint"
        >
          <div
            className="size-1.5 rounded-full shrink-0"
            style={{ backgroundColor: chip.color }}
          />
          {chip.label}
        </div>
      ))}
    </div>
  );
}
