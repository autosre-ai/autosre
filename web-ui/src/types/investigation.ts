/**
 * Investigation Types for AutoSRE V2
 */

import type { Alert, AlertSeverity } from './alert';

export enum InvestigationStatus {
  pending = 'pending',
  running = 'running',
  completed = 'completed',
  failed = 'failed',
}

export enum InvestigationPriority {
  critical = 'critical',
  high = 'high',
  medium = 'medium',
  low = 'low',
}

export enum ObservationType {
  metric = 'metric',
  log = 'log',
  trace = 'trace',
  event = 'event',
  config = 'config',
  dependency = 'dependency',
}

export enum HypothesisStatus {
  proposed = 'proposed',
  investigating = 'investigating',
  confirmed = 'confirmed',
  rejected = 'rejected',
}

export enum FindingSeverity {
  critical = 'critical',
  high = 'high',
  medium = 'medium',
  low = 'low',
  info = 'info',
}

export enum FindingType {
  root_cause = 'root_cause',
  contributing_factor = 'contributing_factor',
  symptom = 'symptom',
  recommendation = 'recommendation',
}

export interface Observation {
  id: string;
  investigationId: string;
  type: ObservationType;
  source: string;
  timestamp: string;
  data: Record<string, unknown>;
  summary: string;
  relevanceScore: number;
  metadata?: {
    query?: string;
    timeRange?: { start: string; end: string };
    service?: string;
    [key: string]: unknown;
  };
}

export interface Hypothesis {
  id: string;
  investigationId: string;
  status: HypothesisStatus;
  title: string;
  description: string;
  confidence: number;
  supportingObservations: string[];
  contradictingObservations: string[];
  testPlan?: string;
  testResults?: string;
  createdAt: string;
  updatedAt: string;
}

export interface Finding {
  id: string;
  investigationId: string;
  type: FindingType;
  severity: FindingSeverity;
  title: string;
  description: string;
  evidence: string[];
  affectedComponents: string[];
  recommendations?: string[];
  relatedHypotheses: string[];
  confidence: number;
  createdAt: string;
}

export interface InvestigationStep {
  id: string;
  name: string;
  description: string;
  status: 'pending' | 'running' | 'completed' | 'skipped' | 'failed';
  startedAt?: string;
  completedAt?: string;
  duration?: number;
  output?: string;
  error?: string;
}

export interface InvestigationTimeline {
  timestamp: string;
  event: string;
  type: 'alert' | 'observation' | 'hypothesis' | 'finding' | 'action' | 'status_change';
  details?: Record<string, unknown>;
}

export interface Investigation {
  id: string;
  title: string;
  description: string;
  status: InvestigationStatus;
  priority: InvestigationPriority;
  alerts: Alert[];
  alertIds: string[];
  observations: Observation[];
  hypotheses: Hypothesis[];
  findings: Finding[];
  steps: InvestigationStep[];
  timeline: InvestigationTimeline[];
  rootCause?: Finding;
  summary?: string;
  assignedTo?: string;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  startedAt?: string;
  completedAt?: string;
  duration?: number;
  tags: string[];
  relatedInvestigations?: string[];
  metadata?: Record<string, unknown>;
}

export interface InvestigationFilter {
  status?: InvestigationStatus[];
  priority?: InvestigationPriority[];
  alertSeverity?: AlertSeverity[];
  assignedTo?: string[];
  createdBy?: string[];
  tags?: string[];
  search?: string;
  createdAfter?: string;
  createdBefore?: string;
  completedAfter?: string;
  completedBefore?: string;
  limit?: number;
  offset?: number;
  sortBy?: 'createdAt' | 'updatedAt' | 'priority' | 'status';
  sortOrder?: 'asc' | 'desc';
}

export interface InvestigationSummary {
  total: number;
  byStatus: Record<InvestigationStatus, number>;
  byPriority: Record<InvestigationPriority, number>;
  avgDuration: number;
  recentlyCompleted: number;
  activeCount: number;
}

export interface CreateInvestigationRequest {
  title?: string;
  description?: string;
  alertIds: string[];
  priority?: InvestigationPriority;
  assignedTo?: string;
  tags?: string[];
  autoStart?: boolean;
}

export interface UpdateInvestigationRequest {
  title?: string;
  description?: string;
  status?: InvestigationStatus;
  priority?: InvestigationPriority;
  assignedTo?: string;
  summary?: string;
  tags?: string[];
  rootCauseId?: string;
}
