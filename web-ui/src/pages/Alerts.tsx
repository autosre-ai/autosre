import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Header } from '@/components/layout';
import { Card, CardContent, Button, SeverityBadge, StatusBadge, Select, Input, EmptyState } from '@/components/ui';
import { Search, Filter, AlertTriangle, Clock, PlayCircle } from 'lucide-react';
import { mockAlerts } from '@/data/mockData';
import { formatRelativeTime, cn } from '@/lib/utils';
import type { Alert } from '@/types';

const severityOptions = [
  { value: '', label: 'All Severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

const statusOptions = [
  { value: '', label: 'All Statuses' },
  { value: 'firing', label: 'Firing' },
  { value: 'acknowledged', label: 'Acknowledged' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'silenced', label: 'Silenced' },
];

export function AlertsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const filteredAlerts = mockAlerts.filter((alert) => {
    const matchesSearch =
      !searchQuery ||
      alert.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      alert.service.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSeverity = !severityFilter || alert.severity === severityFilter;
    const matchesStatus = !statusFilter || alert.status === statusFilter;
    return matchesSearch && matchesSeverity && matchesStatus;
  });

  // Group alerts by status for organization
  const groupedAlerts = {
    firing: filteredAlerts.filter((a) => a.status === 'firing'),
    acknowledged: filteredAlerts.filter((a) => a.status === 'acknowledged'),
    other: filteredAlerts.filter((a) => !['firing', 'acknowledged'].includes(a.status)),
  };

  return (
    <div>
      <Header
        title="Alerts"
        subtitle={`${filteredAlerts.length} alerts`}
        actions={
          <Button variant="outline" size="sm">
            <Filter className="w-4 h-4" />
            Export
          </Button>
        }
      />

      <div className="p-6 lg:p-8 space-y-6">
        {/* Filters */}
        <Card>
          <CardContent className="py-4">
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
                  <Input
                    placeholder="Search alerts..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>
              <div className="flex gap-3">
                <Select
                  options={severityOptions}
                  value={severityFilter}
                  onChange={setSeverityFilter}
                  className="w-40"
                />
                <Select
                  options={statusOptions}
                  value={statusFilter}
                  onChange={setStatusFilter}
                  className="w-40"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Alert List */}
        {filteredAlerts.length === 0 ? (
          <EmptyState
            icon={<AlertTriangle className="w-6 h-6 text-stone-400" />}
            title="No alerts found"
            description="Try adjusting your filters or search query"
          />
        ) : (
          <div className="space-y-6">
            {/* Firing Alerts */}
            {groupedAlerts.firing.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-red-600 dark:text-red-400 mb-3 flex items-center gap-2">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                  </span>
                  Firing ({groupedAlerts.firing.length})
                </h3>
                <div className="space-y-3">
                  {groupedAlerts.firing.map((alert) => (
                    <AlertCard key={alert.id} alert={alert} />
                  ))}
                </div>
              </div>
            )}

            {/* Acknowledged Alerts */}
            {groupedAlerts.acknowledged.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-yellow-600 dark:text-yellow-400 mb-3">
                  Acknowledged ({groupedAlerts.acknowledged.length})
                </h3>
                <div className="space-y-3">
                  {groupedAlerts.acknowledged.map((alert) => (
                    <AlertCard key={alert.id} alert={alert} />
                  ))}
                </div>
              </div>
            )}

            {/* Other Alerts */}
            {groupedAlerts.other.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-stone-600 dark:text-stone-400 mb-3">
                  Other ({groupedAlerts.other.length})
                </h3>
                <div className="space-y-3">
                  {groupedAlerts.other.map((alert) => (
                    <AlertCard key={alert.id} alert={alert} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function AlertCard({ alert }: { alert: Alert }) {
  return (
    <Card hover>
      <Link to={`/alerts/${alert.id}`}>
        <CardContent className="py-4">
          <div className="flex items-start gap-4">
            {/* Severity indicator */}
            <div
              className={cn(
                'w-1 h-full min-h-[60px] rounded-full',
                alert.severity === 'critical' && 'bg-red-500',
                alert.severity === 'high' && 'bg-orange-500',
                alert.severity === 'medium' && 'bg-yellow-500',
                alert.severity === 'low' && 'bg-blue-500'
              )}
            />

            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <SeverityBadge severity={alert.severity} />
                    <StatusBadge status={alert.status} />
                  </div>
                  <h4 className="font-semibold text-stone-900 dark:text-white">
                    {alert.title}
                  </h4>
                  <p className="text-sm text-stone-500 mt-1 line-clamp-2">
                    {alert.description}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  {!alert.investigationId && alert.status === 'firing' && (
                    <Button
                      size="sm"
                      onClick={(e) => {
                        e.preventDefault();
                        // TODO: Start investigation
                      }}
                    >
                      <PlayCircle className="w-4 h-4" />
                      Investigate
                    </Button>
                  )}
                  {alert.investigationId && (
                    <Link to={`/investigations/${alert.investigationId}`}>
                      <Button size="sm" variant="outline">
                        View Investigation
                      </Button>
                    </Link>
                  )}
                </div>
              </div>

              {/* Meta info */}
              <div className="flex items-center gap-4 mt-3 text-xs text-stone-500">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatRelativeTime(alert.startsAt)}
                </span>
                <span className="font-mono bg-stone-100 dark:bg-stone-800 px-1.5 py-0.5 rounded">
                  {alert.service}
                </span>
                {alert.cluster && (
                  <span className="font-mono bg-stone-100 dark:bg-stone-800 px-1.5 py-0.5 rounded">
                    {alert.cluster}
                  </span>
                )}
                <span className="text-stone-400">via {alert.source}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Link>
    </Card>
  );
}
