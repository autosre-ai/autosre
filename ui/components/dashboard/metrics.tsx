'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  TrendingUp,
  TrendingDown,
  Minus,
} from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ComponentType<{ className?: string }>;
  trend?: {
    value: number;
    label: string;
  };
  status?: 'success' | 'warning' | 'danger' | 'neutral';
  className?: string;
}

export function MetricCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  status = 'neutral',
  className,
}: MetricCardProps) {
  const statusColors = {
    success: 'text-green-400',
    warning: 'text-yellow-400',
    danger: 'text-red-400',
    neutral: 'text-gray-400',
  };

  const statusBg = {
    success: 'bg-green-500/10',
    warning: 'bg-yellow-500/10',
    danger: 'bg-red-500/10',
    neutral: 'bg-gray-500/10',
  };

  return (
    <Card className={cn('relative overflow-hidden', className)}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-gray-400">{title}</CardTitle>
        {Icon && (
          <div className={cn('p-2 rounded-lg', statusBg[status])}>
            <Icon className={cn('h-4 w-4', statusColors[status])} />
          </div>
        )}
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline gap-2">
          <div className="text-3xl font-bold">{value}</div>
          {trend && (
            <div
              className={cn(
                'flex items-center text-sm',
                trend.value > 0
                  ? 'text-green-400'
                  : trend.value < 0
                  ? 'text-red-400'
                  : 'text-gray-400'
              )}
            >
              {trend.value > 0 ? (
                <TrendingUp className="h-4 w-4 mr-1" />
              ) : trend.value < 0 ? (
                <TrendingDown className="h-4 w-4 mr-1" />
              ) : (
                <Minus className="h-4 w-4 mr-1" />
              )}
              {Math.abs(trend.value)}%
            </div>
          )}
        </div>
        {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
      </CardContent>
    </Card>
  );
}

interface MetricsGridProps {
  metrics: {
    activeIncidents: number;
    resolvedToday: number;
    mttr: number;
    pendingApprovals: number;
    activeAgents: number;
    successRate: number;
  };
}

export function MetricsGrid({ metrics }: MetricsGridProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
      <MetricCard
        title="Active Incidents"
        value={metrics.activeIncidents}
        icon={AlertTriangle}
        status={metrics.activeIncidents > 5 ? 'danger' : metrics.activeIncidents > 0 ? 'warning' : 'success'}
      />
      <MetricCard
        title="Resolved Today"
        value={metrics.resolvedToday}
        icon={CheckCircle}
        status="success"
        trend={{ value: 12, label: 'vs yesterday' }}
      />
      <MetricCard
        title="MTTR"
        value={`${metrics.mttr}m`}
        subtitle="Mean Time to Resolve"
        icon={Clock}
        status={metrics.mttr > 30 ? 'warning' : 'success'}
      />
      <MetricCard
        title="Pending Approvals"
        value={metrics.pendingApprovals}
        status={metrics.pendingApprovals > 0 ? 'warning' : 'neutral'}
      />
      <MetricCard
        title="Active Agents"
        value={metrics.activeAgents}
        status="success"
      />
      <MetricCard
        title="Success Rate"
        value={`${metrics.successRate}%`}
        status={metrics.successRate >= 95 ? 'success' : metrics.successRate >= 80 ? 'warning' : 'danger'}
        trend={{ value: 3, label: 'vs last week' }}
      />
    </div>
  );
}
