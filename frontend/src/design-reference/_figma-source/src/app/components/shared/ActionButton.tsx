import { LucideIcon } from 'lucide-react';

interface ActionButtonProps {
  label: string;
  icon: LucideIcon;
  disabled?: boolean;
  onClick?: () => void;
  disabledLabel?: string;
  disabledIcon?: LucideIcon;
}

export function ActionButton({ 
  label, 
  icon: Icon, 
  disabled = false, 
  onClick,
  disabledLabel,
  disabledIcon: DisabledIcon
}: ActionButtonProps) {
  const displayLabel = disabled && disabledLabel ? disabledLabel : label;
  const DisplayIcon = disabled && DisabledIcon ? DisabledIcon : Icon;

  return (
    <button
      className="w-full flex items-center justify-center gap-2 rounded-xl transition-all duration-200"
      disabled={disabled}
      onClick={onClick}
      style={{
        height: '44px',
        backgroundColor: disabled ? '#162033' : '#7C5CFC',
        border: disabled ? '1px solid #1E2D45' : 'none',
        fontSize: '14px',
        fontWeight: 600,
        color: disabled ? '#475569' : 'white',
        cursor: disabled ? 'not-allowed' : 'pointer'
      }}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.backgroundColor = '#8B6EFD';
          e.currentTarget.style.boxShadow = '0 4px 20px rgba(124, 92, 252, 0.4)';
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled) {
          e.currentTarget.style.backgroundColor = '#7C5CFC';
          e.currentTarget.style.boxShadow = 'none';
        }
      }}
    >
      <DisplayIcon size={16} />
      {displayLabel}
    </button>
  );
}
