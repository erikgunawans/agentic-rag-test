import { type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SubHeaderProps {
  title: string;
  subtitle: string;
  icon?: LucideIcon;
  onIconClick?: () => void;
}

export function SubHeader({ title, subtitle, icon: Icon, onIconClick }: SubHeaderProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-between px-5 h-16 shrink-0',
        'border-b border-border-subtle'
      )}
    >
      <div className="flex flex-col gap-0.5">
        <div className="text-[15px] font-semibold text-slate-100">
          {title}
        </div>
        <div className="text-[11px] text-text-faint">
          {subtitle}
        </div>
      </div>
      {Icon && (
        <button
          className={cn(
            'flex items-center justify-center w-7 h-7 rounded-lg',
            'text-slate-400 hover:bg-bg-hover',
            'transition-colors duration-200'
          )}
          onClick={onIconClick}
        >
          <Icon size={14} />
        </button>
      )}
    </div>
  );
}
