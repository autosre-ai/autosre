import { useState } from 'react';
import { 
  Cog6ToothIcon,
  ServerIcon,
  KeyIcon,
  BellIcon,
  SunIcon,
  MoonIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  EyeIcon,
  EyeSlashIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import { useTheme } from '@/context/ThemeContext';

interface IntegrationStatus {
  connected: boolean;
  lastChecked?: string;
}

export function SettingsPage() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  
  const toggleTheme = () => {
    setTheme(resolvedTheme === 'dark' ? 'light' : 'dark');
  };
  const [prometheusUrl, setPrometheusUrl] = useState('http://localhost:9090');
  const [kubeContext, setKubeContext] = useState('default');
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [notifications, setNotifications] = useState({
    criticalAlerts: true,
    warningAlerts: true,
    investigationUpdates: true,
    emailDigest: false,
  });
  
  const [integrationStatus, setIntegrationStatus] = useState<{
    prometheus: IntegrationStatus;
    kubernetes: IntegrationStatus;
  }>({
    prometheus: { connected: true, lastChecked: '2 min ago' },
    kubernetes: { connected: true, lastChecked: '5 min ago' },
  });

  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setSaving(false);
  };

  const handleTestConnection = async (integration: 'prometheus' | 'kubernetes') => {
    setTesting(integration);
    // Simulate connection test
    await new Promise((resolve) => setTimeout(resolve, 1500));
    setIntegrationStatus((prev) => ({
      ...prev,
      [integration]: { connected: true, lastChecked: 'just now' },
    }));
    setTesting(null);
  };

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-stone-100 dark:bg-stone-800 rounded-lg">
            <Cog6ToothIcon className="w-6 h-6 text-stone-600 dark:text-stone-400" />
          </div>
          <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">
            Settings
          </h1>
        </div>
        <p className="text-stone-500 dark:text-stone-400">
          Configure integrations, API keys, and preferences
        </p>
      </div>

      <div className="space-y-6">
        {/* Integrations Section */}
        <section className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 overflow-hidden">
          <div className="px-6 py-4 border-b border-stone-200 dark:border-stone-700">
            <div className="flex items-center gap-2">
              <ServerIcon className="w-5 h-5 text-stone-500 dark:text-stone-400" />
              <h2 className="text-lg font-medium text-stone-900 dark:text-stone-100">
                Integrations
              </h2>
            </div>
          </div>
          
          <div className="p-6 space-y-6">
            {/* Prometheus */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-stone-700 dark:text-stone-300">
                  Prometheus URL
                </label>
                <div className="flex items-center gap-2">
                  {integrationStatus.prometheus.connected ? (
                    <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                      <CheckCircleIcon className="w-4 h-4" />
                      Connected
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
                      <ExclamationCircleIcon className="w-4 h-4" />
                      Disconnected
                    </span>
                  )}
                  {integrationStatus.prometheus.lastChecked && (
                    <span className="text-xs text-stone-400">
                      · {integrationStatus.prometheus.lastChecked}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                <input
                  type="url"
                  value={prometheusUrl}
                  onChange={(e) => setPrometheusUrl(e.target.value)}
                  placeholder="http://prometheus:9090"
                  className="flex-1 px-3 py-2 text-sm bg-stone-50 dark:bg-stone-900 border border-stone-200 dark:border-stone-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 dark:focus:ring-amber-400 text-stone-900 dark:text-stone-100"
                />
                <button
                  onClick={() => handleTestConnection('prometheus')}
                  disabled={testing === 'prometheus'}
                  className="px-4 py-2 text-sm font-medium text-stone-700 dark:text-stone-300 bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-600 transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {testing === 'prometheus' ? (
                    <ArrowPathIcon className="w-4 h-4 animate-spin" />
                  ) : (
                    'Test'
                  )}
                </button>
              </div>
            </div>

            {/* Kubernetes */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-stone-700 dark:text-stone-300">
                  Kubernetes Context
                </label>
                <div className="flex items-center gap-2">
                  {integrationStatus.kubernetes.connected ? (
                    <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
                      <CheckCircleIcon className="w-4 h-4" />
                      Connected
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
                      <ExclamationCircleIcon className="w-4 h-4" />
                      Disconnected
                    </span>
                  )}
                  {integrationStatus.kubernetes.lastChecked && (
                    <span className="text-xs text-stone-400">
                      · {integrationStatus.kubernetes.lastChecked}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                <select
                  value={kubeContext}
                  onChange={(e) => setKubeContext(e.target.value)}
                  className="flex-1 px-3 py-2 text-sm bg-stone-50 dark:bg-stone-900 border border-stone-200 dark:border-stone-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 dark:focus:ring-amber-400 text-stone-900 dark:text-stone-100"
                >
                  <option value="default">default</option>
                  <option value="production">production</option>
                  <option value="staging">staging</option>
                  <option value="development">development</option>
                </select>
                <button
                  onClick={() => handleTestConnection('kubernetes')}
                  disabled={testing === 'kubernetes'}
                  className="px-4 py-2 text-sm font-medium text-stone-700 dark:text-stone-300 bg-stone-100 dark:bg-stone-700 rounded-lg hover:bg-stone-200 dark:hover:bg-stone-600 transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {testing === 'kubernetes' ? (
                    <ArrowPathIcon className="w-4 h-4 animate-spin" />
                  ) : (
                    'Test'
                  )}
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* API Keys Section */}
        <section className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 overflow-hidden">
          <div className="px-6 py-4 border-b border-stone-200 dark:border-stone-700">
            <div className="flex items-center gap-2">
              <KeyIcon className="w-5 h-5 text-stone-500 dark:text-stone-400" />
              <h2 className="text-lg font-medium text-stone-900 dark:text-stone-100">
                API Keys
              </h2>
            </div>
          </div>
          
          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
                AutoSRE API Key
              </label>
              <div className="relative">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Enter your API key"
                  className="w-full px-3 py-2 pr-10 text-sm bg-stone-50 dark:bg-stone-900 border border-stone-200 dark:border-stone-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 dark:focus:ring-amber-400 text-stone-900 dark:text-stone-100 font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300"
                >
                  {showApiKey ? (
                    <EyeSlashIcon className="w-5 h-5" />
                  ) : (
                    <EyeIcon className="w-5 h-5" />
                  )}
                </button>
              </div>
              <p className="mt-2 text-xs text-stone-500 dark:text-stone-400">
                Used for authenticating with the AutoSRE backend API
              </p>
            </div>

            <div className="flex gap-2">
              <button className="px-4 py-2 text-sm font-medium text-amber-700 dark:text-amber-300 bg-amber-100 dark:bg-amber-900/30 rounded-lg hover:bg-amber-200 dark:hover:bg-amber-900/50 transition-colors">
                Generate New Key
              </button>
              <button className="px-4 py-2 text-sm font-medium text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900/30 rounded-lg hover:bg-red-200 dark:hover:bg-red-900/50 transition-colors">
                Revoke Key
              </button>
            </div>
          </div>
        </section>

        {/* Appearance Section */}
        <section className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 overflow-hidden">
          <div className="px-6 py-4 border-b border-stone-200 dark:border-stone-700">
            <div className="flex items-center gap-2">
              <SunIcon className="w-5 h-5 text-stone-500 dark:text-stone-400" />
              <h2 className="text-lg font-medium text-stone-900 dark:text-stone-100">
                Appearance
              </h2>
            </div>
          </div>
          
          <div className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-stone-700 dark:text-stone-300">
                  Theme
                </p>
                <p className="text-xs text-stone-500 dark:text-stone-400">
                  Choose between light and dark mode
                </p>
              </div>
              <button
                onClick={toggleTheme}
                className="relative inline-flex h-10 w-20 items-center rounded-full bg-stone-200 dark:bg-stone-700 transition-colors"
              >
                <span
                  className={`inline-flex h-8 w-8 items-center justify-center rounded-full bg-white dark:bg-stone-600 shadow-sm transition-transform ${
                    resolvedTheme === 'dark' ? 'translate-x-10' : 'translate-x-1'
                  }`}
                >
                  {resolvedTheme === 'dark' ? (
                    <MoonIcon className="w-4 h-4 text-amber-500" />
                  ) : (
                    <SunIcon className="w-4 h-4 text-amber-500" />
                  )}
                </span>
              </button>
            </div>
          </div>
        </section>

        {/* Notifications Section */}
        <section className="bg-white dark:bg-stone-800 rounded-xl border border-stone-200 dark:border-stone-700 overflow-hidden">
          <div className="px-6 py-4 border-b border-stone-200 dark:border-stone-700">
            <div className="flex items-center gap-2">
              <BellIcon className="w-5 h-5 text-stone-500 dark:text-stone-400" />
              <h2 className="text-lg font-medium text-stone-900 dark:text-stone-100">
                Notifications
              </h2>
            </div>
          </div>
          
          <div className="p-6 space-y-4">
            {[
              { key: 'criticalAlerts', label: 'Critical Alerts', desc: 'Get notified for critical severity alerts' },
              { key: 'warningAlerts', label: 'Warning Alerts', desc: 'Get notified for warning severity alerts' },
              { key: 'investigationUpdates', label: 'Investigation Updates', desc: 'Get notified when investigations are updated' },
              { key: 'emailDigest', label: 'Daily Email Digest', desc: 'Receive a daily summary of all alerts' },
            ].map((item) => (
              <div key={item.key} className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-stone-700 dark:text-stone-300">
                    {item.label}
                  </p>
                  <p className="text-xs text-stone-500 dark:text-stone-400">
                    {item.desc}
                  </p>
                </div>
                <button
                  onClick={() =>
                    setNotifications((prev) => ({
                      ...prev,
                      [item.key]: !prev[item.key as keyof typeof notifications],
                    }))
                  }
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    notifications[item.key as keyof typeof notifications]
                      ? 'bg-amber-500'
                      : 'bg-stone-300 dark:bg-stone-600'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
                      notifications[item.key as keyof typeof notifications]
                        ? 'translate-x-6'
                        : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            ))}
          </div>
        </section>

        {/* Save Button */}
        <div className="flex justify-end pt-4">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2.5 text-sm font-medium text-white bg-amber-500 rounded-lg hover:bg-amber-600 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {saving ? (
              <>
                <ArrowPathIcon className="w-4 h-4 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Changes'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
