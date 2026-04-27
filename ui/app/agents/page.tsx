'use client';

export const dynamic = 'force-dynamic';

import React from 'react';
import { DashboardLayout } from '@/components/dashboard/layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { LoadingState, EmptyState } from '@/components/ui/spinner';
import { useAgents, useDeployAgent, useStopAgent } from '@/hooks/use-api';
import {
  Bot,
  Play,
  Square,
  Activity,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Cpu,
  Clock,
  BarChart3,
  RefreshCw,
} from 'lucide-react';
import Link from 'next/link';

function getStatusColor(status: string) {
  switch (status) {
    case 'running': return 'bg-green-500/20 text-green-400 border-green-500/30';
    case 'stopped': return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    case 'error': return 'bg-red-500/20 text-red-400 border-red-500/30';
    case 'initializing': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  }
}

function getTypeIcon(type: string) {
  switch (type) {
    case 'investigator': return <Activity className="h-5 w-5 text-blue-400" />;
    case 'executor': return <Cpu className="h-5 w-5 text-yellow-400" />;
    case 'observer': return <Bot className="h-5 w-5 text-purple-400" />;
    case 'coordinator': return <RefreshCw className="h-5 w-5 text-green-400" />;
    default: return <Bot className="h-5 w-5 text-gray-400" />;
  }
}

export default function AgentsPage() {
  const { data: agents, isLoading, error, refetch } = useAgents();
  const deployAgent = useDeployAgent();
  const stopAgent = useStopAgent();

  const handleDeploy = async (id: string) => {
    await deployAgent.mutateAsync(id);
  };

  const handleStop = async (id: string) => {
    await stopAgent.mutateAsync(id);
  };

  const runningAgents = agents?.filter(a => a.status === 'running').length || 0;
  const totalAgents = agents?.length || 0;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Agents</h1>
            <p className="text-gray-400 mt-1">Manage AI agents for incident response</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-sm text-gray-400">
              {runningAgents}/{totalAgents} running
            </div>
            <Button variant="outline" onClick={() => refetch()} className="gap-2">
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Agent Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Total Agents</p>
                  <p className="text-2xl font-bold">{totalAgents}</p>
                </div>
                <Bot className="h-8 w-8 text-blue-400 opacity-50" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Running</p>
                  <p className="text-2xl font-bold text-green-400">{runningAgents}</p>
                </div>
                <CheckCircle className="h-8 w-8 text-green-400 opacity-50" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Stopped</p>
                  <p className="text-2xl font-bold text-gray-400">
                    {agents?.filter(a => a.status === 'stopped').length || 0}
                  </p>
                </div>
                <Square className="h-8 w-8 text-gray-400 opacity-50" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Errors</p>
                  <p className="text-2xl font-bold text-red-400">
                    {agents?.filter(a => a.status === 'error').length || 0}
                  </p>
                </div>
                <XCircle className="h-8 w-8 text-red-400 opacity-50" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Agent List */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-blue-400" />
              All Agents
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <LoadingState message="Loading agents..." />
            ) : error ? (
              <EmptyState
                icon={XCircle}
                title="Failed to load agents"
                description="Unable to connect to the API"
              />
            ) : !agents || agents.length === 0 ? (
              <EmptyState
                icon={Bot}
                title="No agents configured"
                description="Agents will appear here when configured"
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {agents.map(agent => (
                  <div 
                    key={agent.id}
                    className="p-4 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        {getTypeIcon(agent.type)}
                        <div>
                          <h3 className="font-medium">{agent.name}</h3>
                          <p className="text-xs text-gray-400 capitalize">{agent.type}</p>
                        </div>
                      </div>
                      <Badge className={getStatusColor(agent.status)}>
                        {agent.status}
                      </Badge>
                    </div>

                    <p className="text-sm text-gray-400 mb-3 line-clamp-2">
                      {agent.description}
                    </p>

                    {/* Skills */}
                    <div className="flex flex-wrap gap-1 mb-3">
                      {agent.skills.slice(0, 4).map(skill => (
                        <Badge key={skill} variant="outline" className="text-xs">
                          {skill}
                        </Badge>
                      ))}
                      {agent.skills.length > 4 && (
                        <Badge variant="outline" className="text-xs">
                          +{agent.skills.length - 4}
                        </Badge>
                      )}
                    </div>

                    {/* Metrics */}
                    {agent.metrics && (
                      <div className="grid grid-cols-2 gap-2 text-xs text-gray-400 mb-3 p-2 bg-gray-800 rounded">
                        <div className="flex items-center gap-1">
                          <BarChart3 className="h-3 w-3" />
                          {agent.metrics.investigations_handled} investigations
                        </div>
                        <div className="flex items-center gap-1">
                          <CheckCircle className="h-3 w-3" />
                          {Math.round(agent.metrics.success_rate * 100)}% success
                        </div>
                        <div className="flex items-center gap-1">
                          <Activity className="h-3 w-3" />
                          {agent.metrics.actions_executed} actions
                        </div>
                        <div className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {agent.metrics.avg_response_time}ms avg
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      {agent.status === 'stopped' ? (
                        <Button 
                          size="sm" 
                          onClick={() => handleDeploy(agent.id)}
                          disabled={deployAgent.isPending}
                          className="gap-1 flex-1"
                        >
                          <Play className="h-3 w-3" />
                          Start
                        </Button>
                      ) : agent.status === 'running' ? (
                        <Button 
                          variant="outline" 
                          size="sm" 
                          onClick={() => handleStop(agent.id)}
                          disabled={stopAgent.isPending}
                          className="gap-1 flex-1"
                        >
                          <Square className="h-3 w-3" />
                          Stop
                        </Button>
                      ) : (
                        <Button variant="outline" size="sm" disabled className="gap-1 flex-1">
                          <AlertTriangle className="h-3 w-3" />
                          {agent.status}
                        </Button>
                      )}
                      <Link href={`/agents/${agent.id}`}>
                        <Button variant="outline" size="sm">
                          Details
                        </Button>
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
