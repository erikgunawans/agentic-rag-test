import { ShieldCheck, ShieldAlert, ShieldX } from 'lucide-react';

export type ComplianceStatus = 'pass' | 'review' | 'fail';

interface ComplianceStatusBadgeProps {
  status: ComplianceStatus;
  size?: 'sm' | 'md' | 'lg';
}

export function ComplianceStatusBadge({ status, size = 'md' }: ComplianceStatusBadgeProps) {
  const config = {
    pass: {
      icon: ShieldCheck,
      label: 'Passed',
      color: '#34D399',
      backgroundColor: 'rgba(52, 211, 153, 0.12)'
    },
    review: {
      icon: ShieldAlert,
      label: 'Review',
      color: '#F59E0B',
      backgroundColor: 'rgba(245, 158, 11, 0.12)'
    },
    fail: {
      icon: ShieldX,
      label: 'Failed',
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

  const statusConfig = config[status];
  const sizes = sizeConfig[size];
  const Icon = statusConfig.icon;

  return (
    <div
      className="flex items-center"
      style={{
        height: sizes.height,
        padding: sizes.padding,
        backgroundColor: statusConfig.backgroundColor,
        borderRadius: '6px',
        gap: `${sizes.gap}`,
        width: 'fit-content'
      }}
    >
      <Icon size={sizes.iconSize} style={{ color: statusConfig.color, flexShrink: 0 }} />
      <span
        style={{
          fontSize: sizes.fontSize,
          fontWeight: 600,
          color: statusConfig.color,
          whiteSpace: 'nowrap'
        }}
      >
        {statusConfig.label}
      </span>
    </div>
  );
}
