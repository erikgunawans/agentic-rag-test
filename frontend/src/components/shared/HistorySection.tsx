import { type LucideIcon, ShieldCheck, FileText, GitCompare, FilePlus, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

export type BadgeIconVariant = 'shield' | 'file' | 'compare' | 'doc';
export type BadgeColor = 'green' | 'amber' | 'red' | 'purple';

interface HistoryItem {
  id: number;
  title: string;
  subtitle: string;
  time: string;
}

interface HistorySectionProps {
  sectionTitle: string;
  badgeIcon: BadgeIconVariant;
  badgeColor: BadgeColor;
  statusLabel: string;
  emptyStateIcon?: LucideIcon;
  items?: HistoryItem[];
}

const iconMap: Record<BadgeIconVariant, LucideIcon> = {
  shield: ShieldCheck,
  file: FileText,
  compare: GitCompare,
  doc: FilePlus,
};

const colorMap: Record<BadgeColor, { bg: string; border: string; text: string }> = {
  green: {
    bg: 'bg-success/10',
    border: 'border-success/30',
    text: 'text-success',
  },
  amber: {
    bg: 'bg-warning/10',
    border: 'border-warning/30',
    text: 'text-warning',
  },
  red: {
    bg: 'bg-danger/10',
    border: 'border-danger/30',
    text: 'text-danger',
  },
  purple: {
    bg: 'bg-accent-primary/10',
    border: 'border-accent-primary/30',
    text: 'text-accent-primary',
  },
};

export function HistorySection({
  sectionTitle,
  badgeIcon,
  badgeColor,
  statusLabel,
  emptyStateIcon: EmptyIcon = Clock,
  items = [],
}: HistorySectionProps) {
  const BadgeIcon = iconMap[badgeIcon];
  const colors = colorMap[badgeColor];

  return (
    <div className="flex flex-col h-[223px] border-b border-border-subtle">
      {/* Section Header */}
      <div className="flex items-center justify-between px-5 h-12 border-b border-border-subtle">
        <div className="text-xs font-semibold text-slate-400">
          {sectionTitle}
        </div>
        {/* Status Badge */}
        <div
          className={cn(
            'flex items-center gap-1.5 px-2 h-6 rounded-md border',
            colors.bg,
            colors.border
          )}
        >
          <BadgeIcon size={12} className={colors.text} />
          <span className={cn('text-[11px] font-semibold', colors.text)}>
            {statusLabel}
          </span>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {items.length > 0 ? (
          <div className="flex-1 overflow-y-auto scrollbar-kh">
            {items.map((item) => (
              <button
                key={item.id}
                className={cn(
                  'group w-full flex flex-col gap-1 px-5 py-3',
                  'border-b border-border-subtle/50',
                  'transition-colors duration-150 hover:bg-bg-hover'
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 truncate text-[13px] font-medium text-slate-100 text-left">
                    {item.title}
                  </div>
                  <div className="text-[11px] text-text-faint shrink-0">
                    {item.time}
                  </div>
                </div>
                <div className="truncate text-xs text-slate-500 text-left">
                  {item.subtitle}
                </div>
              </button>
            ))}
          </div>
        ) : (
          /* Empty State */
          <div className="flex-1 flex flex-col items-center justify-center gap-2">
            <div
              className={cn(
                'flex items-center justify-center w-10 h-10 rounded-lg',
                'bg-bg-elevated border border-border-subtle'
              )}
            >
              <EmptyIcon size={20} className="text-text-faint" />
            </div>
            <div className="text-xs text-text-faint">
              No recent activity
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
