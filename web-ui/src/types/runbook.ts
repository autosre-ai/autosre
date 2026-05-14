/**
 * Runbook Types for AutoSRE V2
 */

import type { AlertSeverity } from './alert';

export enum RunbookStepType {
  manual = 'manual',
  automated = 'automated',
  conditional = 'conditional',
  approval = 'approval',
  notification = 'notification',
  parallel = 'parallel',
}

export enum RunbookStepStatus {
  pending = 'pending',
  running = 'running',
  completed = 'completed',
  failed = 'failed',
  skipped = 'skipped',
  waiting_approval = 'waiting_approval',
  cancelled = 'cancelled',
}

export enum RunbookStatus {
  draft = 'draft',
  published = 'published',
  deprecated = 'deprecated',
  archived = 'archived',
}

export enum RunbookExecutionStatus {
  pending = 'pending',
  running = 'running',
  paused = 'paused',
  completed = 'completed',
  failed = 'failed',
  cancelled = 'cancelled',
  waiting_approval = 'waiting_approval',
}

export interface RunbookStepAction {
  type: 'command' | 'script' | 'api' | 'query' | 'webhook';
  target?: string;
  command?: string;
  script?: string;
  endpoint?: string;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  headers?: Record<string, string>;
  body?: string;
  query?: string;
  timeout?: number;
  retries?: number;
  retryDelay?: number;
}

export interface RunbookStepCondition {
  field: string;
  operator: 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'contains' | 'regex' | 'exists';
  value: unknown;
  then?: string;
  else?: string;
}

export interface RunbookStepInput {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'select' | 'multiselect' | 'text';
  label: string;
  description?: string;
  required: boolean;
  default?: unknown;
  options?: Array<{ label: string; value: unknown }>;
  validation?: {
    pattern?: string;
    min?: number;
    max?: number;
    minLength?: number;
    maxLength?: number;
  };
}

export interface RunbookStep {
  id: string;
  name: string;
  description: string;
  type: RunbookStepType;
  order: number;
  action?: RunbookStepAction;
  condition?: RunbookStepCondition;
  inputs?: RunbookStepInput[];
  outputs?: string[];
  timeout?: number;
  retries?: number;
  continueOnFailure?: boolean;
  approvers?: string[];
  parallelSteps?: string[];
  dependsOn?: string[];
  instructions?: string;
  warningMessage?: string;
  metadata?: Record<string, unknown>;
}

export interface RunbookVariable {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'object' | 'array';
  description?: string;
  required: boolean;
  default?: unknown;
  source?: 'input' | 'alert' | 'environment' | 'previous_step';
  sourceField?: string;
}

export interface RunbookTrigger {
  type: 'manual' | 'alert' | 'schedule' | 'webhook' | 'event';
  alertMatchers?: Array<{
    label: string;
    operator: 'eq' | 'ne' | 'regex';
    value: string;
  }>;
  schedule?: string;
  webhookToken?: string;
  eventType?: string;
}

export interface Runbook {
  id: string;
  name: string;
  description: string;
  status: RunbookStatus;
  version: number;
  steps: RunbookStep[];
  variables: RunbookVariable[];
  triggers: RunbookTrigger[];
  targetServices?: string[];
  targetAlertSeverities?: AlertSeverity[];
  estimatedDuration?: number;
  tags: string[];
  category?: string;
  owner: string;
  reviewers?: string[];
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  publishedAt?: string;
  lastExecutedAt?: string;
  executionCount: number;
  successRate?: number;
  avgExecutionTime?: number;
  metadata?: Record<string, unknown>;
}

export interface RunbookStepExecution {
  stepId: string;
  status: RunbookStepStatus;
  startedAt?: string;
  completedAt?: string;
  duration?: number;
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  error?: string;
  logs?: string[];
  approvedBy?: string;
  approvedAt?: string;
  skippedReason?: string;
  retryCount?: number;
}

export interface RunbookExecution {
  id: string;
  runbookId: string;
  runbookVersion: number;
  runbookName: string;
  status: RunbookExecutionStatus;
  trigger: {
    type: RunbookTrigger['type'];
    alertId?: string;
    triggeredBy?: string;
    source?: string;
  };
  variables: Record<string, unknown>;
  steps: RunbookStepExecution[];
  currentStepId?: string;
  progress: number;
  startedAt: string;
  completedAt?: string;
  duration?: number;
  error?: string;
  logs: Array<{
    timestamp: string;
    level: 'debug' | 'info' | 'warn' | 'error';
    message: string;
    stepId?: string;
  }>;
  createdBy: string;
  investigationId?: string;
  metadata?: Record<string, unknown>;
}

export interface RunbookFilter {
  status?: RunbookStatus[];
  category?: string[];
  tags?: string[];
  owner?: string[];
  targetServices?: string[];
  search?: string;
  createdAfter?: string;
  createdBefore?: string;
  limit?: number;
  offset?: number;
  sortBy?: 'name' | 'createdAt' | 'updatedAt' | 'executionCount' | 'successRate';
  sortOrder?: 'asc' | 'desc';
}

export interface RunbookExecutionFilter {
  runbookId?: string;
  status?: RunbookExecutionStatus[];
  triggeredBy?: string[];
  triggerType?: RunbookTrigger['type'][];
  startedAfter?: string;
  startedBefore?: string;
  alertId?: string;
  investigationId?: string;
  limit?: number;
  offset?: number;
  sortBy?: 'startedAt' | 'completedAt' | 'duration' | 'status';
  sortOrder?: 'asc' | 'desc';
}

export interface CreateRunbookRequest {
  name: string;
  description: string;
  steps: Omit<RunbookStep, 'id'>[];
  variables?: RunbookVariable[];
  triggers?: RunbookTrigger[];
  targetServices?: string[];
  targetAlertSeverities?: AlertSeverity[];
  estimatedDuration?: number;
  tags?: string[];
  category?: string;
}

export interface UpdateRunbookRequest {
  name?: string;
  description?: string;
  status?: RunbookStatus;
  steps?: Omit<RunbookStep, 'id'>[];
  variables?: RunbookVariable[];
  triggers?: RunbookTrigger[];
  targetServices?: string[];
  targetAlertSeverities?: AlertSeverity[];
  estimatedDuration?: number;
  tags?: string[];
  category?: string;
  owner?: string;
  reviewers?: string[];
}

export interface ExecuteRunbookRequest {
  runbookId: string;
  variables?: Record<string, unknown>;
  alertId?: string;
  investigationId?: string;
  dryRun?: boolean;
  startFromStep?: string;
}

export interface RunbookSummary {
  total: number;
  byStatus: Record<RunbookStatus, number>;
  byCategory: Record<string, number>;
  topUsed: Array<{ runbookId: string; name: string; count: number }>;
  recentExecutions: number;
  avgSuccessRate: number;
}
