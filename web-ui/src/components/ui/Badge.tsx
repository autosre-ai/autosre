import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { getSeverityColor, getStatusColor } from '@/lib/utils';

interface BadgeProps {
  children: ReactNode;
  variant?: 'default' | 'severity' | 'status';
  value?: string;
  className?: string;
}

export function Badge({ children, variant = 'default', value, className }: BadgeProps) {
  const getVariantStyles = () => {
    if (variant === 'severity' && value) return getSeverityColor(value);
    if (variant === 'status' && value) return getStatusColor(value);
    return 'bg-stone-100 text-stone-700 dark:bg-stone-700 dark:text-stone-300';
  };

  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium', getVariantStyles(), className)}>
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  return <Badge variant="severity" value={severity}>{severity.toUpperCase()}</Badge>;
}

export function StatusBadge({ status }: { status: string }) {
  const displayStatus = status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  return <Badge variant="status" value={status}>{displayStatus}</Badge>;
}
