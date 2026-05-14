import {
  Brain,
  Wrench,
  FileText,
  Lightbulb,
  Target,
  Play,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Loader2,
} from 'lucide-react';
import { cn, formatRelativeTime, formatDuration } from '@/lib/utils';
import type { InvestigationStep } from '@/types';

interface TimelineSummaryProps {
  steps: InvestigationStep[];
  maxSteps?: number;
}

const stepIcons: Record<string, typeof Brain> = {
  thought: Brain,
  tool_call: Wrench,
  tool_result: FileText,
  finding: Lightbulb,
  hypothesis: Target,
  action: Play,
  approval_request: AlertTriangle,
};

const statusIcons: Record<string, typeof CheckCircle> = {
  success: CheckCircle,
  error: XCircle,
  running: Loader2,
  pending: AlertTriangle,
};

export function TimelineSummary({ steps, maxSteps = 5 }: TimelineSummaryProps) {
  const displaySteps = maxSteps ? steps.slice(0, maxSteps) : steps;
  const remaining = steps.length - displaySteps.length;

  return (
    <div className="space-y-3">
      {displaySteps.map((step, index) => {
        const Icon = stepIcons[step.type] || Brain;
        const StatusIcon = step.status ? statusIcons[step.status] : null;

        const iconBgColors: Record<string, string> = {
          thought: 'bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400',
          tool_call: 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
          tool_result: 'bg-cyan-100 dark:bg-cyan-900/30 text-cyan-600 dark:text-cyan-400',
          finding: 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400',
          hypothesis: 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400',
          action: 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400',
          approval_request: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400',
        };

        const statusColors: Record<string, string> = {
          success: 'text-green-500',
          error: 'text-red-500',
          running: 'text-yellow-500 animate-spin',
          pending: 'text-stone-400',
        };

        return (
          <div key={step.id} className="flex items-start gap-3">
            <div
              className={cn(
                'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
                iconBgColors[step.type] || 'bg-stone-100 dark:bg-stone-800 text-stone-500'
              )}
            >
              <Icon className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium text-sm text-stone-900 dark:text-white truncate">
                  {step.title}
                </span>
                {StatusIcon && (
                  <StatusIcon
                    className={cn('w-4 h-4 flex-shrink-0', statusColors[step.status || 'pending'])}
                  />
                )}
              </div>
              <p className="text-xs text-stone-500 dark:text-stone-400 line-clamp-1">
                {step.content}
              </p>
              <div className="flex items-center gap-2 mt-1 text-xs text-stone-400">
                <span>{formatRelativeTime(step.timestamp)}</span>
                {step.duration && <span>• {formatDuration(step.duration)}</span>}
              </div>
            </div>
          </div>
        );
      })}

      {remaining > 0 && (
        <p className="text-sm text-stone-500 dark:text-stone-400 pl-11">
          +{remaining} more step{remaining > 1 ? 's' : ''}
        </p>
      )}
    </div>
  );
}

export default TimelineSummary;
