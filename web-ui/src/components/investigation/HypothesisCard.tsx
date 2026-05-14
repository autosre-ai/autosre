import { useState } from 'react';
import {
  Target,
  ChevronDown,
  ChevronUp,
  ThumbsUp,
  ThumbsDown,
  ExternalLink,
  Lightbulb,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';
import { Button, Card, CardContent } from '@/components/ui';
import { cn } from '@/lib/utils';

export interface Hypothesis {
  id: string;
  title: string;
  description: string;
  confidence: number; // 0-100
  status: 'investigating' | 'confirmed' | 'rejected' | 'pending';
  evidence: string[];
  suggestedActions?: string[];
}

interface HypothesisCardProps {
  hypothesis: Hypothesis;
  onConfirm?: (id: string) => void;
  onReject?: (id: string) => void;
  onInvestigate?: (id: string) => void;
}

export function HypothesisCard({
  hypothesis,
  onConfirm,
  onReject,
  onInvestigate,
}: HypothesisCardProps) {
  const [isExpanded, setIsExpanded] = useState(hypothesis.status === 'confirmed');

  const confidenceColor = getConfidenceColor(hypothesis.confidence);
  const statusConfig = getStatusConfig(hypothesis.status);

  return (
    <Card
      className={cn(
        'overflow-hidden transition-all duration-300',
        hypothesis.status === 'confirmed' && 'ring-2 ring-green-500 dark:ring-green-400',
        hypothesis.status === 'rejected' && 'opacity-60'
      )}
    >
      <CardContent className="p-0">
        {/* Header */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full p-4 text-left hover:bg-stone-50 dark:hover:bg-stone-800/50 transition-colors"
        >
          <div className="flex items-start gap-4">
            {/* Confidence indicator */}
            <div className="flex-shrink-0">
              <div className="relative w-14 h-14">
                <svg className="w-14 h-14 -rotate-90" viewBox="0 0 36 36">
                  <circle
                    cx="18"
                    cy="18"
                    r="15.9155"
                    fill="none"
                    className="stroke-stone-200 dark:stroke-stone-700"
                    strokeWidth="3"
                  />
                  <circle
                    cx="18"
                    cy="18"
                    r="15.9155"
                    fill="none"
                    className={confidenceColor.stroke}
                    strokeWidth="3"
                    strokeDasharray={`${hypothesis.confidence}, 100`}
                    strokeLinecap="round"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className={cn('text-sm font-bold', confidenceColor.text)}>
                    {hypothesis.confidence}%
                  </span>
                </div>
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={cn(
                    'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
                    statusConfig.bg,
                    statusConfig.text
                  )}
                >
                  <statusConfig.icon className="w-3 h-3" />
                  {statusConfig.label}
                </span>
              </div>
              <h4 className="font-semibold text-stone-900 dark:text-white">
                {hypothesis.title}
              </h4>
              <p className="text-sm text-stone-500 dark:text-stone-400 mt-1 line-clamp-2">
                {hypothesis.description}
              </p>
            </div>

            {/* Expand indicator */}
            <div className="flex-shrink-0 pt-2">
              {isExpanded ? (
                <ChevronUp className="w-5 h-5 text-stone-400" />
              ) : (
                <ChevronDown className="w-5 h-5 text-stone-400" />
              )}
            </div>
          </div>
        </button>

        {/* Expanded content */}
        {isExpanded && (
          <div className="px-4 pb-4 animate-in slide-in-from-top-2 duration-200">
            <div className="pl-18 space-y-4">
              {/* Evidence */}
              {hypothesis.evidence.length > 0 && (
                <div>
                  <h5 className="text-xs font-semibold text-stone-500 dark:text-stone-400 uppercase tracking-wider mb-2">
                    Supporting Evidence
                  </h5>
                  <ul className="space-y-1.5">
                    {hypothesis.evidence.map((ev, idx) => (
                      <li
                        key={idx}
                        className="flex items-start gap-2 text-sm text-stone-600 dark:text-stone-400"
                      >
                        <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
                        {ev}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Suggested actions */}
              {hypothesis.suggestedActions && hypothesis.suggestedActions.length > 0 && (
                <div>
                  <h5 className="text-xs font-semibold text-stone-500 dark:text-stone-400 uppercase tracking-wider mb-2">
                    Suggested Actions
                  </h5>
                  <ul className="space-y-1.5">
                    {hypothesis.suggestedActions.map((action, idx) => (
                      <li
                        key={idx}
                        className="flex items-start gap-2 text-sm text-stone-600 dark:text-stone-400"
                      >
                        <Lightbulb className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
                        {action}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Actions */}
              {hypothesis.status === 'investigating' && (
                <div className="flex items-center gap-3 pt-2 border-t border-stone-200 dark:border-stone-700">
                  <Button size="sm" onClick={() => onConfirm?.(hypothesis.id)}>
                    <ThumbsUp className="w-4 h-4 mr-1.5" />
                    Confirm as Root Cause
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onReject?.(hypothesis.id)}
                  >
                    <ThumbsDown className="w-4 h-4 mr-1.5" />
                    Reject
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onInvestigate?.(hypothesis.id)}
                  >
                    <ExternalLink className="w-4 h-4 mr-1.5" />
                    Investigate Further
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface HypothesisListProps {
  hypotheses: Hypothesis[];
  onConfirm?: (id: string) => void;
  onReject?: (id: string) => void;
  onInvestigate?: (id: string) => void;
}

export function HypothesisList({
  hypotheses,
  onConfirm,
  onReject,
  onInvestigate,
}: HypothesisListProps) {
  // Sort by confidence, confirmed first
  const sorted = [...hypotheses].sort((a, b) => {
    if (a.status === 'confirmed' && b.status !== 'confirmed') return -1;
    if (b.status === 'confirmed' && a.status !== 'confirmed') return 1;
    if (a.status === 'rejected' && b.status !== 'rejected') return 1;
    if (b.status === 'rejected' && a.status !== 'rejected') return -1;
    return b.confidence - a.confidence;
  });

  if (hypotheses.length === 0) {
    return (
      <div className="text-center py-8 text-stone-500 dark:text-stone-400">
        <Target className="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p className="text-sm">No hypotheses generated yet</p>
        <p className="text-xs mt-1">Hypotheses will appear as the investigation progresses</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {sorted.map((hypothesis) => (
        <HypothesisCard
          key={hypothesis.id}
          hypothesis={hypothesis}
          onConfirm={onConfirm}
          onReject={onReject}
          onInvestigate={onInvestigate}
        />
      ))}
    </div>
  );
}

// Helper functions
function getConfidenceColor(confidence: number) {
  if (confidence >= 80) {
    return {
      stroke: 'stroke-green-500',
      text: 'text-green-600 dark:text-green-400',
    };
  }
  if (confidence >= 60) {
    return {
      stroke: 'stroke-yellow-500',
      text: 'text-yellow-600 dark:text-yellow-400',
    };
  }
  if (confidence >= 40) {
    return {
      stroke: 'stroke-orange-500',
      text: 'text-orange-600 dark:text-orange-400',
    };
  }
  return {
    stroke: 'stroke-red-500',
    text: 'text-red-600 dark:text-red-400',
  };
}

function getStatusConfig(status: string) {
  switch (status) {
    case 'confirmed':
      return {
        label: 'Confirmed',
        icon: CheckCircle,
        bg: 'bg-green-100 dark:bg-green-900/30',
        text: 'text-green-700 dark:text-green-400',
      };
    case 'rejected':
      return {
        label: 'Rejected',
        icon: ThumbsDown,
        bg: 'bg-red-100 dark:bg-red-900/30',
        text: 'text-red-700 dark:text-red-400',
      };
    case 'investigating':
      return {
        label: 'Investigating',
        icon: Target,
        bg: 'bg-blue-100 dark:bg-blue-900/30',
        text: 'text-blue-700 dark:text-blue-400',
      };
    default:
      return {
        label: 'Pending',
        icon: AlertTriangle,
        bg: 'bg-stone-100 dark:bg-stone-800',
        text: 'text-stone-700 dark:text-stone-400',
      };
  }
}

export default HypothesisCard;
