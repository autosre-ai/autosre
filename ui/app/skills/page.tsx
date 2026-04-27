'use client';

export const dynamic = 'force-dynamic';

import React from 'react';
import { DashboardLayout } from '@/components/dashboard/layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { LoadingState, EmptyState } from '@/components/ui/spinner';
import { useSkills } from '@/hooks/use-api';
import {
  Wrench,
  Search,
  Activity,
  Shield,
  MessageSquare,
  Stethoscope,
  Code,
  ChevronRight,
} from 'lucide-react';
import Link from 'next/link';

function getCategoryIcon(category: string) {
  switch (category) {
    case 'diagnostic': return <Stethoscope className="h-5 w-5 text-blue-400" />;
    case 'remediation': return <Wrench className="h-5 w-5 text-yellow-400" />;
    case 'monitoring': return <Activity className="h-5 w-5 text-green-400" />;
    case 'communication': return <MessageSquare className="h-5 w-5 text-purple-400" />;
    default: return <Code className="h-5 w-5 text-gray-400" />;
  }
}

function getCategoryColor(category: string) {
  switch (category) {
    case 'diagnostic': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    case 'remediation': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    case 'monitoring': return 'bg-green-500/20 text-green-400 border-green-500/30';
    case 'communication': return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  }
}

export default function SkillsPage() {
  const { data: skills, isLoading, error } = useSkills();
  const [searchQuery, setSearchQuery] = React.useState('');
  const [categoryFilter, setCategoryFilter] = React.useState<string | null>(null);

  const filteredSkills = React.useMemo(() => {
    if (!skills) return [];
    
    return skills.filter(skill => {
      const matchesSearch = !searchQuery || 
        skill.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        skill.description.toLowerCase().includes(searchQuery.toLowerCase());
      
      const matchesCategory = !categoryFilter || skill.category === categoryFilter;
      
      return matchesSearch && matchesCategory;
    });
  }, [skills, searchQuery, categoryFilter]);

  const categories = ['diagnostic', 'remediation', 'monitoring', 'communication'];

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold">Skills</h1>
          <p className="text-gray-400 mt-1">Available capabilities for agents</p>
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search skills..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
                />
              </div>
              <div className="flex items-center gap-2">
                {categories.map(category => (
                  <Button
                    key={category}
                    variant={categoryFilter === category ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setCategoryFilter(categoryFilter === category ? null : category)}
                    className="capitalize gap-1"
                  >
                    {getCategoryIcon(category)}
                    {category}
                  </Button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Skills Grid */}
        {isLoading ? (
          <LoadingState message="Loading skills..." />
        ) : error ? (
          <Card>
            <CardContent className="py-12">
              <EmptyState
                icon={Shield}
                title="Failed to load skills"
                description="Unable to connect to the API"
              />
            </CardContent>
          </Card>
        ) : filteredSkills.length === 0 ? (
          <Card>
            <CardContent className="py-12">
              <EmptyState
                icon={Wrench}
                title={searchQuery || categoryFilter ? 'No matching skills' : 'No skills available'}
                description={searchQuery || categoryFilter 
                  ? 'Try adjusting your filters' 
                  : 'Skills will appear here when configured'}
              />
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredSkills.map(skill => (
              <Card key={skill.id} className="hover:border-gray-600 transition-colors">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      {getCategoryIcon(skill.category)}
                      <CardTitle className="text-lg">{skill.name}</CardTitle>
                    </div>
                    <Badge className={getCategoryColor(skill.category)}>
                      {skill.category}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-400 mb-4">
                    {skill.description}
                  </p>

                  {/* Parameters */}
                  {skill.parameters.length > 0 && (
                    <div className="mb-4">
                      <p className="text-xs text-gray-500 mb-2">Parameters:</p>
                      <div className="flex flex-wrap gap-1">
                        {skill.parameters.map(param => (
                          <Badge 
                            key={param.name} 
                            variant="outline" 
                            className={`text-xs ${param.required ? 'border-blue-500/30' : ''}`}
                          >
                            {param.name}
                            {param.required && <span className="text-red-400 ml-1">*</span>}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Examples */}
                  {skill.examples.length > 0 && (
                    <div className="mb-4">
                      <p className="text-xs text-gray-500 mb-2">Examples:</p>
                      <div className="space-y-1">
                        {skill.examples.slice(0, 2).map((example, i) => (
                          <code key={i} className="text-xs bg-gray-800 px-2 py-1 rounded block text-gray-400">
                            {example}
                          </code>
                        ))}
                      </div>
                    </div>
                  )}

                  <Link href={`/skills/${skill.id}`}>
                    <Button variant="outline" size="sm" className="w-full gap-1">
                      View Documentation
                      <ChevronRight className="h-3 w-3" />
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
