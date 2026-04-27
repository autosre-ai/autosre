import * as React from 'react';
import { cn } from '@/lib/utils';

const badgeVariants = {
  default: 'bg-gray-700 text-gray-100 border-gray-600',
  secondary: 'bg-gray-800 text-gray-300 border-gray-700',
  success: 'bg-green-500/20 text-green-400 border-green-500/50',
  warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
  danger: 'bg-red-500/20 text-red-400 border-red-500/50',
  info: 'bg-blue-500/20 text-blue-400 border-blue-500/50',
  purple: 'bg-purple-500/20 text-purple-400 border-purple-500/50',
  outline: 'text-gray-200 border-gray-600',
};

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: keyof typeof badgeVariants;
}

function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <div
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
        badgeVariants[variant],
        className
      )}
      {...props}
    />
  );
}

// Status-specific badges
export function StatusBadge({ status }: { status: string }) {
  const variants: Record<string, keyof typeof badgeVariants> = {
    running: 'success',
    active: 'success',
    healthy: 'success',
    connected: 'success',
    completed: 'info',
    stopped: 'default',
    pending: 'warning',
    waiting_approval: 'warning',
    initializing: 'warning',
    error: 'danger',
    failed: 'danger',
    critical: 'danger',
  };

  return <Badge variant={variants[status] || 'default'}>{status}</Badge>;
}

export function SeverityBadge({ severity }: { severity: string }) {
  const variants: Record<string, keyof typeof badgeVariants> = {
    critical: 'danger',
    high: 'danger',
    medium: 'warning',
    warning: 'warning',
    low: 'info',
    info: 'info',
  };

  return <Badge variant={variants[severity] || 'default'}>{severity}</Badge>;
}

export function RiskBadge({ risk }: { risk: string }) {
  const variants: Record<string, keyof typeof badgeVariants> = {
    high: 'danger',
    medium: 'warning',
    low: 'success',
  };

  return <Badge variant={variants[risk] || 'default'}>{risk}</Badge>;
}

export { Badge };
