"use client";

import Link from "next/link";
import {
  Activity,
  Brain,
  Search,
  AlertTriangle,
  CheckCircle,
  Clock,
  ArrowRight,
  Zap,
} from "lucide-react";
import { useInvestigations, useMemory } from "@/lib/hooks";
import { formatRelativeTime, getSeverityColor, getStatusColor } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";

export default function DashboardPage() {
  const { data: investigations, isLoading: loadingInvestigations } =
    useInvestigations();
  const { data: memory, isLoading: loadingMemory } = useMemory();

  const recentInvestigations = investigations?.slice(0, 5) || [];
  const stats = memory?.stats;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">AutoSRE Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            AI-powered incident investigation and resolution
          </p>
        </div>
        <Link href="/investigate">
          <Button size="lg" className="gap-2">
            <Zap className="w-4 h-4" />
            Start Investigation
          </Button>
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-blue-500/10">
                <Activity className="w-6 h-6 text-blue-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {stats?.totalEpisodes || 0}
                </p>
                <p className="text-sm text-muted-foreground">
                  Total Investigations
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-green-500/10">
                <CheckCircle className="w-6 h-6 text-green-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {stats?.successRate
                    ? `${Math.round(stats.successRate * 100)}%`
                    : "N/A"}
                </p>
                <p className="text-sm text-muted-foreground">Success Rate</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-purple-500/10">
                <Brain className="w-6 h-6 text-purple-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {memory?.strategies?.length || 0}
                </p>
                <p className="text-sm text-muted-foreground">
                  Learned Strategies
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 rounded-lg bg-orange-500/10">
                <Clock className="w-6 h-6 text-orange-500" />
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {stats?.averageDuration
                    ? `${Math.round(stats.averageDuration / 60000)}m`
                    : "N/A"}
                </p>
                <p className="text-sm text-muted-foreground">Avg Resolution</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Investigations */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Recent Investigations</CardTitle>
            <Link
              href="/investigate"
              className="text-sm text-primary hover:underline"
            >
              View all
            </Link>
          </CardHeader>
          <CardContent>
            {loadingInvestigations ? (
              <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                  <div
                    key={i}
                    className="h-16 bg-muted animate-pulse rounded-lg"
                  />
                ))}
              </div>
            ) : recentInvestigations.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Search className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No investigations yet</p>
                <p className="text-sm">
                  Start your first investigation to see it here
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {recentInvestigations.map((inv) => (
                  <Link
                    key={inv.id}
                    href={`/investigate/${inv.id}`}
                    className="block p-4 rounded-lg border hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-xs font-medium ${getSeverityColor(inv.severity)}`}
                          >
                            {inv.severity}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(inv.status)}`}
                          >
                            {inv.status}
                          </span>
                        </div>
                        <h3 className="font-medium mt-1 truncate">
                          {inv.title}
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          {formatRelativeTime(inv.createdAt)} •{" "}
                          {inv.findingsCount} findings
                        </p>
                      </div>
                      <ArrowRight className="w-4 h-4 text-muted-foreground" />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Quick Actions & Top Skills */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Link href="/investigate" className="block">
                <Button variant="outline" className="w-full justify-start gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  New Investigation
                </Button>
              </Link>
              <Link href="/memory" className="block">
                <Button variant="outline" className="w-full justify-start gap-2">
                  <Brain className="w-4 h-4" />
                  Browse Memory
                </Button>
              </Link>
              <Link href="/config" className="block">
                <Button variant="outline" className="w-full justify-start gap-2">
                  <Activity className="w-4 h-4" />
                  Configure Skills
                </Button>
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Top Skills Used</CardTitle>
            </CardHeader>
            <CardContent>
              {loadingMemory ? (
                <div className="space-y-2">
                  {[...Array(5)].map((_, i) => (
                    <div
                      key={i}
                      className="h-8 bg-muted animate-pulse rounded"
                    />
                  ))}
                </div>
              ) : stats?.topSkills?.length ? (
                <div className="space-y-2">
                  {stats.topSkills.slice(0, 5).map((skill, idx) => (
                    <div
                      key={skill.skill}
                      className="flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground text-sm">
                          {idx + 1}.
                        </span>
                        <span className="text-sm">{skill.skill}</span>
                      </div>
                      <span className="text-sm text-muted-foreground">
                        {skill.count}x
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No skill usage data yet
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
