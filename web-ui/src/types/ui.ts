/**
 * UI Type Aliases for AutoSRE V2
 * 
 * Aliases and UI-specific types used by components.
 */

import type { Alert, AlertSeverity, AlertStatus } from './alert';
import type { Investigation, InvestigationStatus, InvestigationPriority } from './investigation';
import type { Runbook, RunbookStatus } from './runbook';
import type { Message } from './chat';

// UI Aliases - for components that use different naming
export type AlertUI = Alert;
export type InvestigationUI = Investigation;
export type RunbookUI = Runbook;
export type ChatMessage = Message;

// Metric types for dashboard
export interface MetricDataPoint {
  timestamp: string;
  value: number;
  label?: string;
}

export interface MetricSeries {
  id: string;
  name: string;
  data: MetricDataPoint[];
  color?: string;
  unit?: string;
  type?: 'line' | 'bar' | 'area';
}

export interface DashboardMetrics {
  alertsTotal: number;
  alertsCritical: number;
  alertsHigh: number;
  alertsWarning: number;
  alertsInfo: number;
  investigationsActive: number;
  investigationsCompleted: number;
  investigationsPending: number;
  runbooksExecuted: number;
  runbooksSuccess: number;
  runbooksFailed: number;
  avgResolutionTime: number;
  mttr: number;
  mtta: number;
  systemHealth: number;
  uptimePercentage: number;
  series: MetricSeries[];
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'critical';
  score: number;
  services: Array<{
    name: string;
    status: 'healthy' | 'degraded' | 'unhealthy';
    latency?: number;
    errorRate?: number;
    lastChecked: string;
  }>;
  lastUpdated: string;
}

// Evidence types for investigation panels
export interface Evidence {
  id: string;
  type: 'metric' | 'log' | 'trace' | 'event' | 'config';
  source: string;
  timestamp: string;
  title: string;
  content: string;
  data?: MetricDataPoint[] | Record<string, unknown>;
  relevanceScore?: number;
  metadata?: Record<string, unknown>;
}

// Integration types for settings/connectors
export interface Integration {
  id: string;
  name: string;
  type: 'alertmanager' | 'prometheus' | 'grafana' | 'pagerduty' | 'slack' | 'jira' | 'github' | 'custom';
  status: 'connected' | 'disconnected' | 'error';
  config: Record<string, unknown>;
  lastSyncAt?: string;
  errorMessage?: string;
  createdAt: string;
  updatedAt: string;
}

// Timeline entry for investigation (used by Timeline component)
export interface TimelineEntry {
  id: string;
  type: 'alert' | 'observation' | 'hypothesis' | 'finding' | 'action' | 'status_change' | 'message';
  timestamp: string;
  title: string;
  content?: string;
  status?: string;
  metadata?: Record<string, unknown>;
}
