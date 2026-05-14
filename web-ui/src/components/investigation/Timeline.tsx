import { useState } from 'react';
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
  Clock,
  ChevronDown,
  ChevronRight,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui';
import { formatRelativeTime, formatDuration, cn } from '@/lib/utils';
import type { InvestigationStep } from '@/types';

interface TimelineProps {
  steps: InvestigationStep[];
  onApprove?: (stepId: string) => void;
  onReject?: (stepId: string) => void;
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

const stepLabels: Record<string, string> = {
  thought: 'Thinking',
  tool_call: 'Executing',
  tool_result: 'Result',
  finding: 'Finding',
  hypothesis: 'Hypothesis',
  action: 'Action',
  approval_request: 'Approval Required',
};

const statusIcons: Record<string, typeof CheckCircle> = {
  success: CheckCircle,
  error: XCircle,
  running: Loader2,
  pending: Clock,
};

export function Timeline({ steps, onApprove, onReject }: TimelineProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(
    new Set(steps.slice(-3).map((s) => s.id)) // Expand last 3 by default
  );

  const toggleStep = (stepId: string) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(stepId)) {
        next.delete(stepId);
      } else {
        next.add(stepId);
      }
      return next;
    });
  };

  const expandAll = () => setExpandedSteps(new Set(steps.map((s) => s.id)));
  const collapseAll = () => setExpandedSteps(new Set());

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-stone-500 dark:text-stone-400">
          {steps.length} steps
        </span>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={expandAll}>
            Expand All
          </Button>
          <Button variant="ghost" size="sm" onClick={collapseAll}>
            Collapse All
          </Button>
        </div>
      </div>

      {/* Timeline */}
      <div className="relative">
        {steps.map((step, index) => (
          <TimelineItem
            key={step.id}
            step={step}
            isLast={index === steps.length - 1}
            isExpanded={expandedSteps.has(step.id)}
            onToggle={() => toggleStep(step.id)}
            onApprove={onApprove}
            onReject={onReject}
          />
        ))}
      </div>
    </div>
  );
}

interface TimelineItemProps {
  step: InvestigationStep;
  isLast: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  onApprove?: (stepId: string) => void;
  onReject?: (stepId: string) => void;
}

function TimelineItem({
  step,
  isLast,
  isExpanded,
  onToggle,
  onApprove,
  onReject,
}: TimelineItemProps) {
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

  const lineColors: Record<string, string> = {
    success: 'bg-green-500',
    error: 'bg-red-500',
    running: 'bg-yellow-500',
    pending: 'bg-stone-300 dark:bg-stone-600',
  };

  const isApprovalPending = step.type === 'approval_request' && step.status === 'pending';

  return (
    <div className="flex gap-4 group">
      {/* Timeline line and icon */}
      <div className="flex flex-col items-center w-10 flex-shrink-0">
        <div
          className={cn(
            'w-10 h-10 rounded-xl flex items-center justify-center z-10 transition-transform group-hover:scale-110',
            iconBgColors[step.type] || 'bg-stone-100 dark:bg-stone-800 text-stone-500'
          )}
        >
          <Icon className="w-5 h-5" />
        </div>
        {!isLast && (
          <div
            className={cn(
              'w-0.5 flex-1 min-h-[24px] transition-colors',
              lineColors[step.status || 'pending']
            )}
          />
        )}
      </div>

      {/* Content */}
      <div className={cn('flex-1 pb-6', isLast && 'pb-0')}>
        {/* Header - always visible */}
        <button
          onClick={onToggle}
          className="w-full text-left group/header"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-medium text-stone-500 dark:text-stone-400 uppercase tracking-wider">
                {stepLabels[step.type] || step.type}
              </span>
              {StatusIcon && (
                <StatusIcon
                  className={cn('w-4 h-4', statusColors[step.status || 'pending'])}
                />
              )}
              {step.duration && (
                <span className="text-xs text-stone-400 dark:text-stone-500">
                  {formatDuration(step.duration)}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-stone-400 dark:text-stone-500">
                {formatRelativeTime(step.timestamp)}
              </span>
              {isExpanded ? (
                <ChevronDown className="w-4 h-4 text-stone-400 group-hover/header:text-stone-600 dark:group-hover/header:text-stone-300" />
              ) : (
                <ChevronRight className="w-4 h-4 text-stone-400 group-hover/header:text-stone-600 dark:group-hover/header:text-stone-300" />
              )}
            </div>
          </div>
          <h4 className="font-semibold text-stone-900 dark:text-white mt-1">
            {step.title}
          </h4>
        </button>

        {/* Expandable content */}
        {isExpanded && (
          <div className="mt-3 animate-in slide-in-from-top-2 duration-200">
            {step.type === 'tool_call' || step.type === 'tool_result' ? (
              <pre className="text-sm bg-stone-900 dark:bg-stone-950 text-stone-100 p-4 rounded-lg overflow-x-auto font-mono">
                <code>{step.content}</code>
              </pre>
            ) : isApprovalPending ? (
              <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
                <p className="text-sm text-yellow-800 dark:text-yellow-200 mb-4">
                  {step.content}
                </p>
                <div className="flex items-center gap-3">
                  <Button
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      onApprove?.(step.id);
                    }}
                  >
                    <CheckCircle className="w-4 h-4 mr-1.5" />
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={(e) => {
                      e.stopPropagation();
                      onReject?.(step.id);
                    }}
                  >
                    <XCircle className="w-4 h-4 mr-1.5" />
                    Reject
                  </Button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-stone-600 dark:text-stone-400 leading-relaxed">
                {step.content}
              </p>
            )}

            {/* Metadata */}
            {step.metadata && Object.keys(step.metadata).length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(step.metadata).map(([key, value]) => (
                  <span
                    key={key}
                    className="inline-flex items-center px-2 py-1 rounded-md bg-stone-100 dark:bg-stone-800 text-xs text-stone-600 dark:text-stone-400"
                  >
                    <span className="font-medium">{key}:</span>
                    <span className="ml-1">{String(value)}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Collapsed preview */}
        {!isExpanded && (
          <p className="text-sm text-stone-500 dark:text-stone-400 mt-1 line-clamp-1">
            {step.content}
          </p>
        )}
      </div>
    </div>
  );
}

export default Timeline;
