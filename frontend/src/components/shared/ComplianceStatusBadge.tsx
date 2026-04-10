import { ShieldCheck, ShieldAlert, ShieldX } from 'lucide-react';
import { cn } from '@/lib/utils';

export type ComplianceStatus = 'pass' | 'review' | 'fail';

interface ComplianceStatusBadgeProps {
  status: ComplianceStatus;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const statusConfig = {
  pass: {
    icon: ShieldCheck,
    label: 'Passed',
    colorClass: 'text-success',
    bgClass: 'bg-success/[0.12]',
  },
  review: {
    icon: ShieldAlert,
    label: 'Review',
    colorClass: 'text-warning',
    bgClass: 'bg-warning/[0.12]',
  },
  fail: {
    icon: ShieldX,
    label: 'Failed',
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

export function ComplianceStatusBadge({
  status,
  size = 'md',
  className,
}: ComplianceStatusBadgeProps) {
  const config = statusConfig[status];
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
