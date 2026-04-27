'use client';

// Force dynamic rendering since these pages use client-side data fetching
export const dynamic = 'force-dynamic';

import React from 'react';
import { DashboardLayout } from '@/components/dashboard/layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { LoadingState, EmptyState } from '@/components/ui/spinner';
import { useInvestigations, useCreateInvestigation } from '@/hooks/use-api';
import {
  AlertTriangle,
  Search,
  Plus,
  Clock,
  CheckCircle,
  XCircle,
  Filter,
  ArrowUpDown,
} from 'lucide-react';
import Link from 'next/link';

function getSeverityColor(severity?: string) {
  switch (severity) {
    case 'critical': return 'bg-red-500/20 text-red-400 border-red-500/30';
    case 'high': return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
    case 'medium': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    case 'low': return 'bg-green-500/20 text-green-400 border-green-500/30';
    default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  }
}

function getStatusIcon(status: string) {
  switch (status) {
    case 'running': return <Clock className="h-4 w-4 text-blue-400 animate-pulse" />;
    case 'completed': return <CheckCircle className="h-4 w-4 text-green-400" />;
    case 'failed': return <XCircle className="h-4 w-4 text-red-400" />;
    case 'waiting_approval': return <AlertTriangle className="h-4 w-4 text-yellow-400" />;
    default: return <Clock className="h-4 w-4 text-gray-400" />;
  }
}

function NewInvestigationDialog({ onClose }: { onClose: () => void }) {
  const [issue, setIssue] = React.useState('');
  const [namespace, setNamespace] = React.useState('default');
  const createInvestigation = useCreateInvestigation();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!issue.trim()) return;
    
    await createInvestigation.mutateAsync({ issue, namespace });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <Card className="w-full max-w-lg mx-4">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="h-5 w-5 text-blue-400" />
            New Investigation
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm text-gray-400 block mb-2">
                Describe the issue
              </label>
              <Input
                value={issue}
                onChange={(e) => setIssue(e.target.value)}
                placeholder="e.g., high error rate on checkout-service"
                className="w-full"
                autoFocus
              />
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-2">
                Namespace
              </label>
              <Input
                value={namespace}
                onChange={(e) => setNamespace(e.target.value)}
                placeholder="default"
                className="w-full"
              />
            </div>
            <div className="flex gap-3 justify-end">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={!issue.trim() || createInvestigation.isPending}>
                {createInvestigation.isPending ? 'Starting...' : 'Start Investigation'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default function IncidentsPage() {
  const { data: investigations, isLoading, error } = useInvestigations();
  const [showNewDialog, setShowNewDialog] = React.useState(false);
  const [searchQuery, setSearchQuery] = React.useState('');
  const [statusFilter, setStatusFilter] = React.useState<string | null>(null);

  const filteredInvestigations = React.useMemo(() => {
    if (!investigations) return [];
    
    return investigations.filter(inv => {
      const matchesSearch = !searchQuery || 
        inv.issue.toLowerCase().includes(searchQuery.toLowerCase()) ||
        inv.namespace.toLowerCase().includes(searchQuery.toLowerCase());
      
      const matchesStatus = !statusFilter || inv.status === statusFilter;
      
      return matchesSearch && matchesStatus;
    });
  }, [investigations, searchQuery, statusFilter]);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Incidents</h1>
            <p className="text-gray-400 mt-1">Active and recent investigations</p>
          </div>
          <Button onClick={() => setShowNewDialog(true)} className="gap-2">
            <Plus className="h-4 w-4" />
            New Investigation
          </Button>
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search incidents..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-gray-400" />
                {['running', 'waiting_approval', 'completed', 'failed'].map(status => (
                  <Button
                    key={status}
                    variant={statusFilter === status ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setStatusFilter(statusFilter === status ? null : status)}
                    className="capitalize"
                  >
                    {status.replace('_', ' ')}
                  </Button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Investigation List */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-yellow-400" />
                All Incidents
                {investigations && (
                  <Badge variant="secondary">{investigations.length}</Badge>
                )}
              </CardTitle>
              <Button variant="ghost" size="sm" className="gap-1">
                <ArrowUpDown className="h-4 w-4" />
                Sort
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <LoadingState message="Loading incidents..." />
            ) : error ? (
              <EmptyState
                icon={XCircle}
                title="Failed to load incidents"
                description="Unable to connect to the API"
              />
            ) : filteredInvestigations.length === 0 ? (
              <EmptyState
                icon={CheckCircle}
                title={searchQuery || statusFilter ? 'No matching incidents' : 'No incidents yet'}
                description={searchQuery || statusFilter 
                  ? 'Try adjusting your filters' 
                  : 'Start an investigation to see it here'}
              />
            ) : (
              <div className="space-y-3">
                {filteredInvestigations.map(inv => (
                  <Link key={inv.id} href={`/incidents/${inv.id}`}>
                    <div className="p-4 rounded-lg border border-gray-700 hover:border-gray-600 hover:bg-gray-800/50 transition-colors cursor-pointer">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            {getStatusIcon(inv.status)}
                            <span className="font-medium truncate">{inv.issue}</span>
                          </div>
                          <div className="flex items-center gap-4 text-sm text-gray-400">
                            <span>Namespace: {inv.namespace}</span>
                            <span>Started: {new Date(inv.started_at).toLocaleString()}</span>
                            {inv.root_cause && (
                              <span className="text-green-400">
                                Confidence: {Math.round(inv.confidence * 100)}%
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {inv.severity && (
                            <Badge className={getSeverityColor(inv.severity)}>
                              {inv.severity}
                            </Badge>
                          )}
                          <Badge variant="outline" className="capitalize">
                            {inv.status.replace('_', ' ')}
                          </Badge>
                          {inv.actions.filter(a => a.status === 'pending').length > 0 && (
                            <Badge className="bg-yellow-500/20 text-yellow-400">
                              {inv.actions.filter(a => a.status === 'pending').length} pending
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {showNewDialog && (
        <NewInvestigationDialog onClose={() => setShowNewDialog(false)} />
      )}
    </DashboardLayout>
  );
}
