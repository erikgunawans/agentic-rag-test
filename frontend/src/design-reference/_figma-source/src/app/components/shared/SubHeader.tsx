import { LucideIcon } from 'lucide-react';

interface SubHeaderProps {
  title: string;
  subtitle: string;
  icon?: LucideIcon;
  onIconClick?: () => void;
}

export function SubHeader({ title, subtitle, icon: Icon, onIconClick }: SubHeaderProps) {
  return (
    <div
      className="flex items-center justify-between px-5"
      style={{
        height: '64px',
        borderBottom: '1px solid #1E2D45',
        flexShrink: 0
      }}
    >
      <div className="flex flex-col gap-0.5">
        <div style={{ fontSize: '15px', fontWeight: 600, color: '#F1F5F9' }}>
          {title}
        </div>
        <div style={{ fontSize: '11px', color: '#475569' }}>
          {subtitle}
        </div>
      </div>
      {Icon && (
        <button
          className="flex items-center justify-center rounded-lg transition-colors duration-200"
          style={{
            width: '28px',
            height: '28px',
            color: '#94A3B8'
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#1C2840')}
          onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          onClick={onIconClick}
        >
          <Icon size={14} />
        </button>
      )}
    </div>
  );
}
