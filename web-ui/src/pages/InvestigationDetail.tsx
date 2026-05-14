import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Header } from '@/components/layout';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  SeverityBadge,
  StatusBadge,
} from '@/components/ui';
import { Timeline, EvidencePanel, HypothesisList } from '@/components/investigation';
import type { Hypothesis } from '@/components/investigation';
import {
  ArrowLeft,
  Clock,
  AlertTriangle,
  RefreshCw,
  ArrowUpCircle,
  RotateCcw,
  FileText,
  Brain,
  MessageSquare,
  Share2,
  MoreHorizontal,
} from 'lucide-react';
import { mockInvestigations } from '@/data/mockData';
import { formatRelativeTime, formatDuration, cn } from '@/lib/utils';

// Mock hypotheses data - in real app this would come from the investigation
const mockHypotheses: Hypothesis[] = [
  {
    id: 'hyp-001',
    title: 'Database Query Regression',
    description:
      'The new deployment v2.4.2 introduced a query that performs a full table scan on the transactions table, causing increased latency under load.',
    confidence: 85,
    status: 'investigating',
    evidence: [
      'Latency spike correlates with deployment timestamp (10:05 AM)',
      'Slow query warnings in logs: SELECT * FROM transactions (4.2s avg)',
      'No index on (user_id, status) columns used in WHERE clause',
      'CPU usage on database increased 40% post-deployment',
    ],
    suggestedActions: [
      'Rollback to v2.4.1',
      'Add composite index on transactions(user_id, status)',
      'Review PR #1234 for query changes',
    ],
  },
  {
    id: 'hyp-002',
    title: 'Connection Pool Exhaustion',
    description:
      'Database connection pool may be saturated due to long-running queries holding connections.',
    confidence: 45,
    status: 'investigating',
    evidence: [
      'Connection pool usage at 87% (usually 40-50%)',
      'Query execution time increased across all services',
    ],
    suggestedActions: [
      'Increase connection pool size temporarily',
      'Add connection timeout configuration',
    ],
  },
  {
    id: 'hyp-003',
    title: 'Network Latency Issue',
    description: 'Increased network latency between application pods and database.',
    confidence: 15,
    status: 'rejected',
    evidence: ['Network metrics show normal latency (< 1ms)'],
    suggestedActions: [],
  },
];

// Quick actions available for investigations
const quickActions = [
  {
    id: 'restart',
    label: 'Restart Pod',
    icon: RefreshCw,
    description: 'Restart the affected pod',
    variant: 'outline' as const,
  },
  {
    id: 'scale',
    label: 'Scale Up',
    icon: ArrowUpCircle,
    description: 'Add more replicas',
    variant: 'outline' as const,
  },
  {
    id: 'rollback',
    label: 'Rollback',
    icon: RotateCcw,
    description: 'Rollback to previous version',
    variant: 'danger' as const,
  },
];

export function InvestigationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>(mockHypotheses);

  const investigation = mockInvestigations.find((i) => i.id === id);

  if (!investigation) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] p-8">
        <AlertTriangle className="w-16 h-16 text-stone-300 dark:text-stone-600 mb-4" />
        <h2 className="text-xl font-semibold text-stone-900 dark:text-white mb-2">
          Investigation not found
        </h2>
        <p className="text-stone-500 dark:text-stone-400 mb-6">
          The investigation you're looking for doesn't exist or has been removed.
        </p>
        <Button onClick={() => navigate('/investigations')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Investigations
        </Button>
      </div>
    );
  }

  const duration = investigation.completedAt
    ? new Date(investigation.completedAt).getTime() -
      new Date(investigation.startedAt).getTime()
    : new Date().getTime() - new Date(investigation.startedAt).getTime();

  const handleApproveStep = (stepId: string) => {
    console.log('Approve step:', stepId);
    // In real app: call API to approve the action
  };

  const handleRejectStep = (stepId: string) => {
    console.log('Reject step:', stepId);
    // In real app: call API to reject the action
  };

  const handleConfirmHypothesis = (hypId: string) => {
    setHypotheses((prev) =>
      prev.map((h) =>
        h.id === hypId
          ? { ...h, status: 'confirmed' as const }
          : h.status === 'confirmed'
          ? { ...h, status: 'rejected' as const }
          : h
      )
    );
  };

  const handleRejectHypothesis = (hypId: string) => {
    setHypotheses((prev) =>
      prev.map((h) => (h.id === hypId ? { ...h, status: 'rejected' as const } : h))
    );
  };

  const handleQuickAction = (actionId: string) => {
    console.log('Quick action:', actionId);
    // In real app: show confirmation dialog and execute action
  };

  return (
    <div className="min-h-screen bg-stone-50 dark:bg-stone-900">
      {/* Header */}
      <Header
        title={`Investigation ${investigation.id}`}
        subtitle={investigation.alertTitle}
        actions={
          <div className="flex items-center gap-2">
            {investigation.status === 'in_progress' && (
              <Button variant="outline" size="sm">
                Cancel Investigation
              </Button>
            )}
            <Button variant="ghost" size="sm">
              <Share2 className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="sm">
              <MoreHorizontal className="w-4 h-4" />
            </Button>
          </div>
        }
      />

      <div className="p-6 lg:p-8 space-y-6">
        {/* Back link */}
        <Link
          to="/investigations"
          className="inline-flex items-center gap-2 text-sm text-stone-500 hover:text-stone-700 dark:hover:text-stone-300 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Investigations
        </Link>

        {/* Status bar */}
        <Card>
          <CardContent className="py-4">
            <div className="flex flex-wrap items-center gap-4">
              <SeverityBadge severity={investigation.severity} />
              <StatusBadge status={investigation.status} />
              <div className="flex items-center gap-2 text-sm text-stone-500 dark:text-stone-400">
                <Clock className="w-4 h-4" />
                <span>Started {formatRelativeTime(investigation.startedAt)}</span>
              </div>
              <div className="h-4 w-px bg-stone-300 dark:bg-stone-600" />
              <span className="text-sm text-stone-500 dark:text-stone-400">
                Duration: {formatDuration(duration)}
              </span>
              <div className="h-4 w-px bg-stone-300 dark:bg-stone-600" />
              <span className="text-sm text-stone-500 dark:text-stone-400">
                {investigation.steps.length} steps
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Root cause banner (if identified) */}
        {investigation.rootCause && (
          <div className="p-5 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/50 flex items-center justify-center flex-shrink-0">
                <Brain className="w-5 h-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <h4 className="font-semibold text-green-800 dark:text-green-200 mb-1">
                  Root Cause Identified
                </h4>
                <p className="text-green-700 dark:text-green-300">{investigation.rootCause}</p>
                {investigation.recommendation && (
                  <p className="text-sm text-green-600 dark:text-green-400 mt-2">
                    <span className="font-medium">Recommendation:</span>{' '}
                    {investigation.recommendation}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Main content grid */}
        <div className="grid lg:grid-cols-5 gap-6">
          {/* Timeline - Left column */}
          <div className="lg:col-span-2">
            <Card className="sticky top-6">
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>Timeline</CardTitle>
                <span className="text-xs text-stone-500 dark:text-stone-400">
                  Live updates
                  <span className="ml-2 inline-block w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                </span>
              </CardHeader>
              <CardContent>
                <Timeline
                  steps={investigation.steps}
                  onApprove={handleApproveStep}
                  onReject={handleRejectStep}
                />
              </CardContent>
            </Card>
          </div>

          {/* Evidence - Right column */}
          <div className="lg:col-span-3">
            <Card>
              <CardHeader>
                <CardTitle>Evidence</CardTitle>
              </CardHeader>
              <CardContent>
                <EvidencePanel evidence={investigation.evidence} />
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Hypotheses section */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Root Cause Hypotheses</CardTitle>
              <span className="text-sm text-stone-500 dark:text-stone-400">
                {hypotheses.filter((h) => h.status === 'investigating').length} under
                investigation
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <HypothesisList
              hypotheses={hypotheses}
              onConfirm={handleConfirmHypothesis}
              onReject={handleRejectHypothesis}
              onInvestigate={(id) => console.log('Investigate further:', id)}
            />
          </CardContent>
        </Card>

        {/* Quick actions section */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              {quickActions.map((action) => (
                <Button
                  key={action.id}
                  variant={action.variant}
                  onClick={() => handleQuickAction(action.id)}
                  className="gap-2"
                >
                  <action.icon className="w-4 h-4" />
                  {action.label}
                </Button>
              ))}
              <div className="w-px bg-stone-200 dark:bg-stone-700 mx-2" />
              <Link to={`/chat?investigation=${investigation.id}`}>
                <Button variant="outline" className="gap-2">
                  <MessageSquare className="w-4 h-4" />
                  Continue in Chat
                </Button>
              </Link>
              <Button variant="outline" className="gap-2">
                <FileText className="w-4 h-4" />
                Export Report
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Related info footer */}
        <div className="flex items-center justify-between text-sm text-stone-500 dark:text-stone-400 pt-4 border-t border-stone-200 dark:border-stone-700">
          <div className="flex items-center gap-4">
            <span>
              Alert:{' '}
              <Link
                to={`/alerts/${investigation.alertId}`}
                className="text-forest dark:text-forest-light hover:underline"
              >
                {investigation.alertId}
              </Link>
            </span>
            <span>Service: {investigation.alertTitle.split(' ').pop()}</span>
          </div>
          <span>Last updated {formatRelativeTime(new Date().toISOString())}</span>
        </div>
      </div>
    </div>
  );
}

export default InvestigationDetailPage;
