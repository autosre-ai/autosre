'use client';

import React from 'react';
import { DashboardLayout } from '@/components/dashboard/layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { MetricsGrid } from '@/components/dashboard/metrics';
import { IncidentList } from '@/components/incidents/incident-card';
import { AgentStatusMini } from '@/components/agents/agent-card';
import { LoadingState, EmptyState } from '@/components/ui/spinner';
import { useInvestigations, useAgents, useSystemStatus } from '@/hooks/use-api';
import {
  AlertTriangle,
  Bot,
  Activity,
  RefreshCw,
  ChevronRight,
  Shield,
  Zap,
  Clock,
  CheckCircle,
} from 'lucide-react';
import Link from 'next/link';

function SystemStatusIndicator() {
  const { data: status, isLoading, error } = useSystemStatus();

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-gray-400">
        <RefreshCw className="h-4 w-4 animate-spin" />
        <span className="text-sm">Checking status...</span>
      </div>
    );
  }

  if (error || !status) {
    return (
      <div className="flex items-center gap-2 text-red-400">
        <Activity className="h-4 w-4" />
        <span className="text-sm">Connection Error</span>
      </div>
    );
  }

  const integrations = [
    { name: 'Prometheus', key: 'prometheus' as const },
    { name: 'Kubernetes', key: 'kubernetes' as const },
    { name: 'LLM', key: 'llm' as const },
  ];

  return (
    <div className="flex items-center gap-4">
      {integrations.map(({ name, key }) => {
        const int = status.integrations[key];
        const isConnected = int.status === 'connected';
        return (
          <div
            key={key}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm ${
              isConnected ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
            }`}
          >
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            {name}
          </div>
        );
      })}
    </div>
  );
}

function QuickActions() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-gray-400">Quick Actions</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-2">
        <Link href="/incidents?new=true">
          <Button variant="outline" size="sm" className="w-full justify-start gap-2">
            <Zap className="h-4 w-4 text-yellow-400" />
            New Investigation
          </Button>
        </Link>
        <Link href="/agents">
          <Button variant="outline" size="sm" className="w-full justify-start gap-2">
            <Bot className="h-4 w-4 text-blue-400" />
            Manage Agents
          </Button>
        </Link>
        <Link href="/runbooks">
          <Button variant="outline" size="sm" className="w-full justify-start gap-2">
            <Shield className="h-4 w-4 text-purple-400" />
            Run Playbook
          </Button>
        </Link>
        <Link href="/settings">
          <Button variant="outline" size="sm" className="w-full justify-start gap-2">
            <Activity className="h-4 w-4 text-green-400" />
            View Metrics
          </Button>
        </Link>
      </CardContent>
    </Card>
  );
}

function RecentActivity() {
  const { data: investigations } = useInvestigations();
  
  const recentActions = React.useMemo(() => {
    if (!investigations) return [];
    
    const actions: Array<{
      id: string;
      type: 'investigation' | 'action' | 'completion';
      message: string;
      timestamp: string;
      status?: string;
    }> = [];

    investigations.slice(0, 5).forEach(inv => {
      actions.push({
        id: `inv-${inv.id}`,
        type: 'investigation',
        message: `Investigation started: ${inv.issue.slice(0, 50)}...`,
        timestamp: inv.started_at,
      });

      inv.actions.forEach(action => {
        if (action.status === 'completed') {
          actions.push({
            id: `action-${action.id}`,
            type: 'action',
            message: `Action executed: ${action.description.slice(0, 40)}...`,
            timestamp: action.executed_at || inv.started_at,
            status: 'completed',
          });
        }
      });

      if (inv.status === 'completed' && inv.completed_at) {
        actions.push({
          id: `complete-${inv.id}`,
          type: 'completion',
          message: `Investigation resolved: ${inv.issue.slice(0, 40)}...`,
          timestamp: inv.completed_at,
        });
      }
    });

    return actions
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 8);
  }, [investigations]);

  const getIcon = (type: string) => {
    switch (type) {
      case 'investigation':
        return <AlertTriangle className="h-4 w-4 text-yellow-400" />;
      case 'action':
        return <Zap className="h-4 w-4 text-blue-400" />;
      case 'completion':
        return <CheckCircle className="h-4 w-4 text-green-400" />;
      default:
        return <Activity className="h-4 w-4 text-gray-400" />;
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-gray-400">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {recentActions.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">No recent activity</p>
          ) : (
            recentActions.map((activity) => (
              <div key={activity.id} className="flex items-start gap-3">
                {getIcon(activity.type)}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-200 truncate">{activity.message}</p>
                  <p className="text-xs text-gray-500">
                    {new Date(activity.timestamp).toLocaleTimeString()}
                  </p>
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function DashboardContent() {
  const { data: investigations, isLoading: loadingInvestigations } = useInvestigations();
  const { data: agents, isLoading: loadingAgents } = useAgents();

  // Mock metrics - in production, fetch from API
  const metrics = React.useMemo(() => {
    const active = investigations?.filter(i => i.status === 'running').length || 0;
    const resolved = investigations?.filter(i => i.status === 'completed').length || 0;
    const pending = investigations?.reduce(
      (count, inv) => count + inv.actions.filter(a => a.status === 'pending' && a.requires_approval).length,
      0
    ) || 0;
    const runningAgents = agents?.filter(a => a.status === 'running').length || 0;

    return {
      activeIncidents: active,
      resolvedToday: resolved,
      mttr: 15,
      pendingApprovals: pending,
      activeAgents: runningAgents,
      successRate: 94,
    };
  }, [investigations, agents]);

  const activeIncidents = React.useMemo(
    () => investigations?.filter(i => i.status === 'running' || i.status === 'waiting_approval') || [],
    [investigations]
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-gray-400 mt-1">Monitor and manage your SRE operations</p>
        </div>
        <SystemStatusIndicator />
      </div>

      {/* Metrics */}
      <MetricsGrid metrics={metrics} />

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Incidents - takes 2 columns */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-yellow-400" />
                <CardTitle>Active Incidents</CardTitle>
              </div>
              <Link href="/incidents">
                <Button variant="ghost" size="sm" className="gap-1">
                  View all <ChevronRight className="h-4 w-4" />
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              {loadingInvestigations ? (
                <LoadingState message="Loading incidents..." />
              ) : activeIncidents.length === 0 ? (
                <EmptyState
                  icon={CheckCircle}
                  title="All clear!"
                  description="No active incidents at the moment"
                />
              ) : (
                <IncidentList incidents={activeIncidents} maxItems={5} compact />
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right sidebar */}
        <div className="space-y-6">
          {/* Agents status */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="flex items-center gap-2">
                <Bot className="h-5 w-5 text-blue-400" />
                <CardTitle className="text-sm font-medium text-gray-400">Agents</CardTitle>
              </div>
              <Link href="/agents">
                <Button variant="ghost" size="sm" className="gap-1">
                  Manage <ChevronRight className="h-4 w-4" />
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              {loadingAgents ? (
                <LoadingState />
              ) : agents && agents.length > 0 ? (
                <AgentStatusMini agents={agents} />
              ) : (
                <p className="text-sm text-gray-500">No agents configured</p>
              )}
            </CardContent>
          </Card>

          {/* Quick actions */}
          <QuickActions />

          {/* Recent activity */}
          <RecentActivity />
        </div>
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <DashboardLayout>
      <DashboardContent />
    </DashboardLayout>
  );
}
