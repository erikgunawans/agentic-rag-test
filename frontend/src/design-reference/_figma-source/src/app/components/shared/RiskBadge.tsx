import { FileCheck, FileWarning, FileX } from 'lucide-react';

export type RiskLevel = 'low' | 'medium' | 'high';

interface RiskBadgeProps {
  risk: RiskLevel;
  size?: 'sm' | 'md' | 'lg';
}

export function RiskBadge({ risk, size = 'md' }: RiskBadgeProps) {
  const config = {
    low: {
      icon: FileCheck,
      label: 'Low Risk',
      color: '#34D399',
      backgroundColor: 'rgba(52, 211, 153, 0.12)'
    },
    medium: {
      icon: FileWarning,
      label: 'Med Risk',
      color: '#F59E0B',
      backgroundColor: 'rgba(245, 158, 11, 0.12)'
    },
    high: {
      icon: FileX,
      label: 'High Risk',
      color: '#F87171',
      backgroundColor: 'rgba(248, 113, 113, 0.12)'
    }
  };

  const sizeConfig = {
    sm: {
      height: '24px',
      padding: '0 8px',
      iconSize: 12,
      fontSize: '11px',
      gap: '4px'
    },
    md: {
      height: '28px',
      padding: '0 10px',
      iconSize: 14,
      fontSize: '12px',
      gap: '6px'
    },
    lg: {
      height: '32px',
      padding: '0 12px',
      iconSize: 16,
      fontSize: '13px',
      gap: '6px'
    }
  };

  const riskConfig = config[risk];
  const sizes = sizeConfig[size];
  const Icon = riskConfig.icon;

  return (
    <div
      className="flex items-center"
      style={{
        height: sizes.height,
        padding: sizes.padding,
        backgroundColor: riskConfig.backgroundColor,
        borderRadius: '6px',
        gap: `${sizes.gap}`,
        width: 'fit-content'
      }}
    >
      <Icon size={sizes.iconSize} style={{ color: riskConfig.color, flexShrink: 0 }} />
      <span
        style={{
          fontSize: sizes.fontSize,
          fontWeight: 600,
          color: riskConfig.color,
          whiteSpace: 'nowrap'
        }}
      >
        {riskConfig.label}
      </span>
    </div>
  );
}
