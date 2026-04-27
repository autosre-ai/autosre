'use client';

export const dynamic = 'force-dynamic';

import React from 'react';
import { DashboardLayout } from '@/components/dashboard/layout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useSystemStatus } from '@/hooks/use-api';
import {
  Settings,
  Database,
  Cloud,
  Bot,
  MessageSquare,
  Bell,
  Shield,
  Key,
  RefreshCw,
  CheckCircle,
  XCircle,
  ExternalLink,
} from 'lucide-react';

function IntegrationCard({
  name,
  icon: Icon,
  status,
  details,
  configLink,
}: {
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  status: 'connected' | 'error' | 'not_configured';
  details?: string;
  configLink?: string;
}) {
  return (
    <Card className={`
      ${status === 'connected' ? 'border-green-500/30' : ''}
      ${status === 'error' ? 'border-red-500/30' : ''}
    `}>
      <CardContent className="pt-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${
              status === 'connected' ? 'bg-green-500/10' : 
              status === 'error' ? 'bg-red-500/10' : 
              'bg-gray-500/10'
            }`}>
              <Icon className={`h-6 w-6 ${
                status === 'connected' ? 'text-green-400' : 
                status === 'error' ? 'text-red-400' : 
                'text-gray-400'
              }`} />
            </div>
            <div>
              <h3 className="font-medium">{name}</h3>
              <p className="text-sm text-gray-400">{details || 'Not configured'}</p>
            </div>
          </div>
          <Badge className={`
            ${status === 'connected' ? 'bg-green-500/20 text-green-400' : ''}
            ${status === 'error' ? 'bg-red-500/20 text-red-400' : ''}
            ${status === 'not_configured' ? 'bg-gray-500/20 text-gray-400' : ''}
          `}>
            {status === 'connected' && <CheckCircle className="h-3 w-3 mr-1" />}
            {status === 'error' && <XCircle className="h-3 w-3 mr-1" />}
            {status}
          </Badge>
        </div>
        {configLink && (
          <Button variant="outline" size="sm" className="w-full gap-1">
            Configure
            <ExternalLink className="h-3 w-3" />
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

export default function SettingsPage() {
  const { data: systemStatus, isLoading, refetch } = useSystemStatus();

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Settings</h1>
            <p className="text-gray-400 mt-1">Configure integrations and preferences</p>
          </div>
          <Button variant="outline" onClick={() => refetch()} className="gap-2">
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh Status
          </Button>
        </div>

        {/* Version Info */}
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Shield className="h-5 w-5 text-blue-400" />
                <div>
                  <h3 className="font-medium">OpenSRE</h3>
                  <p className="text-sm text-gray-400">
                    Version {systemStatus?.version || 'Loading...'}
                  </p>
                </div>
              </div>
              <Button variant="outline" size="sm">
                Check for Updates
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Integrations */}
        <div>
          <h2 className="text-lg font-semibold mb-4">Integrations</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <IntegrationCard
              name="Prometheus"
              icon={Database}
              status={systemStatus?.integrations?.prometheus?.status === 'connected' ? 'connected' : 
                      systemStatus?.integrations?.prometheus ? 'error' : 'not_configured'}
              details={systemStatus?.integrations?.prometheus?.details}
              configLink="#"
            />
            <IntegrationCard
              name="Kubernetes"
              icon={Cloud}
              status={systemStatus?.integrations?.kubernetes?.status === 'connected' ? 'connected' : 
                      systemStatus?.integrations?.kubernetes ? 'error' : 'not_configured'}
              details={systemStatus?.integrations?.kubernetes?.details}
              configLink="#"
            />
            <IntegrationCard
              name="LLM Provider"
              icon={Bot}
              status={systemStatus?.integrations?.llm?.status === 'connected' ? 'connected' : 
                      systemStatus?.integrations?.llm ? 'error' : 'not_configured'}
              details={systemStatus?.integrations?.llm?.details}
              configLink="#"
            />
            <IntegrationCard
              name="Slack"
              icon={MessageSquare}
              status="not_configured"
              details="Send notifications and approvals"
              configLink="#"
            />
            <IntegrationCard
              name="PagerDuty"
              icon={Bell}
              status="not_configured"
              details="Incident management"
              configLink="#"
            />
            <IntegrationCard
              name="API Keys"
              icon={Key}
              status="connected"
              details="Manage authentication"
              configLink="#"
            />
          </div>
        </div>

        {/* Configuration Sections */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* LLM Settings */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bot className="h-5 w-5 text-blue-400" />
                LLM Configuration
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm text-gray-400 block mb-2">Provider</label>
                <select className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm">
                  <option value="ollama">Ollama (Local)</option>
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                </select>
              </div>
              <div>
                <label className="text-sm text-gray-400 block mb-2">Model</label>
                <input
                  type="text"
                  defaultValue="llama3:8b"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 block mb-2">Base URL</label>
                <input
                  type="text"
                  defaultValue="http://localhost:11434"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm"
                />
              </div>
              <Button className="w-full">Save Configuration</Button>
            </CardContent>
          </Card>

          {/* Safety Settings */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-green-400" />
                Safety Settings
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Require Approval</p>
                  <p className="text-sm text-gray-400">Require human approval for all actions</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" defaultChecked className="sr-only peer" />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                </label>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">High-Risk Auto-Block</p>
                  <p className="text-sm text-gray-400">Automatically block high-risk actions</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" defaultChecked className="sr-only peer" />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                </label>
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Audit Logging</p>
                  <p className="text-sm text-gray-400">Log all actions for compliance</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" defaultChecked className="sr-only peer" />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-500"></div>
                </label>
              </div>
              <Button className="w-full">Save Settings</Button>
            </CardContent>
          </Card>
        </div>

        {/* Environment Variables Reference */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5 text-gray-400" />
              Environment Variables
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm overflow-x-auto">
              <div className="space-y-2">
                <div><span className="text-gray-500"># Prometheus</span></div>
                <div><span className="text-blue-400">OPENSRE_PROMETHEUS_URL</span>=http://prometheus:9090</div>
                <div className="pt-2"><span className="text-gray-500"># LLM Provider</span></div>
                <div><span className="text-blue-400">OPENSRE_LLM_PROVIDER</span>=ollama</div>
                <div><span className="text-blue-400">OPENSRE_OLLAMA_MODEL</span>=llama3:8b</div>
                <div><span className="text-blue-400">OPENSRE_OLLAMA_URL</span>=http://localhost:11434</div>
                <div className="pt-2"><span className="text-gray-500"># Slack (optional)</span></div>
                <div><span className="text-blue-400">OPENSRE_SLACK_BOT_TOKEN</span>=xoxb-...</div>
                <div><span className="text-blue-400">OPENSRE_SLACK_CHANNEL</span>=#alerts</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
