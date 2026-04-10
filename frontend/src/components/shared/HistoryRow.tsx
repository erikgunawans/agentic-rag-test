import { type ReactNode } from 'react';
import { ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface HistoryRowProps {
  id: number | string;
  badge: ReactNode;
  name: string;
  metaChip: string;
  timestamp: string;
  statusIcon?: ReactNode;
  onClick?: () => void;
}

export function HistoryRow({
  badge,
  name,
  metaChip,
  timestamp,
  statusIcon,
  onClick,
}: HistoryRowProps) {
  return (
    <button
      className={cn(
        'group w-full flex items-center gap-2.5 px-4 h-11 cursor-pointer',
        'transition-colors duration-150 hover:bg-bg-hover'
      )}
      onClick={onClick}
    >
      {/* Badge */}
      {badge}

      {/* Center info */}
      <div className="flex-1 flex flex-col gap-0.5 items-start min-w-0">
        <div className="text-xs font-medium text-slate-100 truncate w-full text-left">
          {name}
        </div>
        <div className="flex items-center gap-1.5">
          <div className="text-[10px] text-text-faint bg-bg-elevated px-1.5 py-px rounded">
            {metaChip}
          </div>
          <div className="w-[3px] h-[3px] rounded-full bg-text-faint" />
          <div className="text-[10px] text-text-faint">{timestamp}</div>
        </div>
      </div>

      {/* Right: status icon or chevron on hover */}
      <div className="shrink-0">
        <ChevronRight
          size={14}
          className="text-text-faint hidden group-hover:block"
        />
        <span className="group-hover:hidden">{statusIcon}</span>
      </div>
    </button>
  );
}
