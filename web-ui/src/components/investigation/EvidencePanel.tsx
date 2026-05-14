import { useState } from 'react';
import {
  Activity,
  FileText,
  GitBranch,
  AlertCircle,
  ChevronDown,
  ChevronRight,
  Copy,
  Check,
  ExternalLink,
  TrendingUp,
  TrendingDown,
  Minus,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { Button, Card, CardContent } from '@/components/ui';
import { cn, formatRelativeTime } from '@/lib/utils';
import type { Evidence, MetricDataPoint } from '@/types';

interface EvidencePanelProps {
  evidence: Evidence[];
  className?: string;
}

type EvidenceTab = 'all' | 'metrics' | 'logs' | 'events' | 'alerts';

const tabConfig: Record<EvidenceTab, { label: string; icon: typeof Activity }> = {
  all: { label: 'All', icon: FileText },
  metrics: { label: 'Metrics', icon: Activity },
  logs: { label: 'Logs', icon: FileText },
  events: { label: 'K8s Events', icon: GitBranch },
  alerts: { label: 'Related Alerts', icon: AlertCircle },
};

const evidenceTypeToTab: Record<string, EvidenceTab> = {
  metric: 'metrics',
  log: 'logs',
  trace: 'events',
  config: 'events',
  command_output: 'logs',
  screenshot: 'all',
};

export function EvidencePanel({ evidence, className }: EvidencePanelProps) {
  const [activeTab, setActiveTab] = useState<EvidenceTab>('all');
  const [expandedItems, setExpandedItems] = useState<Set<string>>(
    new Set(evidence.slice(0, 3).map((e) => e.id))
  );

  const filteredEvidence = evidence.filter((e) => {
    if (activeTab === 'all') return true;
    return evidenceTypeToTab[e.type] === activeTab;
  });

  const toggleItem = (id: string) => {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Count evidence by type
  const counts = evidence.reduce((acc, e) => {
    const tab = evidenceTypeToTab[e.type] || 'all';
    acc[tab] = (acc[tab] || 0) + 1;
    return acc;
  }, {} as Record<EvidenceTab, number>);

  return (
    <div className={cn('space-y-4', className)}>
      {/* Tabs */}
      <div className="flex items-center gap-1 p-1 bg-stone-100 dark:bg-stone-800 rounded-lg overflow-x-auto">
        {(Object.keys(tabConfig) as EvidenceTab[]).map((tab) => {
          const config = tabConfig[tab];
          const count = tab === 'all' ? evidence.length : counts[tab] || 0;
          const Icon = config.icon;

          return (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors whitespace-nowrap',
                activeTab === tab
                  ? 'bg-white dark:bg-stone-700 text-stone-900 dark:text-white shadow-sm'
                  : 'text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-white'
              )}
            >
              <Icon className="w-4 h-4" />
              <span>{config.label}</span>
              {count > 0 && (
                <span
                  className={cn(
                    'px-1.5 py-0.5 text-xs rounded-full',
                    activeTab === tab
                      ? 'bg-forest/10 text-forest dark:bg-forest-light/20 dark:text-forest-light'
                      : 'bg-stone-200 dark:bg-stone-600 text-stone-600 dark:text-stone-300'
                  )}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Evidence list */}
      {filteredEvidence.length === 0 ? (
        <div className="text-center py-8 text-stone-500 dark:text-stone-400">
          <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No evidence in this category</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredEvidence.map((item) => (
            <EvidenceItem
              key={item.id}
              evidence={item}
              isExpanded={expandedItems.has(item.id)}
              onToggle={() => toggleItem(item.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface EvidenceItemProps {
  evidence: Evidence;
  isExpanded: boolean;
  onToggle: () => void;
}

function EvidenceItem({ evidence, isExpanded, onToggle }: EvidenceItemProps) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(evidence.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const typeIcons: Record<string, typeof Activity> = {
    metric: Activity,
    log: FileText,
    trace: GitBranch,
    config: FileText,
    command_output: FileText,
    screenshot: FileText,
  };

  const typeColors: Record<string, string> = {
    metric: 'text-blue-500 bg-blue-100 dark:bg-blue-900/30',
    log: 'text-purple-500 bg-purple-100 dark:bg-purple-900/30',
    trace: 'text-cyan-500 bg-cyan-100 dark:bg-cyan-900/30',
    config: 'text-amber-500 bg-amber-100 dark:bg-amber-900/30',
    command_output: 'text-green-500 bg-green-100 dark:bg-green-900/30',
    screenshot: 'text-pink-500 bg-pink-100 dark:bg-pink-900/30',
  };

  const Icon = typeIcons[evidence.type] || FileText;

  return (
    <Card className="overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full text-left p-4 hover:bg-stone-50 dark:hover:bg-stone-800/50 transition-colors"
      >
        <div className="flex items-start gap-3">
          <div
            className={cn(
              'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
              typeColors[evidence.type] || 'text-stone-500 bg-stone-100 dark:bg-stone-800'
            )}
          >
            <Icon className="w-4 h-4" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <h4 className="font-medium text-stone-900 dark:text-white truncate">
                {evidence.title}
              </h4>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className="text-xs text-stone-400 dark:text-stone-500">
                  {formatRelativeTime(evidence.timestamp)}
                </span>
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-stone-400" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-stone-400" />
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-stone-100 dark:bg-stone-700 text-stone-600 dark:text-stone-400">
                {evidence.source}
              </span>
              <span className="text-xs text-stone-500 dark:text-stone-400 capitalize">
                {evidence.type.replace('_', ' ')}
              </span>
            </div>
          </div>
        </div>
      </button>

      {isExpanded && (
        <CardContent className="pt-0 animate-in slide-in-from-top-2 duration-200">
          <div className="relative">
            {/* Render metric as a chart if it looks like metric data */}
            {evidence.type === 'metric' ? (
              <MetricChart content={evidence.content} />
            ) : (
              <pre className="text-sm bg-stone-900 dark:bg-stone-950 text-stone-100 p-4 rounded-lg overflow-x-auto font-mono whitespace-pre-wrap">
                {evidence.content}
              </pre>
            )}

            {/* Copy button */}
            <Button
              variant="ghost"
              size="sm"
              onClick={copyToClipboard}
              className="absolute top-2 right-2 bg-stone-800/80 hover:bg-stone-700 text-white"
            >
              {copied ? (
                <>
                  <Check className="w-3 h-3 mr-1" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3 mr-1" />
                  Copy
                </>
              )}
            </Button>
          </div>

          {/* Action links */}
          <div className="flex items-center gap-3 mt-3">
            <Button variant="ghost" size="sm" className="text-xs">
              <ExternalLink className="w-3 h-3 mr-1" />
              View in {evidence.source}
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  );
}

// Simple metric chart for metric evidence
function MetricChart({ content }: { content: string }) {
  // Parse the content to extract metric info
  // For now, generate sample data based on content
  const sampleData: MetricDataPoint[] = Array.from({ length: 20 }, (_, i) => {
    const baseValue = content.includes('5200') ? 200 : 100;
    const spike = i > 10 && i < 15 ? 5000 : 0;
    return {
      timestamp: new Date(Date.now() - (20 - i) * 60000).toISOString(),
      value: baseValue + Math.random() * 50 + spike,
    };
  });

  const maxValue = Math.max(...sampleData.map((d) => d.value));
  const minValue = Math.min(...sampleData.map((d) => d.value));
  const avgValue = sampleData.reduce((a, b) => a + b.value, 0) / sampleData.length;
  const trend = sampleData[sampleData.length - 1].value > sampleData[0].value;

  return (
    <div className="space-y-4">
      {/* Metric summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="p-3 rounded-lg bg-stone-100 dark:bg-stone-800">
          <p className="text-xs text-stone-500 dark:text-stone-400 mb-1">Current</p>
          <div className="flex items-center gap-1">
            {trend ? (
              <TrendingUp className="w-4 h-4 text-red-500" />
            ) : (
              <TrendingDown className="w-4 h-4 text-green-500" />
            )}
            <span className="font-semibold text-stone-900 dark:text-white">
              {Math.round(sampleData[sampleData.length - 1].value)}ms
            </span>
          </div>
        </div>
        <div className="p-3 rounded-lg bg-stone-100 dark:bg-stone-800">
          <p className="text-xs text-stone-500 dark:text-stone-400 mb-1">Average</p>
          <div className="flex items-center gap-1">
            <Minus className="w-4 h-4 text-stone-400" />
            <span className="font-semibold text-stone-900 dark:text-white">
              {Math.round(avgValue)}ms
            </span>
          </div>
        </div>
        <div className="p-3 rounded-lg bg-stone-100 dark:bg-stone-800">
          <p className="text-xs text-stone-500 dark:text-stone-400 mb-1">Peak</p>
          <div className="flex items-center gap-1">
            <TrendingUp className="w-4 h-4 text-red-500" />
            <span className="font-semibold text-stone-900 dark:text-white">
              {Math.round(maxValue)}ms
            </span>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="h-48 bg-stone-900 dark:bg-stone-950 rounded-lg p-4">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={sampleData}>
            <XAxis
              dataKey="timestamp"
              tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              stroke="#78716c"
              fontSize={10}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="#78716c"
              fontSize={10}
              tickLine={false}
              axisLine={false}
              domain={[0, 'auto']}
              tickFormatter={(v) => `${v}ms`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1c1917',
                border: '1px solid #44403c',
                borderRadius: '8px',
                fontSize: '12px',
              }}
              labelFormatter={(t) => new Date(t as string).toLocaleString()}
              formatter={(value) => [`${Math.round(value as number)}ms`, 'Latency']}
            />
            <ReferenceLine
              y={5000}
              stroke="#ef4444"
              strokeDasharray="5 5"
              label={{ value: 'Threshold', fill: '#ef4444', fontSize: 10, position: 'right' }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: '#3b82f6' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Text content below chart */}
      <p className="text-sm text-stone-400 dark:text-stone-500 font-mono">{content}</p>
    </div>
  );
}

export default EvidencePanel;
