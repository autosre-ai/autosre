import { useState, useMemo } from 'react';
import { Header } from '@/components/layout';
import {
  Card,
  CardContent,
  Button,
  Badge,
  Select,
  Input,
  EmptyState,
  Modal,
  ConfirmDialog,
} from '@/components/ui';
import {
  Search,
  Plus,
  BookOpen,
  Play,
  Clock,
  History,
  Eye,
  Edit,
  ChevronRight,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Loader2,
  Filter,
  Tag,
  User,
  Terminal,
  FileText,
  Shield,
  Zap,
} from 'lucide-react';
import { mockRunbooks } from '@/data/mockData';
import { formatRelativeTime, cn } from '@/lib/utils';
import type { RunbookUI as Runbook, ExecutionStatus, RiskLevel } from '@/types';

// ============================================================================
// Mock execution history data
// ============================================================================
interface ExecutionHistoryItem {
  id: string;
  runbookId: string;
  status: ExecutionStatus;
  triggeredBy: string;
  startedAt: string;
  completedAt?: string;
  dryRun: boolean;
  parameters: Record<string, unknown>;
}

const mockExecutionHistory: ExecutionHistoryItem[] = [
  {
    id: 'exec-001',
    runbookId: 'rb-001',
    status: 'completed',
    triggeredBy: 'auto-sre',
    startedAt: new Date(Date.now() - 2 * 3600000).toISOString(),
    completedAt: new Date(Date.now() - 2 * 3600000 + 180000).toISOString(),
    dryRun: false,
    parameters: { service: 'payment-gateway' },
  },
  {
    id: 'exec-002',
    runbookId: 'rb-001',
    status: 'completed',
    triggeredBy: 'john.doe@example.com',
    startedAt: new Date(Date.now() - 5 * 3600000).toISOString(),
    completedAt: new Date(Date.now() - 5 * 3600000 + 240000).toISOString(),
    dryRun: true,
    parameters: { service: 'checkout-api' },
  },
  {
    id: 'exec-003',
    runbookId: 'rb-002',
    status: 'failed',
    triggeredBy: 'auto-sre',
    startedAt: new Date(Date.now() - 15 * 86400000).toISOString(),
    completedAt: new Date(Date.now() - 15 * 86400000 + 60000).toISOString(),
    dryRun: false,
    parameters: {},
  },
];

// ============================================================================
// Filter options
// ============================================================================
const categoryOptions = [
  { value: '', label: 'All Categories' },
  { value: 'Performance', label: 'Performance' },
  { value: 'Database', label: 'Database' },
  { value: 'Kubernetes', label: 'Kubernetes' },
  { value: 'Security', label: 'Security' },
  { value: 'Network', label: 'Network' },
];

const statusOptions = [
  { value: '', label: 'All Statuses' },
  { value: 'published', label: 'Published' },
  { value: 'draft', label: 'Draft' },
  { value: 'deprecated', label: 'Deprecated' },
];

// ============================================================================
// Helper components
// ============================================================================
function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    published: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    draft: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
    deprecated: 'bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400',
    active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  };

  return (
    <Badge className={cn('capitalize', colors[status] || colors.draft)}>
      {status}
    </Badge>
  );
}

function RiskBadge({ risk }: { risk: RiskLevel }) {
  const colors: Record<RiskLevel, string> = {
    low: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    medium: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
    high: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    critical: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  };

  return (
    <Badge className={cn('capitalize', colors[risk])}>
      <Shield className="w-3 h-3 mr-1" />
      {risk} Risk
    </Badge>
  );
}

function ExecutionStatusBadge({ status }: { status: ExecutionStatus }) {
  const config: Record<ExecutionStatus, { icon: typeof CheckCircle; color: string }> = {
    completed: { icon: CheckCircle, color: 'text-green-600 dark:text-green-400' },
    failed: { icon: XCircle, color: 'text-red-600 dark:text-red-400' },
    running: { icon: Loader2, color: 'text-blue-600 dark:text-blue-400' },
    pending: { icon: Clock, color: 'text-yellow-600 dark:text-yellow-400' },
    cancelled: { icon: XCircle, color: 'text-stone-500 dark:text-stone-400' },
  };

  const { icon: Icon, color } = config[status];

  return (
    <span className={cn('flex items-center gap-1 text-sm', color)}>
      <Icon className={cn('w-4 h-4', status === 'running' && 'animate-spin')} />
      <span className="capitalize">{status}</span>
    </span>
  );
}

// ============================================================================
// Main Page Component
// ============================================================================
export function RunbooksPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  // Modal states
  const [selectedRunbook, setSelectedRunbook] = useState<Runbook | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showExecuteConfirm, setShowExecuteConfirm] = useState(false);
  const [isDryRun, setIsDryRun] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);

  // Filter runbooks
  const filteredRunbooks = useMemo(() => {
    return mockRunbooks.filter((rb) => {
      const matchesSearch =
        !searchQuery ||
        rb.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        rb.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        rb.tags.some((tag) => tag.toLowerCase().includes(searchQuery.toLowerCase()));
      const matchesCategory = !categoryFilter || rb.category === categoryFilter;
      const matchesStatus = !statusFilter || rb.status === statusFilter;
      return matchesSearch && matchesCategory && matchesStatus;
    });
  }, [searchQuery, categoryFilter, statusFilter]);

  // Stats
  const stats = {
    total: mockRunbooks.length,
    published: mockRunbooks.filter((r) => r.status === 'published').length,
    draft: mockRunbooks.filter((r) => r.status === 'draft').length,
    executions: mockRunbooks.reduce((acc, r) => acc + (r.executionCount || 0), 0),
  };

  // Handle execute
  const handleExecute = async () => {
    if (!selectedRunbook) return;
    setIsExecuting(true);
    // Simulate execution
    await new Promise((resolve) => setTimeout(resolve, 2000));
    setIsExecuting(false);
    setShowExecuteConfirm(false);
    // TODO: Show success notification
  };

  return (
    <div className="min-h-screen bg-stone-50 dark:bg-stone-900">
      <Header
        title="Runbooks"
        subtitle={`${filteredRunbooks.length} runbooks`}
        actions={
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="w-4 h-4" />
            Create Runbook
          </Button>
        }
      />

      <div className="p-6 lg:p-8 space-y-6">
        {/* Stats cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Runbooks"
            value={stats.total}
            icon={BookOpen}
            color="bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-400"
          />
          <StatCard
            label="Published"
            value={stats.published}
            icon={CheckCircle}
            color="bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400"
          />
          <StatCard
            label="Drafts"
            value={stats.draft}
            icon={Edit}
            color="bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400"
          />
          <StatCard
            label="Total Executions"
            value={stats.executions}
            icon={Zap}
            color="bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
          />
        </div>

        {/* Search and filters */}
        <Card>
          <CardContent className="py-4">
            <div className="flex flex-col gap-4">
              <div className="flex flex-col sm:flex-row gap-4">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
                  <Input
                    placeholder="Search runbooks by name, description, or tags..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <Button
                  variant={showFilters ? 'secondary' : 'outline'}
                  onClick={() => setShowFilters(!showFilters)}
                  className="gap-2"
                >
                  <Filter className="w-4 h-4" />
                  Filters
                  {(categoryFilter || statusFilter) && (
                    <span className="w-5 h-5 rounded-full bg-forest text-white text-xs flex items-center justify-center">
                      {[categoryFilter, statusFilter].filter(Boolean).length}
                    </span>
                  )}
                </Button>
              </div>

              {showFilters && (
                <div className="flex flex-col sm:flex-row gap-4 pt-4 border-t border-stone-200 dark:border-stone-700 animate-in slide-in-from-top-2 duration-200">
                  <Select
                    options={categoryOptions}
                    value={categoryFilter}
                    onChange={setCategoryFilter}
                    className="w-full sm:w-48"
                  />
                  <Select
                    options={statusOptions}
                    value={statusFilter}
                    onChange={setStatusFilter}
                    className="w-full sm:w-48"
                  />
                  {(categoryFilter || statusFilter) && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setCategoryFilter('');
                        setStatusFilter('');
                      }}
                    >
                      Clear filters
                    </Button>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Runbook list */}
        {filteredRunbooks.length === 0 ? (
          <EmptyState
            icon={<BookOpen className="w-6 h-6 text-stone-400" />}
            title="No runbooks found"
            description="No runbooks match your search criteria. Try adjusting your filters or create a new runbook."
          />
        ) : (
          <div className="space-y-4">
            {/* Table header */}
            <div className="hidden md:grid md:grid-cols-12 gap-4 px-6 py-3 text-xs font-semibold text-stone-500 dark:text-stone-400 uppercase tracking-wider">
              <div className="col-span-5">Name</div>
              <div className="col-span-2">Category</div>
              <div className="col-span-2">Status</div>
              <div className="col-span-2">Last Run</div>
              <div className="col-span-1">Actions</div>
            </div>

            {/* Runbook cards */}
            {filteredRunbooks.map((runbook) => (
              <RunbookCard
                key={runbook.id}
                runbook={runbook}
                onView={() => setSelectedRunbook(runbook)}
                onExecute={() => {
                  setSelectedRunbook(runbook);
                  setShowExecuteConfirm(true);
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Runbook Detail Modal */}
      {selectedRunbook && !showExecuteConfirm && (
        <RunbookDetailModal
          runbook={selectedRunbook}
          isOpen={!!selectedRunbook && !showExecuteConfirm}
          onClose={() => setSelectedRunbook(null)}
          onExecute={(dryRun) => {
            setIsDryRun(dryRun);
            setShowExecuteConfirm(true);
          }}
          executionHistory={mockExecutionHistory.filter(
            (e) => e.runbookId === selectedRunbook.id
          )}
        />
      )}

      {/* Execute Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showExecuteConfirm}
        onClose={() => {
          setShowExecuteConfirm(false);
          setIsDryRun(false);
        }}
        onConfirm={handleExecute}
        title={isDryRun ? 'Execute Dry Run' : 'Execute Runbook'}
        description={
          isDryRun
            ? `This will simulate executing "${selectedRunbook?.name}" without making any changes. Continue?`
            : `This will execute "${selectedRunbook?.name}" in production. Are you sure you want to proceed?`
        }
        confirmText={isDryRun ? 'Run Dry Run' : 'Execute'}
        variant={isDryRun ? 'default' : 'danger'}
        loading={isExecuting}
      />

      {/* Create Runbook Modal */}
      <CreateRunbookModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
      />
    </div>
  );
}

// ============================================================================
// Stat Card Component
// ============================================================================
function StatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: number;
  icon: typeof BookOpen;
  color: string;
}) {
  return (
    <Card>
      <CardContent className="py-4">
        <div className="flex items-center gap-3">
          <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', color)}>
            <Icon className="w-5 h-5" />
          </div>
          <div>
            <p className="text-2xl font-bold text-stone-900 dark:text-white">{value}</p>
            <p className="text-xs text-stone-500 dark:text-stone-400 uppercase tracking-wider">
              {label}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Runbook Card Component
// ============================================================================
function RunbookCard({
  runbook,
  onView,
  onExecute,
}: {
  runbook: Runbook;
  onView: () => void;
  onExecute: () => void;
}) {
  return (
    <Card hover className="group">
      <CardContent className="py-4">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
          {/* Name & Description */}
          <div className="col-span-1 md:col-span-5">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-forest/10 dark:bg-forest/20 flex items-center justify-center flex-shrink-0">
                <BookOpen className="w-5 h-5 text-forest dark:text-forest-light" />
              </div>
              <div className="min-w-0">
                <h4 className="font-semibold text-stone-900 dark:text-white truncate">
                  {runbook.name}
                </h4>
                <p className="text-sm text-stone-500 dark:text-stone-400 line-clamp-1">
                  {runbook.description}
                </p>
                <div className="flex flex-wrap gap-1 mt-2">
                  {runbook.tags.slice(0, 3).map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-400"
                    >
                      <Tag className="w-3 h-3 mr-1" />
                      {tag}
                    </span>
                  ))}
                  {runbook.tags.length > 3 && (
                    <span className="text-xs text-stone-400">
                      +{runbook.tags.length - 3}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Category */}
          <div className="col-span-1 md:col-span-2">
            <span className="md:hidden text-xs text-stone-500 dark:text-stone-400 mr-2">
              Category:
            </span>
            <Badge className="bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300">
              {runbook.category || 'Uncategorized'}
            </Badge>
          </div>

          {/* Status */}
          <div className="col-span-1 md:col-span-2">
            <span className="md:hidden text-xs text-stone-500 dark:text-stone-400 mr-2">
              Status:
            </span>
            <StatusBadge status={runbook.status} />
          </div>

          {/* Last Run */}
          <div className="col-span-1 md:col-span-2">
            <span className="md:hidden text-xs text-stone-500 dark:text-stone-400 mr-2">
              Last Run:
            </span>
            {runbook.lastExecutedAt ? (
              <span className="flex items-center gap-1 text-sm text-stone-600 dark:text-stone-400">
                <Clock className="w-3 h-3" />
                {formatRelativeTime(runbook.lastExecutedAt)}
              </span>
            ) : (
              <span className="text-sm text-stone-400">Never</span>
            )}
          </div>

          {/* Actions */}
          <div className="col-span-1 flex gap-2 justify-end">
            <Button
              variant="ghost"
              size="sm"
              onClick={onView}
              className="opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <Eye className="w-4 h-4" />
            </Button>
            <Button
              size="sm"
              onClick={onExecute}
              disabled={runbook.status === 'draft'}
              className="gap-1"
            >
              <Play className="w-4 h-4" />
              <span className="hidden sm:inline">Run</span>
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Runbook Detail Modal
// ============================================================================
function RunbookDetailModal({
  runbook,
  isOpen,
  onClose,
  onExecute,
  executionHistory,
}: {
  runbook: Runbook;
  isOpen: boolean;
  onClose: () => void;
  onExecute: (dryRun: boolean) => void;
  executionHistory: ExecutionHistoryItem[];
}) {
  const [activeTab, setActiveTab] = useState<'details' | 'history'>('details');

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={runbook.name} size="xl">
      <div className="space-y-6">
        {/* Header info */}
        <div className="flex flex-wrap gap-2">
          <StatusBadge status={runbook.status} />
          {runbook.category && (
            <Badge className="bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300">
              {runbook.category}
            </Badge>
          )}
          <RiskBadge risk={(runbook as unknown as { riskLevel?: RiskLevel }).riskLevel || 'low'} />
        </div>

        <p className="text-stone-600 dark:text-stone-300">{runbook.description}</p>

        {/* Meta info */}
        <div className="flex flex-wrap gap-6 text-sm text-stone-500 dark:text-stone-400">
          <span className="flex items-center gap-1">
            <User className="w-4 h-4" />
            {runbook.author}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-4 h-4" />
            Updated {formatRelativeTime(runbook.updatedAt)}
          </span>
          <span className="flex items-center gap-1">
            <Zap className="w-4 h-4" />
            {runbook.executionCount || 0} executions
          </span>
        </div>

        {/* Tags */}
        <div className="flex flex-wrap gap-2">
          {runbook.tags.map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-400"
            >
              <Tag className="w-3 h-3 mr-1" />
              {tag}
            </span>
          ))}
        </div>

        {/* Tab navigation */}
        <div className="border-b border-stone-200 dark:border-stone-700">
          <div className="flex gap-4">
            <button
              onClick={() => setActiveTab('details')}
              className={cn(
                'pb-3 text-sm font-medium border-b-2 transition-colors',
                activeTab === 'details'
                  ? 'border-forest text-forest dark:text-forest-light'
                  : 'border-transparent text-stone-500 hover:text-stone-700 dark:hover:text-stone-300'
              )}
            >
              <FileText className="w-4 h-4 inline mr-2" />
              Steps ({runbook.steps.length})
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={cn(
                'pb-3 text-sm font-medium border-b-2 transition-colors',
                activeTab === 'history'
                  ? 'border-forest text-forest dark:text-forest-light'
                  : 'border-transparent text-stone-500 hover:text-stone-700 dark:hover:text-stone-300'
              )}
            >
              <History className="w-4 h-4 inline mr-2" />
              Execution History
            </button>
          </div>
        </div>

        {/* Tab content */}
        {activeTab === 'details' ? (
          <div className="space-y-4">
            {/* Steps */}
            <div className="space-y-3">
              {runbook.steps.map((step, index) => (
                <div
                  key={step.id}
                  className="flex gap-4 p-4 rounded-lg bg-stone-50 dark:bg-stone-800/50 border border-stone-200 dark:border-stone-700"
                >
                  <div className="w-8 h-8 rounded-full bg-forest text-white flex items-center justify-center flex-shrink-0 font-semibold text-sm">
                    {index + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h5 className="font-semibold text-stone-900 dark:text-white">
                        {step.title || step.name}
                      </h5>
                      {step.type && (
                        <Badge
                          className={cn(
                            'text-xs',
                            step.type === 'automated'
                              ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                              : step.type === 'approval'
                              ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
                              : 'bg-stone-100 text-stone-600 dark:bg-stone-700 dark:text-stone-300'
                          )}
                        >
                          {step.type}
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-stone-600 dark:text-stone-400">
                      {step.description}
                    </p>
                    {step.command && (
                      <div className="mt-2 p-2 rounded bg-stone-900 dark:bg-stone-950 font-mono text-xs text-green-400 overflow-x-auto">
                        <Terminal className="w-3 h-3 inline mr-2" />
                        {step.command}
                      </div>
                    )}
                    {step.timeout && (
                      <p className="text-xs text-stone-400 mt-2">
                        Timeout: {step.timeout}s
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Parameters placeholder */}
            {/* {Object.keys(runbook.parameters || {}).length > 0 && (
              <div>
                <h5 className="font-semibold text-stone-900 dark:text-white mb-3">
                  Parameters
                </h5>
                ... parameter inputs would go here
              </div>
            )} */}
          </div>
        ) : (
          <div className="space-y-3">
            {executionHistory.length === 0 ? (
              <div className="text-center py-8 text-stone-500">
                <History className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>No execution history</p>
              </div>
            ) : (
              executionHistory.map((execution) => (
                <div
                  key={execution.id}
                  className="flex items-center justify-between p-4 rounded-lg bg-stone-50 dark:bg-stone-800/50 border border-stone-200 dark:border-stone-700"
                >
                  <div className="flex items-center gap-4">
                    <ExecutionStatusBadge status={execution.status} />
                    <div>
                      <p className="text-sm font-medium text-stone-900 dark:text-white">
                        {execution.dryRun ? 'Dry Run' : 'Execution'}
                      </p>
                      <p className="text-xs text-stone-500">
                        Triggered by {execution.triggeredBy}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-stone-600 dark:text-stone-400">
                      {formatRelativeTime(execution.startedAt)}
                    </p>
                    {execution.completedAt && (
                      <p className="text-xs text-stone-400">
                        Duration:{' '}
                        {Math.round(
                          (new Date(execution.completedAt).getTime() -
                            new Date(execution.startedAt).getTime()) /
                            1000
                        )}
                        s
                      </p>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex justify-end gap-3 pt-4 border-t border-stone-200 dark:border-stone-700">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button
            variant="outline"
            onClick={() => onExecute(true)}
            disabled={runbook.status === 'draft'}
            className="gap-2"
          >
            <AlertTriangle className="w-4 h-4" />
            Dry Run
          </Button>
          <Button
            onClick={() => onExecute(false)}
            disabled={runbook.status === 'draft'}
            className="gap-2"
          >
            <Play className="w-4 h-4" />
            Execute
          </Button>
        </div>
      </div>
    </Modal>
  );
}

// ============================================================================
// Create Runbook Modal
// ============================================================================
function CreateRunbookModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('');
  const [tags, setTags] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  const handleCreate = async () => {
    setIsCreating(true);
    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1500));
    setIsCreating(false);
    onClose();
    // Reset form
    setName('');
    setDescription('');
    setCategory('');
    setTags('');
  };

  const isValid = name.trim().length > 0;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create New Runbook"
      description="Define a new runbook for your team. You can add steps after creation."
      size="lg"
    >
      <div className="space-y-6">
        {/* Name */}
        <div>
          <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
            Name <span className="text-red-500">*</span>
          </label>
          <Input
            placeholder="e.g., Database Failover Procedure"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
            Description
          </label>
          <textarea
            placeholder="Describe what this runbook does and when to use it..."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full px-4 py-2 rounded-lg border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-800 text-stone-900 dark:text-white placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-forest dark:focus:ring-forest-light resize-none"
          />
        </div>

        {/* Category */}
        <div>
          <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
            Category
          </label>
          <Select
            options={categoryOptions}
            value={category}
            onChange={setCategory}
          />
        </div>

        {/* Tags */}
        <div>
          <label className="block text-sm font-medium text-stone-700 dark:text-stone-300 mb-2">
            Tags
          </label>
          <Input
            placeholder="Comma-separated tags (e.g., production, critical, database)"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
          />
          <p className="text-xs text-stone-500 mt-1">
            Separate multiple tags with commas
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex justify-end gap-3 pt-4 border-t border-stone-200 dark:border-stone-700">
          <Button variant="outline" onClick={onClose} disabled={isCreating}>
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={!isValid || isCreating} loading={isCreating}>
            <Plus className="w-4 h-4" />
            Create Runbook
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default RunbooksPage;
