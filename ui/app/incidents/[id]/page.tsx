'use client';

export const dynamic = 'force-dynamic';

import React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { DashboardLayout } from '@/components/dashboard/layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { LoadingState } from '@/components/ui/spinner';
import { useInvestigation, useApproveAction, useRejectAction } from '@/hooks/use-api';
import {
  ArrowLeft,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Activity,
  Terminal,
  ThumbsUp,
  ThumbsDown,
  ChevronRight,
  Eye,
  Target,
  Zap,
} from 'lucide-react';
import Link from 'next/link';

function getStatusColor(status: string) {
  switch (status) {
    case 'running': return 'text-blue-400 bg-blue-500/10';
    case 'completed': return 'text-green-400 bg-green-500/10';
    case 'failed': return 'text-red-400 bg-red-500/10';
    case 'waiting_approval': return 'text-yellow-400 bg-yellow-500/10';
    default: return 'text-gray-400 bg-gray-500/10';
  }
}

function getRiskColor(risk: string) {
  switch (risk) {
    case 'low': return 'text-green-400 border-green-500/30';
    case 'medium': return 'text-yellow-400 border-yellow-500/30';
    case 'high': return 'text-red-400 border-red-500/30';
    default: return 'text-gray-400 border-gray-500/30';
  }
}

function getSeverityIcon(severity: string) {
  switch (severity) {
    case 'critical': return <AlertTriangle className="h-4 w-4 text-red-400" />;
    case 'warning': return <AlertTriangle className="h-4 w-4 text-yellow-400" />;
    case 'info': return <Activity className="h-4 w-4 text-blue-400" />;
    default: return <Activity className="h-4 w-4 text-gray-400" />;
  }
}

export default function IncidentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  
  const { data: investigation, isLoading, error } = useInvestigation(id);
  const approveAction = useApproveAction();
  const rejectAction = useRejectAction();

  const handleApprove = async (actionId: string) => {
    await approveAction.mutateAsync({ investigationId: id, actionId });
  };

  const handleReject = async (actionId: string) => {
    await rejectAction.mutateAsync({ investigationId: id, actionId, reason: '' });
  };

  if (isLoading) {
    return (
      <DashboardLayout>
        <LoadingState message="Loading investigation..." />
      </DashboardLayout>
    );
  }

  if (error || !investigation) {
    return (
      <DashboardLayout>
        <Card>
          <CardContent className="py-12 text-center">
            <XCircle className="h-12 w-12 text-red-400 mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">Investigation Not Found</h2>
            <p className="text-gray-400 mb-4">Unable to load this investigation.</p>
            <Button onClick={() => router.push('/incidents')}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Incidents
            </Button>
          </CardContent>
        </Card>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <Link 
              href="/incidents" 
              className="inline-flex items-center text-sm text-gray-400 hover:text-white mb-2"
            >
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back to Incidents
            </Link>
            <h1 className="text-2xl font-bold">{investigation.issue}</h1>
            <div className="flex items-center gap-4 mt-2 text-sm text-gray-400">
              <span>ID: {investigation.id}</span>
              <span>Namespace: {investigation.namespace}</span>
              <span>Started: {new Date(investigation.started_at).toLocaleString()}</span>
            </div>
          </div>
          <Badge className={`${getStatusColor(investigation.status)} text-sm px-3 py-1`}>
            {investigation.status === 'running' && <Clock className="h-3 w-3 mr-1 animate-pulse" />}
            {investigation.status === 'completed' && <CheckCircle className="h-3 w-3 mr-1" />}
            {investigation.status === 'failed' && <XCircle className="h-3 w-3 mr-1" />}
            {investigation.status === 'waiting_approval' && <AlertTriangle className="h-3 w-3 mr-1" />}
            {investigation.status.replace('_', ' ')}
          </Badge>
        </div>

        {/* Root Cause */}
        {investigation.root_cause && (
          <Card className="border-green-500/30 bg-green-500/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-green-400">
                <Target className="h-5 w-5" />
                Root Cause Analysis
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-lg">{investigation.root_cause}</p>
              <div className="mt-4 flex items-center gap-4 text-sm text-gray-400">
                <span className="flex items-center gap-1">
                  <Activity className="h-4 w-4" />
                  Confidence: {Math.round(investigation.confidence * 100)}%
                </span>
                <div className="flex-1 bg-gray-700 rounded-full h-2 max-w-xs">
                  <div 
                    className="bg-green-500 h-2 rounded-full transition-all"
                    style={{ width: `${investigation.confidence * 100}%` }}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Observations */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5 text-blue-400" />
                Observations
                <Badge variant="secondary">{investigation.observations.length}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {investigation.observations.length === 0 ? (
                  <p className="text-gray-400 text-sm">No observations yet...</p>
                ) : (
                  investigation.observations.map((obs, i) => (
                    <div key={i} className="p-3 bg-gray-800 rounded-lg border border-gray-700">
                      <div className="flex items-center gap-2 mb-1">
                        {getSeverityIcon(obs.severity)}
                        <span className="font-medium text-sm">{obs.source}</span>
                        <Badge variant="outline" className="text-xs">
                          {obs.type}
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-300">{obs.summary}</p>
                      <p className="text-xs text-gray-500 mt-1">
                        {new Date(obs.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          {/* Actions */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-yellow-400" />
                Recommended Actions
                <Badge variant="secondary">{investigation.actions.length}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {investigation.actions.length === 0 ? (
                  <p className="text-gray-400 text-sm">No actions suggested yet...</p>
                ) : (
                  investigation.actions.map((action) => (
                    <div 
                      key={action.id} 
                      className={`p-4 rounded-lg border ${
                        action.status === 'pending' 
                          ? 'border-yellow-500/30 bg-yellow-500/5' 
                          : action.status === 'completed'
                          ? 'border-green-500/30 bg-green-500/5'
                          : action.status === 'failed'
                          ? 'border-red-500/30 bg-red-500/5'
                          : 'border-gray-700 bg-gray-800'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium">{action.description}</span>
                            <Badge className={`border ${getRiskColor(action.risk)}`}>
                              {action.risk} risk
                            </Badge>
                          </div>
                          <code className="text-xs bg-gray-900 px-2 py-1 rounded block mt-2 text-gray-400">
                            {action.command}
                          </code>
                          {action.output && (
                            <pre className="text-xs bg-gray-900 px-2 py-1 rounded mt-2 text-green-400 max-h-24 overflow-auto">
                              {action.output}
                            </pre>
                          )}
                          {action.error && (
                            <pre className="text-xs bg-gray-900 px-2 py-1 rounded mt-2 text-red-400 max-h-24 overflow-auto">
                              {action.error}
                            </pre>
                          )}
                        </div>
                      </div>
                      
                      {action.status === 'pending' && action.requires_approval && (
                        <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-700">
                          <Button 
                            size="sm" 
                            onClick={() => handleApprove(action.id)}
                            disabled={approveAction.isPending}
                            className="gap-1"
                          >
                            <ThumbsUp className="h-3 w-3" />
                            Approve
                          </Button>
                          <Button 
                            variant="outline" 
                            size="sm" 
                            onClick={() => handleReject(action.id)}
                            disabled={rejectAction.isPending}
                            className="gap-1"
                          >
                            <ThumbsDown className="h-3 w-3" />
                            Reject
                          </Button>
                        </div>
                      )}
                      
                      {action.status !== 'pending' && (
                        <div className="mt-3 pt-3 border-t border-gray-700 text-sm text-gray-400 flex items-center gap-2">
                          {action.status === 'completed' && <CheckCircle className="h-4 w-4 text-green-400" />}
                          {action.status === 'failed' && <XCircle className="h-4 w-4 text-red-400" />}
                          {action.status === 'executing' && <Clock className="h-4 w-4 text-blue-400 animate-pulse" />}
                          <span className="capitalize">{action.status}</span>
                          {action.executed_at && (
                            <span>• {new Date(action.executed_at).toLocaleTimeString()}</span>
                          )}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Similar Incidents */}
        {investigation.similar_incidents && investigation.similar_incidents.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-gray-400">
                Similar Past Incidents
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {investigation.similar_incidents.map((inc, i) => (
                  <Badge key={i} variant="outline" className="cursor-pointer hover:bg-gray-700">
                    {inc}
                    <ChevronRight className="h-3 w-3 ml-1" />
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
