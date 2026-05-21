import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { formatDistanceToNow, format, parseISO } from 'date-fns';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatRelativeTime(dateString: string): string {
  try {
    return formatDistanceToNow(parseISO(dateString), { addSuffix: true });
  } catch {
    return dateString;
  }
}

export function formatDateTime(dateString: string): string {
  try {
    return format(parseISO(dateString), 'MMM d, yyyy h:mm a');
  } catch {
    return dateString;
  }
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 3600000) return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
  return `${Math.floor(ms / 3600000)}h ${Math.floor((ms % 3600000) / 60000)}m`;
}

export function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'critical':
      return 'text-red-500';
    case 'high':
      return 'text-orange-500';
    case 'medium':
    case 'warning':
      return 'text-yellow-500';
    case 'low':
    case 'info':
      return 'text-blue-500';
    default:
      return 'text-gray-500';
  }
}

export function getSeverityBg(severity: string): string {
  switch (severity) {
    case 'critical':
      return 'bg-red-500/10 border-red-500/30';
    case 'high':
      return 'bg-orange-500/10 border-orange-500/30';
    case 'medium':
    case 'warning':
      return 'bg-yellow-500/10 border-yellow-500/30';
    case 'low':
    case 'info':
      return 'bg-blue-500/10 border-blue-500/30';
    default:
      return 'bg-gray-500/10 border-gray-500/30';
  }
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'running':
    case 'active':
    case 'healthy':
      return 'bg-green-500';
    case 'stopped':
    case 'completed':
      return 'bg-blue-500';
    case 'error':
    case 'failed':
      return 'bg-red-500';
    case 'initializing':
    case 'pending':
    case 'waiting_approval':
      return 'bg-yellow-500';
    default:
      return 'bg-gray-500';
  }
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length - 3) + '...';
}
