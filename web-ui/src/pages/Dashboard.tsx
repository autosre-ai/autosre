import { Link } from 'react-router-dom';
import { Header } from '@/components/layout';
import { Card, CardContent, CardHeader, CardTitle, Button, SeverityBadge, StatusBadge } from '@/components/ui';
import { AlertTriangle, Search, Clock, TrendingUp, Activity, ArrowRight, Zap, BookOpen } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { mockDashboardMetrics, mockSystemHealth, mockAlerts, mockInvestigations, mockAlertTrend, generateMetricSeries } from '@/data/mockData';
import { formatRelativeTime, cn } from '@/lib/utils';

const metricSeries = generateMetricSeries(24, 30);

const statCards = [
  { title: 'Active Alerts', value: mockDashboardMetrics.activeAlerts, icon: AlertTriangle, color: 'text-red-500', bgColor: 'bg-red-100 dark:bg-red-900/30', href: '/alerts?status=firing' },
  { title: 'Critical', value: mockDashboardMetrics.criticalAlerts, icon: Zap, color: 'text-orange-500', bgColor: 'bg-orange-100 dark:bg-orange-900/30', href: '/alerts?severity=critical' },
  { title: 'Investigations', value: mockDashboardMetrics.activeInvestigations, icon: Search, color: 'text-blue-500', bgColor: 'bg-blue-100 dark:bg-blue-900/30', href: '/investigations' },
  { title: 'MTTR', value: `${mockDashboardMetrics.mttr}m`, icon: Clock, color: 'text-green-500', bgColor: 'bg-green-100 dark:bg-green-900/30', href: '#' },
];

export function DashboardPage() {
  const activeAlerts = mockAlerts.filter((a) => a.status === 'firing').slice(0, 5);
  const activeInvestigation = mockInvestigations.find((i) => i.status === 'in_progress');

  return (
    <div>
      <Header title="Dashboard" subtitle="Overview of your system health and incidents" actions={<Link to="/chat"><Button size="sm"><Zap className="w-4 h-4" />Ask SRE Assistant</Button></Link>} />

      <div className="p-6 lg:p-8 space-y-6">
        {/* Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {statCards.map((stat) => (
            <Link key={stat.title} to={stat.href}>
              <Card hover className="h-full">
                <CardContent className="py-4">
                  <div className="flex items-center gap-4">
                    <div className={cn('p-3 rounded-xl', stat.bgColor)}><stat.icon className={cn('w-6 h-6', stat.color)} /></div>
                    <div>
                      <p className="text-2xl font-bold text-stone-900 dark:text-white">{stat.value}</p>
                      <p className="text-sm text-stone-500">{stat.title}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

        {/* Main content grid */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* System Health */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2"><Activity className="w-5 h-5" />System Health</CardTitle>
                <StatusBadge status={mockSystemHealth.status} />
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {mockSystemHealth.services.map((service) => (
                <div key={service.name} className="flex items-center justify-between py-2 border-b border-stone-100 dark:border-stone-800 last:border-0">
                  <div className="flex items-center gap-3">
                    <div className={cn('w-2 h-2 rounded-full', service.status === 'healthy' && 'bg-green-500', service.status === 'warning' && 'bg-yellow-500', service.status === 'error' && 'bg-red-500')} />
                    <span className="text-sm font-medium text-stone-700 dark:text-stone-300">{service.name}</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-stone-500">
                    <span>{service.latencyP99}ms</span>
                    <span>{service.errorRate}% err</span>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Request Metrics Chart */}
          <Card className="lg:col-span-2">
            <CardHeader><CardTitle className="flex items-center gap-2"><TrendingUp className="w-5 h-5" />Request Metrics (24h)</CardTitle></CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={metricSeries[0].data}>
                    <defs><linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#1e3a2f" stopOpacity={0.3} /><stop offset="95%" stopColor="#1e3a2f" stopOpacity={0} /></linearGradient></defs>
                    <XAxis dataKey="timestamp" tickFormatter={(val) => new Date(val).toLocaleTimeString('en-US', { hour: '2-digit' })} stroke="#a8a29e" tick={{ fontSize: 12 }} />
                    <YAxis stroke="#a8a29e" tick={{ fontSize: 12 }} />
                    <Tooltip contentStyle={{ backgroundColor: '#1c1917', border: '1px solid #44403c', borderRadius: '8px' }} labelFormatter={(val) => new Date(val).toLocaleString()} />
                    <Area type="monotone" dataKey="value" stroke="#1e3a2f" strokeWidth={2} fillOpacity={1} fill="url(#colorRequests)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Bottom grid */}
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Active Alerts */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2"><AlertTriangle className="w-5 h-5 text-red-500" />Active Alerts</CardTitle>
                <Link to="/alerts"><Button variant="ghost" size="sm">View all <ArrowRight className="w-4 h-4 ml-1" /></Button></Link>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {activeAlerts.length === 0 ? (
                <div className="text-center py-8 text-stone-500">No active alerts 🎉</div>
              ) : (
                activeAlerts.map((alert) => (
                  <Link key={alert.id} to={`/alerts/${alert.id}`} className="block p-3 rounded-lg hover:bg-stone-50 dark:hover:bg-stone-800/50 transition-colors">
                    <div className="flex items-start gap-3">
                      <SeverityBadge severity={alert.severity} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-stone-900 dark:text-white truncate">{alert.title}</p>
                        <p className="text-xs text-stone-500 mt-0.5">{alert.service} • {formatRelativeTime(alert.startsAt)}</p>
                      </div>
                    </div>
                  </Link>
                ))
              )}
            </CardContent>
          </Card>

          {/* Alert Trend */}
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><TrendingUp className="w-5 h-5" />Alert Trend (7 days)</CardTitle></CardHeader>
            <CardContent>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={mockAlertTrend}>
                    <XAxis dataKey="date" stroke="#a8a29e" tick={{ fontSize: 12 }} />
                    <YAxis stroke="#a8a29e" tick={{ fontSize: 12 }} />
                    <Tooltip contentStyle={{ backgroundColor: '#1c1917', border: '1px solid #44403c', borderRadius: '8px' }} />
                    <Bar dataKey="critical" stackId="a" fill="#ef4444" />
                    <Bar dataKey="high" stackId="a" fill="#f97316" />
                    <Bar dataKey="medium" stackId="a" fill="#eab308" />
                    <Bar dataKey="low" stackId="a" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Active Investigation */}
        {activeInvestigation && (
          <Card className="border-forest/30 dark:border-forest/50">
            <CardHeader className="bg-forest/5 dark:bg-forest/10">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2"><Search className="w-5 h-5 text-forest" />Active Investigation</CardTitle>
                <Link to={`/investigations/${activeInvestigation.id}`}><Button size="sm">View Details <ArrowRight className="w-4 h-4 ml-1" /></Button></Link>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-start gap-4">
                <div className="flex-1">
                  <h4 className="font-semibold text-stone-900 dark:text-white">{activeInvestigation.alertTitle}</h4>
                  <p className="text-sm text-stone-500 mt-1">Started {formatRelativeTime(activeInvestigation.startedAt)} • {activeInvestigation.steps.length} steps completed</p>
                  <div className="mt-4 flex items-center gap-2">
                    <SeverityBadge severity={activeInvestigation.severity} />
                    <StatusBadge status={activeInvestigation.status} />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Quick Actions */}
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Link to="/chat"><Card hover className="h-full"><CardContent className="py-6 text-center"><Search className="w-8 h-8 mx-auto text-forest mb-3" /><p className="font-medium text-stone-900 dark:text-white">Start Investigation</p><p className="text-sm text-stone-500 mt-1">AI-powered analysis</p></CardContent></Card></Link>
          <Link to="/runbooks"><Card hover className="h-full"><CardContent className="py-6 text-center"><BookOpen className="w-8 h-8 mx-auto text-blue-500 mb-3" /><p className="font-medium text-stone-900 dark:text-white">Run Playbook</p><p className="text-sm text-stone-500 mt-1">Execute remediation</p></CardContent></Card></Link>
          <Link to="/alerts"><Card hover className="h-full"><CardContent className="py-6 text-center"><AlertTriangle className="w-8 h-8 mx-auto text-orange-500 mb-3" /><p className="font-medium text-stone-900 dark:text-white">View Alerts</p><p className="text-sm text-stone-500 mt-1">All active alerts</p></CardContent></Card></Link>
          <Link to="/settings"><Card hover className="h-full"><CardContent className="py-6 text-center"><Activity className="w-8 h-8 mx-auto text-purple-500 mb-3" /><p className="font-medium text-stone-900 dark:text-white">Integrations</p><p className="text-sm text-stone-500 mt-1">Manage connections</p></CardContent></Card></Link>
        </div>
      </div>
    </div>
  );
}
