import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Header } from '@/components/layout';
import { MetricsChart } from '@/components/MetricsChart';
import { TimelineSummary } from '@/components/Timeline';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  SeverityBadge,
  StatusBadge,
  ConfirmDialog,
} from '@/components/ui';
import {
  ArrowLeft,
  Clock,
  PlayCircle,
  CheckCircle2,
  VolumeX,
  ExternalLink,
  AlertTriangle,
  Server,
  Tag,
  Link as LinkIcon,
  MessageSquare,
  History,
} from 'lucide-react';
import { mockAlerts, mockInvestigations, generateMetricSeries } from '@/data/mockData';
import { formatRelativeTime, cn } from '@/lib/utils';

export function AlertDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [showAckModal, setShowAckModal] = useState(false);
  const [showSilenceModal, setShowSilenceModal] = useState(false);
  const [showResolveModal, setShowResolveModal] = useState(false);

  const alert = mockAlerts.find((a) => a.id === id);
  const investigation = alert?.investigationId
    ? mockInvestigations.find((inv) => inv.id === alert.investigationId)
    : null;

  const latencyData = generateMetricSeries(6, 5);
  const errorData = generateMetricSeries(6, 5);

  if (!alert) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 mx-auto text-stone-400 mb-4" />
          <h2 className="text-xl font-semibold text-stone-900 dark:text-white mb-2">
            Alert not found
          </h2>
          <p className="text-stone-500 mb-4">
            The alert you're looking for doesn't exist or has been deleted.
          </p>
          <Link to="/alerts">
            <Button>
              <ArrowLeft className="w-4 h-4" />
              Back to Alerts
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const handleInvestigate = () => {
    navigate(`/chat?alertId=${alert.id}`);
  };

  return (
    <div>
      <Header
        title={
          <div className="flex items-center gap-3">
            <Link
              to="/alerts"
              className="p-1 hover:bg-stone-100 dark:hover:bg-stone-800 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <span className="truncate">{alert.title}</span>
          </div>
        }
        subtitle={`Alert ${alert.id}`}
        actions={
          <div className="flex items-center gap-2">
            {alert.status === 'firing' && !alert.investigationId && (
              <Button onClick={handleInvestigate}>
                <PlayCircle className="w-4 h-4" />
                Start Investigation
              </Button>
            )}
            {alert.investigationId && (
              <Link to={`/investigations/${alert.investigationId}`}>
                <Button>
                  <ExternalLink className="w-4 h-4" />
                  View Investigation
                </Button>
              </Link>
            )}
          </div>
        }
      />

      <div className="p-6 lg:p-8 space-y-6">
        {/* Alert Info Card */}
        <Card>
          <CardContent className="py-6">
            <div className="flex flex-col lg:flex-row lg:items-start gap-6">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-4">
                  <SeverityBadge severity={alert.severity} />
                  <StatusBadge status={alert.status} />
                  {alert.status === 'firing' && (
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                    </span>
                  )}
                </div>

                <h2 className="text-2xl font-bold text-stone-900 dark:text-white mb-2">
                  {alert.title}
                </h2>
                <p className="text-stone-600 dark:text-stone-300 mb-4">
                  {alert.description}
                </p>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                  <div>
                    <p className="text-xs text-stone-500 mb-1">Service</p>
                    <p className="font-mono text-sm font-medium text-stone-900 dark:text-white flex items-center gap-1.5">
                      <Server className="w-3.5 h-3.5" />
                      {alert.service}
                    </p>
                  </div>
                  {alert.cluster && (
                    <div>
                      <p className="text-xs text-stone-500 mb-1">Cluster</p>
                      <p className="font-mono text-sm font-medium text-stone-900 dark:text-white">
                        {alert.cluster}
                      </p>
                    </div>
                  )}
                  <div>
                    <p className="text-xs text-stone-500 mb-1">Source</p>
                    <p className="font-mono text-sm font-medium text-stone-900 dark:text-white">
                      {alert.source}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-stone-500 mb-1">Started</p>
                    <p className="text-sm font-medium text-stone-900 dark:text-white flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5" />
                      {formatRelativeTime(alert.startsAt)}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <Tag className="w-4 h-4 text-stone-400" />
                  {Object.entries(alert.labels).map(([key, value]) => (
                    <span
                      key={key}
                      className="px-2 py-0.5 bg-stone-100 dark:bg-stone-800 rounded text-xs font-mono"
                    >
                      {key}={value}
                    </span>
                  ))}
                </div>

                {alert.annotations?.runbook && (
                  <a
                    href={alert.annotations.runbook}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 mt-4 text-sm text-forest hover:underline"
                  >
                    <LinkIcon className="w-3.5 h-3.5" />
                    View Runbook
                  </a>
                )}
              </div>

              <div className="lg:w-64 space-y-2">
                {alert.status === 'firing' && (
                  <>
                    <Button
                      variant="outline"
                      className="w-full justify-start"
                      onClick={() => setShowAckModal(true)}
                    >
                      <CheckCircle2 className="w-4 h-4" />
                      Acknowledge
                    </Button>
                    <Button
                      variant="outline"
                      className="w-full justify-start"
                      onClick={() => setShowSilenceModal(true)}
                    >
                      <VolumeX className="w-4 h-4" />
                      Silence (1h)
                    </Button>
                  </>
                )}
                {(alert.status === 'firing' || alert.status === 'acknowledged') && (
                  <Button
                    variant="outline"
                    className="w-full justify-start text-green-600 border-green-300 hover:bg-green-50 dark:hover:bg-green-900/20"
                    onClick={() => setShowResolveModal(true)}
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    Mark Resolved
                  </Button>
                )}
                <Link to={`/chat?alertId=${alert.id}`} className="block">
                  <Button variant="outline" className="w-full justify-start">
                    <MessageSquare className="w-4 h-4" />
                    Ask AutoSRE
                  </Button>
                </Link>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Charts */}
        <div className="grid lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Latency (p99)</CardTitle>
            </CardHeader>
            <CardContent>
              <MetricsChart data={[latencyData[1]]} type="area" height={200} showGrid={false} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Error Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <MetricsChart data={[{ ...errorData[2], color: '#ef4444' }]} type="line" height={200} showGrid={false} />
            </CardContent>
          </Card>
        </div>

        {/* Investigation History */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <History className="w-5 h-5" />
                Investigation History
              </CardTitle>
              {investigation && (
                <Link to={`/investigations/${investigation.id}`}>
                  <Button variant="ghost" size="sm">
                    View Full Details
                    <ExternalLink className="w-4 h-4 ml-1" />
                  </Button>
                </Link>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {investigation ? (
              <div>
                <div className="flex items-center gap-3 mb-4 pb-4 border-b border-stone-200 dark:border-stone-700">
                  <StatusBadge status={investigation.status} />
                  <span className="text-sm text-stone-500">
                    Started {formatRelativeTime(investigation.startedAt)}
                    {investigation.completedAt && (
                      <> • Completed {formatRelativeTime(investigation.completedAt)}</>
                    )}
                  </span>
                </div>
                <TimelineSummary steps={investigation.steps} maxSteps={4} />

                {investigation.rootCause && (
                  <div className="mt-4 p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                    <h4 className="font-semibold text-green-800 dark:text-green-300 mb-1">
                      Root Cause
                    </h4>
                    <p className="text-sm text-green-700 dark:text-green-400">
                      {investigation.rootCause}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8">
                <History className="w-10 h-10 mx-auto text-stone-300 dark:text-stone-600 mb-3" />
                <p className="text-stone-500 mb-4">No investigation started yet</p>
                <Button onClick={handleInvestigate}>
                  <PlayCircle className="w-4 h-4" />
                  Start Investigation
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Related Alerts */}
        <Card>
          <CardHeader>
            <CardTitle>Related Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-center py-6 text-stone-500">
              <AlertTriangle className="w-8 h-8 mx-auto text-stone-300 dark:text-stone-600 mb-2" />
              <p>No related alerts found</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Modals */}
      <ConfirmDialog
        isOpen={showAckModal}
        onClose={() => setShowAckModal(false)}
        onConfirm={() => setShowAckModal(false)}
        title="Acknowledge Alert"
        message="Are you sure you want to acknowledge this alert? This indicates you are aware of the issue and are working on it."
        confirmLabel="Acknowledge"
      />

      <ConfirmDialog
        isOpen={showSilenceModal}
        onClose={() => setShowSilenceModal(false)}
        onConfirm={() => setShowSilenceModal(false)}
        title="Silence Alert"
        message="Silence this alert for 1 hour? You won't receive notifications during this time."
        confirmLabel="Silence"
      />

      <ConfirmDialog
        isOpen={showResolveModal}
        onClose={() => setShowResolveModal(false)}
        onConfirm={() => setShowResolveModal(false)}
        title="Resolve Alert"
        message="Mark this alert as resolved? This will close the alert and stop any associated monitoring."
        confirmLabel="Resolve"
        variant="success"
      />
    </div>
  );
}
