'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge, StatusBadge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn, formatRelativeTime } from '@/lib/utils';
import type { Agent } from '@/lib/api';
import {
  Bot,
  Play,
  Square,
  Activity,
  Clock,
  Wrench,
  ChevronRight,
} from 'lucide-react';
import Link from 'next/link';

const agentTypeColors = {
  investigator: 'text-blue-400 bg-blue-500/10',
  executor: 'text-green-400 bg-green-500/10',
  observer: 'text-purple-400 bg-purple-500/10',
  coordinator: 'text-yellow-400 bg-yellow-500/10',
};

const agentTypeIcons = {
  investigator: '🔍',
  executor: '⚡',
  observer: '👁️',
  coordinator: '🎯',
};

interface AgentCardProps {
  agent: Agent;
  onDeploy?: (id: string) => void;
  onStop?: (id: string) => void;
  isLoading?: boolean;
}

export function AgentCard({ agent, onDeploy, onStop, isLoading }: AgentCardProps) {
  const isRunning = agent.status === 'running';
  const TypeIcon = agentTypeColors[agent.type] ? agentTypeIcons[agent.type] : '🤖';

  return (
    <Link href={`/agents/${agent.id}`}>
      <Card className="hover:border-gray-700 transition-all cursor-pointer">
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className={cn(
                'w-10 h-10 rounded-lg flex items-center justify-center text-lg',
                agentTypeColors[agent.type]
              )}>
                {TypeIcon}
              </div>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-medium">{agent.name}</h3>
                  <StatusBadge status={agent.status} />
                </div>
                
                <p className="text-sm text-gray-400 line-clamp-2">
                  {agent.description}
                </p>

                <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                  <span className="flex items-center gap-1 capitalize">
                    <Bot className="h-3 w-3" />
                    {agent.type}
                  </span>
                  <span className="flex items-center gap-1">
                    <Wrench className="h-3 w-3" />
                    {agent.skills.length} skills
                  </span>
                  {agent.last_active && (
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatRelativeTime(agent.last_active)}
                    </span>
                  )}
                </div>

                {agent.metrics && (
                  <div className="flex items-center gap-4 mt-2 text-xs">
                    <span className="text-gray-400">
                      {agent.metrics.investigations_handled} investigations
                    </span>
                    <span className={cn(
                      agent.metrics.success_rate >= 90 ? 'text-green-400' :
                      agent.metrics.success_rate >= 70 ? 'text-yellow-400' : 'text-red-400'
                    )}>
                      {agent.metrics.success_rate}% success
                    </span>
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0" onClick={(e) => e.preventDefault()}>
              {isRunning ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onStop?.(agent.id)}
                  disabled={isLoading}
                >
                  <Square className="h-4 w-4 mr-1" />
                  Stop
                </Button>
              ) : (
                <Button
                  variant="default"
                  size="sm"
                  onClick={() => onDeploy?.(agent.id)}
                  disabled={isLoading}
                >
                  <Play className="h-4 w-4 mr-1" />
                  Deploy
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

interface AgentGridProps {
  agents: Agent[];
  onDeploy?: (id: string) => void;
  onStop?: (id: string) => void;
  loadingId?: string;
}

export function AgentGrid({ agents, onDeploy, onStop, loadingId }: AgentGridProps) {
  if (agents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-500">
        <Bot className="h-12 w-12 mb-4 opacity-50" />
        <p>No agents configured</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {agents.map((agent) => (
        <AgentCard
          key={agent.id}
          agent={agent}
          onDeploy={onDeploy}
          onStop={onStop}
          isLoading={loadingId === agent.id}
        />
      ))}
    </div>
  );
}

// Mini agent status for dashboard
export function AgentStatusMini({ agents }: { agents: Agent[] }) {
  const running = agents.filter(a => a.status === 'running').length;
  const total = agents.length;

  return (
    <div className="flex items-center gap-4">
      <div className="flex -space-x-2">
        {agents.slice(0, 4).map((agent, i) => (
          <div
            key={agent.id}
            className={cn(
              'w-8 h-8 rounded-full border-2 border-gray-900 flex items-center justify-center text-xs',
              agent.status === 'running' ? 'bg-green-500/20' : 'bg-gray-700'
            )}
            title={agent.name}
          >
            {agentTypeIcons[agent.type] || '🤖'}
          </div>
        ))}
        {agents.length > 4 && (
          <div className="w-8 h-8 rounded-full border-2 border-gray-900 bg-gray-700 flex items-center justify-center text-xs">
            +{agents.length - 4}
          </div>
        )}
      </div>
      <div className="text-sm">
        <span className="text-green-400 font-medium">{running}</span>
        <span className="text-gray-500"> / {total} running</span>
      </div>
    </div>
  );
}
