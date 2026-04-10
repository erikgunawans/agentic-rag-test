import { LucideIcon, ChevronLeft, X, ArrowLeft, Settings } from 'lucide-react';

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
  onRightIconClick 
}: ColumnHeaderProps) {
  const iconMap: Record<RightIconVariant, LucideIcon | null> = {
    'chevron-left': ChevronLeft,
    'close': X,
    'arrow-left': ArrowLeft,
    'settings': Settings,
    'none': null
  };

  const Icon = rightIcon !== 'none' ? iconMap[rightIcon] : null;

  return (
    <div 
      className="flex items-center justify-between"
      style={{
        height: '64px',
        backgroundColor: '#0F1829',
        borderBottom: '1px solid #1E2D45',
        padding: '0 20px'
      }}
    >
      {/* Left: Title and Subtitle */}
      <div className="flex flex-col gap-0.5">
        <div style={{ fontSize: '14px', fontWeight: 600, color: '#F1F5F9' }}>
          {title}
        </div>
        {subtitle && (
          <div style={{ fontSize: '12px', color: '#94A3B8' }}>
            {subtitle}
          </div>
        )}
      </div>

      {/* Right: Icon Button */}
      {Icon && (
        <button 
          onClick={onRightIconClick}
          className="flex items-center justify-center rounded-lg transition-colors duration-200"
          style={{
            width: '32px',
            height: '32px',
            color: '#94A3B8'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#1C2840';
            e.currentTarget.style.color = '#F1F5F9';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
            e.currentTarget.style.color = '#94A3B8';
          }}
        >
          <Icon size={20} />
        </button>
      )}
    </div>
  );
}
