import { type LucideIcon, ChevronLeft, X, ArrowLeft, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';

export type RightIconVariant = 'chevron-left' | 'close' | 'arrow-left' | 'settings' | 'none';

interface ColumnHeaderProps {
  title: string;
  subtitle?: string;
  rightIcon?: RightIconVariant;
  onRightIconClick?: () => void;
}

export function ColumnHeader({
  title,
  subtitle,
  rightIcon = 'chevron-left',
  onRightIconClick,
}: ColumnHeaderProps) {
  const iconMap: Record<RightIconVariant, LucideIcon | null> = {
    'chevron-left': ChevronLeft,
    'close': X,
    'arrow-left': ArrowLeft,
    'settings': Settings,
    'none': null,
  };

  const Icon = rightIcon !== 'none' ? iconMap[rightIcon] : null;

  return (
    <div
      className={cn(
        'flex items-center justify-between h-16 px-5',
        'bg-bg-surface border-b border-border-subtle'
      )}
    >
      {/* Left: Title and Subtitle */}
      <div className="flex flex-col gap-0.5">
        <div className="text-sm font-semibold text-slate-100">
          {title}
        </div>
        {subtitle && (
          <div className="text-xs text-slate-400">
            {subtitle}
          </div>
        )}
      </div>

      {/* Right: Icon Button */}
      {Icon && (
        <button
          onClick={onRightIconClick}
          className={cn(
            'flex items-center justify-center w-8 h-8 rounded-lg',
            'text-slate-400 hover:bg-bg-hover hover:text-slate-100',
            'transition-colors duration-200'
          )}
        >
          <Icon size={20} />
        </button>
      )}
    </div>
  );
}
