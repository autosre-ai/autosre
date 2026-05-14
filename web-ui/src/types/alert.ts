/**
 * Alert Types for AutoSRE V2
 */

export enum AlertSeverity {
  critical = 'critical',
  high = 'high',
  warning = 'warning',
  info = 'info',
}

export enum AlertStatus {
  firing = 'firing',
  pending = 'pending',
  resolved = 'resolved',
}

export interface AlertLabels {
  alertname: string;
  severity: AlertSeverity;
  service?: string;
  namespace?: string;
  pod?: string;
  node?: string;
  instance?: string;
  job?: string;
  cluster?: string;
  region?: string;
  environment?: string;
  team?: string;
  [key: string]: string | AlertSeverity | undefined;
}

export interface AlertAnnotations {
  summary?: string;
  description?: string;
  runbook_url?: string;
  dashboard_url?: string;
  [key: string]: string | undefined;
}

export interface Alert {
  id: string;
  name: string;
  severity: AlertSeverity;
  status: AlertStatus;
  labels: AlertLabels;
  annotations: AlertAnnotations;
  startsAt: string;
  endsAt?: string;
  updatedAt: string;
  generatorURL?: string;
  fingerprint: string;
  silenced: boolean;
  inhibited: boolean;
  acknowledgedBy?: string;
  acknowledgedAt?: string;
}

export interface AlertFilter {
  severity?: AlertSeverity[];
  status?: AlertStatus[];
  labels?: Partial<AlertLabels>;
  service?: string[];
  namespace?: string[];
  cluster?: string[];
  team?: string[];
  search?: string;
  silenced?: boolean;
  inhibited?: boolean;
  startsAfter?: string;
  startsBefore?: string;
  limit?: number;
  offset?: number;
}

export interface AlertGroup {
  labels: Partial<AlertLabels>;
  alerts: Alert[];
  receiver: string;
  groupKey: string;
}

export interface AlertSummary {
  total: number;
  bySeverity: Record<AlertSeverity, number>;
  byStatus: Record<AlertStatus, number>;
  topServices: Array<{ service: string; count: number }>;
}

export interface AlertAcknowledgement {
  alertId: string;
  acknowledgedBy: string;
  acknowledgedAt: string;
  comment?: string;
}

export interface SilenceRequest {
  matchers: Array<{
    name: string;
    value: string;
    isRegex: boolean;
    isEqual: boolean;
  }>;
  startsAt: string;
  endsAt: string;
  createdBy: string;
  comment: string;
}

export interface Silence {
  id: string;
  matchers: SilenceRequest['matchers'];
  startsAt: string;
  endsAt: string;
  createdBy: string;
  comment: string;
  status: {
    state: 'active' | 'pending' | 'expired';
  };
  updatedAt: string;
}
