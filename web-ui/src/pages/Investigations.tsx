import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Header } from '@/components/layout';
import {
  Card,
  CardContent,
  Button,
  SeverityBadge,
  StatusBadge,
  Select,
  Input,
  EmptyState,
} from '@/components/ui';
import {
  Search,
  Clock,
  ArrowRight,
  Filter,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Brain,
} from 'lucide-react';
import { mockInvestigations } from '@/data/mockData';
import { formatRelativeTime, formatDuration, cn } from '@/lib/utils';
import type { Investigation } from '@/types';

const statusOptions = [
  { value: '', label: 'All Statuses' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'waiting_approval', label: 'Waiting Approval' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
];

const severityOptions = [
  { value: '', label: 'All Severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

export function InvestigationsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const filteredInvestigations = mockInvestigations.filter((inv) => {
    const matchesSearch =
      !searchQuery ||
      inv.alertTitle.toLowerCase().includes(searchQuery.toLowerCase()) ||
      inv.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      inv.rootCause?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = !statusFilter || inv.status === statusFilter;
    const matchesSeverity = !severityFilter || inv.severity === severityFilter;
    return matchesSearch && matchesStatus && matchesSeverity;
  });

  const activeInvestigations = filteredInvestigations.filter(
    (i) => i.status === 'in_progress' || i.status === 'waiting_approval'
  );
  const completedInvestigations = filteredInvestigations.filter(
    (i) => i.status === 'completed' || i.status === 'failed'
  );

  // Stats
  const stats = {
    total: mockInvestigations.length,
    active: mockInvestigations.filter(
      (i) => i.status === 'in_progress' || i.status === 'waiting_approval'
    ).length,
    completed: mockInvestigations.filter((i) => i.status === 'completed').length,
    failed: mockInvestigations.filter((i) => i.status === 'failed').length,
  };

  return (
    <div className="min-h-screen bg-stone-50 dark:bg-stone-900">
      <Header
        title="Investigations"
        subtitle={`${filteredInvestigations.length} investigations`}
      />

      <div className="p-6 lg:p-8 space-y-6">
        {/* Stats cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total"
            value={stats.total}
            icon={Brain}
            color="bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-400"
          />
          <StatCard
            label="Active"
            value={stats.active}
            icon={TrendingUp}
            color="bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
            pulse={stats.active > 0}
          />
          <StatCard
            label="Completed"
            value={stats.completed}
            icon={CheckCircle}
            color="bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400"
          />
          <StatCard
            label="Failed"
            value={stats.failed}
            icon={XCircle}
            color="bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400"
          />
        </div>

        {/* Search and filters */}
        <Card>
          <CardContent className="py-4">
            <div className="flex flex-col gap-4">
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
                  <Input
                    placeholder="Search investigations by title, ID, or root cause..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <Button
                  variant={showFilters ? 'secondary' : 'outline'}
                  onClick={() => setShowFilters(!showFilters)}
                  className="gap-2"
                >
                  <Filter className="w-4 h-4" />
                  Filters
                  {(statusFilter || severityFilter) && (
                    <span className="w-5 h-5 rounded-full bg-forest text-white text-xs flex items-center justify-center">
                      {[statusFilter, severityFilter].filter(Boolean).length}
                    </span>
                  )}
                </Button>
              </div>

              {showFilters && (
                <div className="flex flex-col sm:flex-row gap-4 pt-4 border-t border-stone-200 dark:border-stone-700 animate-in slide-in-from-top-2 duration-200">
                  <Select
                    options={statusOptions}
                    value={statusFilter}
                    onChange={setStatusFilter}
                    className="w-full sm:w-48"
                  />
                  <Select
                    options={severityOptions}
                    value={severityFilter}
                    onChange={setSeverityFilter}
                    className="w-full sm:w-48"
                  />
                  {(statusFilter || severityFilter) && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setStatusFilter('');
                        setSeverityFilter('');
                      }}
                    >
                      Clear filters
                    </Button>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Results */}
        {filteredInvestigations.length === 0 ? (
          <EmptyState
            icon={<Search className="w-6 h-6 text-stone-400" />}
            title="No investigations found"
            description="No investigations match your search criteria. Try adjusting your filters."
          />
        ) : (
          <div className="space-y-8">
            {/* Active investigations */}
            {activeInvestigations.length > 0 && (
              <section>
                <div className="flex items-center gap-3 mb-4">
                  <div className="relative">
                    <span className="absolute inline-flex h-3 w-3 rounded-full bg-forest opacity-75 animate-ping" />
                    <span className="relative inline-flex h-3 w-3 rounded-full bg-forest" />
                  </div>
                  <h3 className="text-sm font-semibold text-forest dark:text-forest-light uppercase tracking-wider">
                    Active Investigations ({activeInvestigations.length})
                  </h3>
                </div>
                <div className="space-y-4">
                  {activeInvestigations.map((investigation) => (
                    <InvestigationCard
                      key={investigation.id}
                      investigation={investigation}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Completed investigations */}
            {completedInvestigations.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-stone-600 dark:text-stone-400 uppercase tracking-wider mb-4">
                  Completed ({completedInvestigations.length})
                </h3>
                <div className="space-y-4">
                  {completedInvestigations.map((investigation) => (
                    <InvestigationCard
                      key={investigation.id}
                      investigation={investigation}
                    />
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Stat card component
function StatCard({
  label,
  value,
  icon: Icon,
  color,
  pulse,
}: {
  label: string;
  value: number;
  icon: typeof Brain;
  color: string;
  pulse?: boolean;
}) {
  return (
    <Card>
      <CardContent className="py-4">
        <div className="flex items-center gap-3">
          <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', color)}>
            <Icon className="w-5 h-5" />
          </div>
          <div>
            <p className="text-2xl font-bold text-stone-900 dark:text-white flex items-center gap-2">
              {value}
              {pulse && (
                <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              )}
            </p>
            <p className="text-xs text-stone-500 dark:text-stone-400 uppercase tracking-wider">
              {label}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Investigation card component
function InvestigationCard({ investigation }: { investigation: Investigation }) {
  const duration = investigation.completedAt
    ? new Date(investigation.completedAt).getTime() -
      new Date(investigation.startedAt).getTime()
    : new Date().getTime() - new Date(investigation.startedAt).getTime();

  const pendingApproval = investigation.steps.find(
    (s) => s.type === 'approval_request' && s.status === 'pending'
  );

  const completedSteps = investigation.steps.filter(
    (s) => s.status === 'success'
  ).length;
  const progress = Math.round((completedSteps / investigation.steps.length) * 100);

  return (
    <Card
      hover
      className={cn(
        'transition-all duration-200',
        pendingApproval && 'ring-2 ring-yellow-400 dark:ring-yellow-600'
      )}
    >
      <Link to={`/investigations/${investigation.id}`}>
        <CardContent className="py-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              {/* Badges row */}
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <SeverityBadge severity={investigation.severity} />
                <StatusBadge status={investigation.status} />
                {pendingApproval && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 rounded text-xs font-medium">
                    <AlertTriangle className="w-3 h-3" />
                    Approval Required
                  </span>
                )}
              </div>

              {/* Title */}
              <h4 className="font-semibold text-stone-900 dark:text-white text-lg">
                {investigation.alertTitle}
              </h4>
              <p className="text-sm text-stone-500 dark:text-stone-400 mt-1">
                {investigation.id}
              </p>

              {/* Meta info */}
              <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-stone-500 dark:text-stone-400">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  Started {formatRelativeTime(investigation.startedAt)}
                </span>
                <span>Duration: {formatDuration(duration)}</span>
                <span>{investigation.steps.length} steps</span>
              </div>

              {/* Progress bar for active investigations */}
              {(investigation.status === 'in_progress' ||
                investigation.status === 'waiting_approval') && (
                <div className="mt-4">
                  <div className="flex items-center justify-between text-xs text-stone-500 dark:text-stone-400 mb-1">
                    <span>Progress</span>
                    <span>{progress}%</span>
                  </div>
                  <div className="h-1.5 bg-stone-200 dark:bg-stone-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-forest dark:bg-forest-light rounded-full transition-all duration-500"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Root cause (if completed) */}
              {investigation.rootCause && (
                <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-100 dark:border-green-900">
                  <p className="text-sm text-green-700 dark:text-green-400">
                    <span className="font-medium">Root Cause:</span>{' '}
                    {investigation.rootCause}
                  </p>
                </div>
              )}
            </div>

            {/* Action button */}
            <Button variant="ghost" size="sm" className="flex-shrink-0">
              View
              <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </CardContent>
      </Link>
    </Card>
  );
}

export default InvestigationsPage;
