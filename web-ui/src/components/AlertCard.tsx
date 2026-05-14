import { cn, formatRelativeTime } from '@/lib/utils';
import {
  AlertTriangle,
  AlertCircle,
  Info,
  Clock,
  ExternalLink,
  Zap,
  Server,
  Database,
  Globe,
  Activity,
} from 'lucide-react';
import { Badge, SeverityBadge, StatusBadge } from './ui';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from './ui';
import type { Alert, AlertUI } from '@/types';

// Accept both Alert and AlertUI (which may have title/startsAt aliases)
type AlertLike = Alert | AlertUI;

interface AlertCardProps {
  alert: AlertLike;
  onClick?: () => void;
  selected?: boolean;
  compact?: boolean;
  className?: string;
}

const severityIcons = {
  critical: AlertCircle,
  high: AlertTriangle,
  medium: AlertTriangle,
  low: Info,
  info: Info,
};

const severityColors = {
  critical: 'border-l-red-500',
  high: 'border-l-orange-500',
  medium: 'border-l-yellow-500',
  low: 'border-l-blue-500',
  info: 'border-l-stone-400',
};

const sourceIcons: Record<string, typeof Server> = {
  prometheus: Activity,
  datadog: Zap,
  pagerduty: AlertTriangle,
  cloudwatch: Globe,
  database: Database,
  default: Server,
};

// Helper to get display name (supports both name and title fields)
function getDisplayName(alert: AlertLike): string {
  return (alert as AlertUI).title || alert.name;
}

// Helper to get fired/started time (supports both startedAt and startsAt)
function getStartedAt(alert: AlertLike): string {
  return alert.startedAt || (alert as AlertUI).startsAt || '';
}

export function AlertCard({
  alert,
  onClick,
  selected = false,
  compact = false,
  className,
}: AlertCardProps) {
  const SeverityIcon = severityIcons[alert.severity] || AlertTriangle;
  const SourceIcon = sourceIcons[alert.source?.toLowerCase() || 'default'] || Server;
  const displayName = getDisplayName(alert);
  const startedAt = getStartedAt(alert);

  if (compact) {
    return (
      <div
        onClick={onClick}
        className={cn(
          'flex items-center gap-3 p-3 rounded-lg border transition-all cursor-pointer',
          'border-stone-200 dark:border-stone-700',
          'hover:border-stone-300 dark:hover:border-stone-600',
          'bg-white dark:bg-stone-800',
          selected && 'ring-2 ring-forest ring-offset-2 dark:ring-offset-stone-900',
          className
        )}
      >
        <div
          className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
            alert.severity === 'critical' && 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400',
            alert.severity === 'high' && 'bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400',
            alert.severity === 'medium' && 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400',
            alert.severity === 'low' && 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
            alert.severity === 'info' && 'bg-stone-100 dark:bg-stone-700 text-stone-500'
          )}
        >
          <SeverityIcon className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm text-stone-900 dark:text-white truncate">
            {displayName}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-stone-500 truncate">{alert.service}</span>
            <span className="text-stone-400">•</span>
            <span className="text-xs text-stone-400">
              {startedAt && formatRelativeTime(startedAt)}
            </span>
          </div>
        </div>
        <StatusBadge status={alert.status} />
      </div>
    );
  }

  return (
    <Card
      onClick={onClick}
      className={cn(
        'border-l-4 cursor-pointer transition-all hover:shadow-md',
        severityColors[alert.severity],
        selected && 'ring-2 ring-forest ring-offset-2 dark:ring-offset-stone-900',
        className
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <div
              className={cn(
                'w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0',
                alert.severity === 'critical' && 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400',
                alert.severity === 'high' && 'bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400',
                alert.severity === 'medium' && 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400',
                alert.severity === 'low' && 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
                alert.severity === 'info' && 'bg-stone-100 dark:bg-stone-700 text-stone-500'
              )}
            >
              <SeverityIcon className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <CardTitle className="text-base">{displayName}</CardTitle>
              {alert.description && (
                <p className="text-sm text-stone-500 dark:text-stone-400 mt-1 line-clamp-2">
                  {alert.description}
                </p>
              )}
            </div>
          </div>
          <div className="flex flex-col items-end gap-2 flex-shrink-0">
            <SeverityBadge severity={alert.severity} />
            <StatusBadge status={alert.status} />
          </div>
        </div>
      </CardHeader>

      <CardContent className="py-3">
        <div className="flex flex-wrap gap-2">
          {alert.service && (
            <Badge variant="default" className="text-xs">
              <Server className="w-3 h-3 mr-1" />
              {alert.service}
            </Badge>
          )}
          {alert.namespace && (
            <Badge variant="default" className="text-xs">
              <Globe className="w-3 h-3 mr-1" />
              {alert.namespace}
            </Badge>
          )}
          {alert.source && (
            <Badge variant="default" className="text-xs">
              <SourceIcon className="w-3 h-3 mr-1" />
              {alert.source}
            </Badge>
          )}
        </div>

        {alert.labels && Object.keys(alert.labels).length > 0 && (
          <div className="flex flex-wrap gap-1 mt-3">
            {Object.entries(alert.labels).slice(0, 4).map(([key, value]) => (
              <span
                key={key}
                className="px-2 py-0.5 text-xs bg-stone-100 dark:bg-stone-700 text-stone-600 dark:text-stone-300 rounded"
              >
                {key}: {value}
              </span>
            ))}
            {Object.keys(alert.labels).length > 4 && (
              <span className="px-2 py-0.5 text-xs text-stone-500">
                +{Object.keys(alert.labels).length - 4} more
              </span>
            )}
          </div>
        )}
      </CardContent>

      <CardFooter className="pt-2 border-t border-stone-100 dark:border-stone-700">
        <div className="flex items-center justify-between w-full text-xs text-stone-500">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              Fired {startedAt && formatRelativeTime(startedAt)}
            </span>
            {alert.resolvedAt && (
              <span>Resolved {formatRelativeTime(alert.resolvedAt)}</span>
            )}
          </div>
          {alert.runbookUrl && (
            <a
              href={alert.runbookUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1 text-forest hover:underline"
            >
              Runbook
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
      </CardFooter>
    </Card>
  );
}

// Mini variant for list views
export function AlertCardMini({ alert, onClick }: { alert: AlertLike; onClick?: () => void }) {
  const SeverityIcon = severityIcons[alert.severity] || AlertTriangle;
  const displayName = getDisplayName(alert);
  const startedAt = getStartedAt(alert);

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-2 p-2 rounded text-left transition-colors',
        'hover:bg-stone-100 dark:hover:bg-stone-800'
      )}
    >
      <SeverityIcon
        className={cn(
          'w-4 h-4 flex-shrink-0',
          alert.severity === 'critical' && 'text-red-500',
          alert.severity === 'high' && 'text-orange-500',
          alert.severity === 'medium' && 'text-yellow-500',
          alert.severity === 'low' && 'text-blue-500',
          alert.severity === 'info' && 'text-stone-400'
        )}
      />
      <span className="flex-1 text-sm truncate text-stone-700 dark:text-stone-300">
        {displayName}
      </span>
      <span className="text-xs text-stone-400">
        {startedAt && formatRelativeTime(startedAt)}
      </span>
    </button>
  );
}

export default AlertCard;
