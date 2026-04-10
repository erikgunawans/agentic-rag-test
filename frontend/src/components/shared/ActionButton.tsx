import { type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface ActionButtonProps {
  label: string;
  icon: LucideIcon;
  disabled?: boolean;
  onClick?: () => void;
  disabledLabel?: string;
  disabledIcon?: LucideIcon;
  className?: string;
}

export function ActionButton({
  label,
  icon: Icon,
  disabled = false,
  onClick,
  disabledLabel,
  disabledIcon: DisabledIcon,
  className,
}: ActionButtonProps) {
  const displayLabel = disabled && disabledLabel ? disabledLabel : label;
  const DisplayIcon = disabled && DisabledIcon ? DisabledIcon : Icon;

  return (
    <Button
      className={cn(
        'w-full h-11 gap-2 rounded-xl text-sm font-semibold transition-all duration-200',
        disabled
          ? 'bg-bg-deep border border-border-subtle text-text-faint cursor-not-allowed'
          : 'bg-accent-primary border-transparent text-white hover:bg-accent-primary/90 hover:shadow-[0_4px_20px_rgba(124,92,252,0.4)]',
        className,
      )}
      disabled={disabled}
      onClick={onClick}
    >
      <DisplayIcon className="size-4" />
      {displayLabel}
    </Button>
  );
}
