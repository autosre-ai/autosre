import { type ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { AlertCircle, Info, CheckCircle2, AlertTriangle } from 'lucide-react';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-12 text-center', className)}>
      {icon && (
        <div className="w-12 h-12 rounded-full bg-stone-100 dark:bg-stone-800 flex items-center justify-center mb-4">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-semibold text-stone-900 dark:text-white">{title}</h3>
      {description && (
        <p className="mt-1 text-sm text-stone-500 max-w-sm">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// Alert component for inline messages
interface AlertProps {
  variant?: 'info' | 'success' | 'warning' | 'error';
  title?: string;
  children: ReactNode;
  className?: string;
}

export function Alert({ variant = 'info', title, children, className }: AlertProps) {
  const variants = {
    info: {
      bg: 'bg-blue-50 dark:bg-blue-900/20',
      border: 'border-blue-200 dark:border-blue-800',
      icon: <Info className="w-5 h-5 text-blue-500" />,
      title: 'text-blue-800 dark:text-blue-300',
      text: 'text-blue-700 dark:text-blue-400',
    },
    success: {
      bg: 'bg-green-50 dark:bg-green-900/20',
      border: 'border-green-200 dark:border-green-800',
      icon: <CheckCircle2 className="w-5 h-5 text-green-500" />,
      title: 'text-green-800 dark:text-green-300',
      text: 'text-green-700 dark:text-green-400',
    },
    warning: {
      bg: 'bg-yellow-50 dark:bg-yellow-900/20',
      border: 'border-yellow-200 dark:border-yellow-800',
      icon: <AlertTriangle className="w-5 h-5 text-yellow-500" />,
      title: 'text-yellow-800 dark:text-yellow-300',
      text: 'text-yellow-700 dark:text-yellow-400',
    },
    error: {
      bg: 'bg-red-50 dark:bg-red-900/20',
      border: 'border-red-200 dark:border-red-800',
      icon: <AlertCircle className="w-5 h-5 text-red-500" />,
      title: 'text-red-800 dark:text-red-300',
      text: 'text-red-700 dark:text-red-400',
    },
  };

  const styles = variants[variant];

  return (
    <div className={cn('rounded-lg border p-4', styles.bg, styles.border, className)}>
      <div className="flex gap-3">
        {styles.icon}
        <div className="flex-1">
          {title && <h4 className={cn('font-semibold mb-1', styles.title)}>{title}</h4>}
          <div className={cn('text-sm', styles.text)}>{children}</div>
        </div>
      </div>
    </div>
  );
}
