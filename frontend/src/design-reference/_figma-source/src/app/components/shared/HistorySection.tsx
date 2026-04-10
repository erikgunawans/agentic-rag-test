import { LucideIcon, ShieldCheck, FileText, GitCompare, FilePlus, Clock } from 'lucide-react';

export type BadgeIconVariant = 'shield' | 'file' | 'compare' | 'doc';
export type BadgeColor = 'green' | 'amber' | 'red' | 'purple';

interface HistorySectionProps {
  sectionTitle: string;
  badgeIcon: BadgeIconVariant;
  badgeColor: BadgeColor;
  statusLabel: string;
  emptyStateIcon?: LucideIcon;
  items?: HistoryItem[];
}

interface HistoryItem {
  id: number;
  title: string;
  subtitle: string;
  time: string;
}

export function HistorySection({
  sectionTitle,
  badgeIcon,
  badgeColor,
  statusLabel,
  emptyStateIcon: EmptyIcon = Clock,
  items = []
}: HistorySectionProps) {
  const iconMap: Record<BadgeIconVariant, LucideIcon> = {
    shield: ShieldCheck,
    file: FileText,
    compare: GitCompare,
    doc: FilePlus
  };

  const colorMap: Record<BadgeColor, { bg: string; border: string; text: string }> = {
    green: {
      bg: 'rgba(52, 211, 153, 0.1)',
      border: 'rgba(52, 211, 153, 0.3)',
      text: '#34D399'
    },
    amber: {
      bg: 'rgba(245, 158, 11, 0.1)',
      border: 'rgba(245, 158, 11, 0.3)',
      text: '#F59E0B'
    },
    red: {
      bg: 'rgba(248, 113, 113, 0.1)',
      border: 'rgba(248, 113, 113, 0.3)',
      text: '#F87171'
    },
    purple: {
      bg: 'rgba(124, 92, 252, 0.1)',
      border: 'rgba(124, 92, 252, 0.3)',
      text: '#7C5CFC'
    }
  };

  const BadgeIcon = iconMap[badgeIcon];
  const colors = colorMap[badgeColor];

  return (
    <div
      className="flex flex-col"
      style={{
        height: '223px',
        borderBottom: '1px solid #1E2D45'
      }}
    >
      {/* Section Header */}
      <div
        className="flex items-center justify-between px-5"
        style={{
          height: '48px',
          borderBottom: '1px solid #1E2D45'
        }}
      >
        <div style={{ fontSize: '12px', fontWeight: 600, color: '#94A3B8' }}>
          {sectionTitle}
        </div>
        {/* Status Badge */}
        <div
          className="flex items-center gap-1.5 px-2 rounded-md"
          style={{
            height: '24px',
            backgroundColor: colors.bg,
            border: `1px solid ${colors.border}`
          }}
        >
          <BadgeIcon size={12} style={{ color: colors.text }} />
          <span style={{ fontSize: '11px', fontWeight: 600, color: colors.text }}>
            {statusLabel}
          </span>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {items.length > 0 ? (
          // History Items
          <div className="flex-1 overflow-y-auto">
            {items.map((item) => (
              <button
                key={item.id}
                className="w-full flex flex-col gap-1 px-5 py-3 transition-colors duration-150"
                style={{
                  backgroundColor: 'transparent',
                  borderBottom: '1px solid rgba(30, 45, 69, 0.5)'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#1C2840';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div
                    className="flex-1 truncate"
                    style={{
                      fontSize: '13px',
                      fontWeight: 500,
                      color: '#F1F5F9',
                      textAlign: 'left'
                    }}
                  >
                    {item.title}
                  </div>
                  <div style={{ fontSize: '11px', color: '#475569', flexShrink: 0 }}>
                    {item.time}
                  </div>
                </div>
                <div
                  className="truncate"
                  style={{
                    fontSize: '12px',
                    color: '#64748B',
                    textAlign: 'left'
                  }}
                >
                  {item.subtitle}
                </div>
              </button>
            ))}
          </div>
        ) : (
          // Empty State
          <div className="flex-1 flex flex-col items-center justify-center gap-2">
            <div
              className="flex items-center justify-center rounded-lg"
              style={{
                width: '40px',
                height: '40px',
                backgroundColor: '#162033',
                border: '1px solid #1E2D45'
              }}
            >
              <EmptyIcon size={20} style={{ color: '#475569' }} />
            </div>
            <div style={{ fontSize: '12px', color: '#475569' }}>
              No recent activity
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
