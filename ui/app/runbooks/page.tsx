'use client';

export const dynamic = 'force-dynamic';

import React from 'react';
import { DashboardLayout } from '@/components/dashboard/layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { LoadingState, EmptyState } from '@/components/ui/spinner';
import { useRunbooks, useExecuteRunbook } from '@/hooks/use-api';
import {
  BookOpen,
  Search,
  Play,
  Clock,
  CheckCircle,
  BarChart3,
  AlertTriangle,
  ChevronRight,
  Filter,
} from 'lucide-react';
import Link from 'next/link';

export default function RunbooksPage() {
  const { data: runbooks, isLoading, error } = useRunbooks();
  const executeRunbook = useExecuteRunbook();
  const [searchQuery, setSearchQuery] = React.useState('');
  const [categoryFilter, setCategoryFilter] = React.useState<string | null>(null);

  const categories = React.useMemo(() => {
    if (!runbooks) return [];
    return Array.from(new Set(runbooks.map(r => r.category)));
  }, [runbooks]);

  const filteredRunbooks = React.useMemo(() => {
    if (!runbooks) return [];
    
    return runbooks.filter(runbook => {
      const matchesSearch = !searchQuery || 
        runbook.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        runbook.description.toLowerCase().includes(searchQuery.toLowerCase());
      
      const matchesCategory = !categoryFilter || runbook.category === categoryFilter;
      
      return matchesSearch && matchesCategory;
    });
  }, [runbooks, searchQuery, categoryFilter]);

  const handleExecute = async (id: string) => {
    await executeRunbook.mutateAsync({ id });
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Runbooks</h1>
            <p className="text-gray-400 mt-1">Automated procedures and playbooks</p>
          </div>
          <Badge variant="secondary">
            {runbooks?.length || 0} runbooks
          </Badge>
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search runbooks..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
              {categories.length > 0 && (
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4 text-gray-400" />
                  {categories.map(category => (
                    <Button
                      key={category}
                      variant={categoryFilter === category ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setCategoryFilter(categoryFilter === category ? null : category)}
                    >
                      {category}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Runbook List */}
        {isLoading ? (
          <LoadingState message="Loading runbooks..." />
        ) : error ? (
          <Card>
            <CardContent className="py-12">
              <EmptyState
                icon={AlertTriangle}
                title="Failed to load runbooks"
                description="Unable to connect to the API"
              />
            </CardContent>
          </Card>
        ) : filteredRunbooks.length === 0 ? (
          <Card>
            <CardContent className="py-12">
              <EmptyState
                icon={BookOpen}
                title={searchQuery || categoryFilter ? 'No matching runbooks' : 'No runbooks available'}
                description={searchQuery || categoryFilter 
                  ? 'Try adjusting your filters' 
                  : 'Runbooks will appear here when configured'}
              />
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {filteredRunbooks.map(runbook => (
              <Card key={runbook.id} className="hover:border-gray-600 transition-colors">
                <CardContent className="py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <BookOpen className="h-5 w-5 text-blue-400" />
                        <h3 className="font-medium">{runbook.name}</h3>
                        <Badge variant="outline">{runbook.category}</Badge>
                      </div>
                      <p className="text-sm text-gray-400 mb-3">
                        {runbook.description}
                      </p>
                      
                      {/* Steps preview */}
                      <div className="flex flex-wrap gap-2 mb-3">
                        {runbook.steps.slice(0, 5).map((step, i) => (
                          <Badge key={step.id} variant="secondary" className="text-xs">
                            {i + 1}. {step.name}
                          </Badge>
                        ))}
                        {runbook.steps.length > 5 && (
                          <Badge variant="secondary" className="text-xs">
                            +{runbook.steps.length - 5} more
                          </Badge>
                        )}
                      </div>

                      {/* Triggers */}
                      {runbook.triggers.length > 0 && (
                        <div className="text-xs text-gray-500">
                          <span>Triggers: </span>
                          {runbook.triggers.join(', ')}
                        </div>
                      )}
                    </div>

                    <div className="flex flex-col items-end gap-2">
                      {/* Stats */}
                      <div className="flex items-center gap-4 text-sm text-gray-400">
                        <div className="flex items-center gap-1">
                          <BarChart3 className="h-4 w-4" />
                          {runbook.execution_count} runs
                        </div>
                        {runbook.avg_duration && (
                          <div className="flex items-center gap-1">
                            <Clock className="h-4 w-4" />
                            {Math.round(runbook.avg_duration / 60)}m avg
                          </div>
                        )}
                      </div>

                      {/* Last executed */}
                      {runbook.last_executed && (
                        <div className="text-xs text-gray-500">
                          Last run: {new Date(runbook.last_executed).toLocaleDateString()}
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          onClick={() => handleExecute(runbook.id)}
                          disabled={executeRunbook.isPending}
                          className="gap-1"
                        >
                          <Play className="h-3 w-3" />
                          Run
                        </Button>
                        <Link href={`/runbooks/${runbook.id}`}>
                          <Button variant="outline" size="sm" className="gap-1">
                            Details
                            <ChevronRight className="h-3 w-3" />
                          </Button>
                        </Link>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
