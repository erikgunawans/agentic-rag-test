import { LucideIcon } from 'lucide-react';

interface IconRailItemProps {
  icon: LucideIcon;
  isActive: boolean;
  onClick: () => void;
}

export function IconRailItem({ icon: Icon, isActive, onClick }: IconRailItemProps) {
  return (
    <button
      className="flex items-center justify-center transition-all duration-200"
      style={{
        width: '36px',
        height: '36px',
        borderRadius: '8px',
        backgroundColor: isActive ? 'rgba(124, 92, 252, 0.12)' : 'transparent',
        color: isActive ? '#7C5CFC' : '#475569',
        cursor: 'pointer',
        boxShadow: isActive ? '0 0 16px rgba(124, 92, 252, 0.3)' : 'none'
      }}
      onClick={onClick}
      onMouseEnter={(e) => {
        if (!isActive) {
          e.currentTarget.style.backgroundColor = '#1C2840';
          e.currentTarget.style.color = '#94A3B8';
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive) {
          e.currentTarget.style.backgroundColor = 'transparent';
          e.currentTarget.style.color = '#475569';
        }
      }}
    >
      <Icon size={18} />
    </button>
  );
}

interface IconRailProps {
  items: Array<{
    icon: LucideIcon;
    isActive: boolean;
    onClick: () => void;
  }>;
}

export function IconRail({ items }: IconRailProps) {
  return (
    <div
      className="flex flex-col items-center gap-2"
      style={{
        width: '56px',
        backgroundColor: '#0F1829',
        borderRight: '1px solid #1E2D45',
        paddingTop: '16px',
        height: '900px'
      }}
    >
      {items.map((item, index) => (
        <IconRailItem key={index} {...item} />
      ))}
    </div>
  );
}
