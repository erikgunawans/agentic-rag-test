import { FileCheck, FileWarning, FileX } from 'lucide-react';
import { cn } from '@/lib/utils';

export type RiskLevel = 'low' | 'medium' | 'high';

interface RiskBadgeProps {
  risk: RiskLevel;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const riskConfig = {
  low: {
    icon: FileCheck,
    label: 'Low Risk',
    colorClass: 'text-success',
    bgClass: 'bg-success/[0.12]',
  },
  medium: {
    icon: FileWarning,
    label: 'Med Risk',
    colorClass: 'text-warning',
    bgClass: 'bg-warning/[0.12]',
  },
  high: {
    icon: FileX,
    label: 'High Risk',
    colorClass: 'text-danger',
    bgClass: 'bg-danger/[0.12]',
  },
} as const;

const sizeConfig = {
  sm: {
    wrapper: 'h-6 px-2 gap-1 rounded-md',
    iconClass: 'size-3',
    textClass: 'text-[11px]',
  },
  md: {
    wrapper: 'h-7 px-2.5 gap-1.5 rounded-md',
    iconClass: 'size-3.5',
    textClass: 'text-xs',
  },
  lg: {
    wrapper: 'h-8 px-3 gap-1.5 rounded-md',
    iconClass: 'size-4',
    textClass: 'text-[13px]',
  },
} as const;

export function RiskBadge({ risk, size = 'md', className }: RiskBadgeProps) {
  const config = riskConfig[risk];
  const sizes = sizeConfig[size];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        'inline-flex items-center w-fit',
        config.bgClass,
        sizes.wrapper,
        className,
      )}
    >
      <Icon className={cn(sizes.iconClass, config.colorClass, 'shrink-0')} />
      <span className={cn(sizes.textClass, 'font-semibold whitespace-nowrap', config.colorClass)}>
        {config.label}
      </span>
    </div>
  );
}
