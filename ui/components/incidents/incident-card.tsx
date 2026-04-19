'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge, StatusBadge, SeverityBadge } from '@/components/ui/badge';
import { cn, formatRelativeTime, truncate } from '@/lib/utils';
import type { Investigation } from '@/lib/api';
import {
  AlertTriangle,
  Clock,
  Eye,
  Wrench,
  ChevronRight,
  Brain,
} from 'lucide-react';
import Link from 'next/link';

interface IncidentCardProps {
  incident: Investigation;
  compact?: boolean;
}

export function IncidentCard({ incident, compact = false }: IncidentCardProps) {
  const severity = incident.severity || 
    (incident.observations.some(o => o.severity === 'critical') ? 'critical' :
     incident.observations.some(o => o.severity === 'warning') ? 'warning' : 'info');

  const severityColors = {
    critical: 'border-l-red-500',
    high: 'border-l-orange-500',
    medium: 'border-l-yellow-500',
    warning: 'border-l-yellow-500',
    low: 'border-l-blue-500',
    info: 'border-l-blue-500',
  };

  const pendingActions = incident.actions.filter(a => a.status === 'pending' && a.requires_approval).length;

  return (
    <Link href={`/incidents/${incident.id}`}>
      <Card
        className={cn(
          'border-l-4 transition-all hover:border-gray-700 cursor-pointer',
          severityColors[severity as keyof typeof severityColors] || 'border-l-gray-500'
        )}
      >
        <CardContent className={cn('p-4', compact && 'p-3')}>
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <AlertTriangle className={cn(
                  'h-4 w-4 shrink-0',
                  severity === 'critical' ? 'text-red-500' :
                  severity === 'warning' || severity === 'medium' ? 'text-yellow-500' :
                  'text-blue-500'
                )} />
                <h3 className={cn('font-medium truncate', compact ? 'text-sm' : 'text-base')}>
                  {truncate(incident.issue, compact ? 50 : 80)}
                </h3>
              </div>
              
              <div className="flex items-center gap-3 text-sm text-gray-400">
                <span>{incident.namespace}</span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatRelativeTime(incident.started_at)}
                </span>
              </div>

              {!compact && incident.root_cause && (
                <div className="mt-3 flex items-start gap-2 p-2 bg-yellow-500/10 rounded border border-yellow-500/20">
                  <Brain className="h-4 w-4 text-yellow-500 shrink-0 mt-0.5" />
                  <div className="text-sm">
                    <span className="text-yellow-500 font-medium">Root Cause: </span>
                    <span className="text-gray-300">{truncate(incident.root_cause, 100)}</span>
                    <span className="text-gray-500 ml-1">
                      ({Math.round(incident.confidence * 100)}% confidence)
                    </span>
                  </div>
                </div>
              )}
            </div>

            <div className="flex flex-col items-end gap-2 shrink-0">
              <StatusBadge status={incident.status} />
              
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <Eye className="h-3 w-3" />
                  {incident.observations.length}
                </span>
                <span className="flex items-center gap-1">
                  <Wrench className="h-3 w-3" />
                  {incident.actions.length}
                </span>
              </div>

              {pendingActions > 0 && (
                <Badge variant="warning" className="text-xs">
                  {pendingActions} approval{pendingActions > 1 ? 's' : ''} needed
                </Badge>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

interface IncidentListProps {
  incidents: Investigation[];
  compact?: boolean;
  maxItems?: number;
}

export function IncidentList({ incidents, compact = false, maxItems }: IncidentListProps) {
  const displayIncidents = maxItems ? incidents.slice(0, maxItems) : incidents;

  if (incidents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-500">
        <AlertTriangle className="h-12 w-12 mb-4 opacity-50" />
        <p>No incidents found</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {displayIncidents.map((incident) => (
        <IncidentCard key={incident.id} incident={incident} compact={compact} />
      ))}
      
      {maxItems && incidents.length > maxItems && (
        <Link
          href="/incidents"
          className="flex items-center justify-center gap-2 py-3 text-sm text-blue-400 hover:text-blue-300 transition-colors"
        >
          View all {incidents.length} incidents
          <ChevronRight className="h-4 w-4" />
        </Link>
      )}
    </div>
  );
}
