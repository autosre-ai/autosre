// API client for OpenSRE backend
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class APIError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'APIError';
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}/api${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  
  if (!res.ok) {
    const text = await res.text();
    throw new APIError(res.status, text || `HTTP ${res.status}`);
  }
  
  return res.json();
}

export const api = {
  // System
  getStatus: () => request<SystemStatus>('/status'),
  
  // Investigations (Incidents)
  getInvestigations: () => request<Investigation[]>('/investigations'),
  getInvestigation: (id: string) => request<Investigation>(`/investigations/${id}`),
  createInvestigation: (data: { issue: string; namespace: string }) =>
    request<Investigation>('/investigate', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  // Actions
  approveAction: (investigationId: string, actionId: string) =>
    request('/actions/approve', {
      method: 'POST',
      body: JSON.stringify({ investigation_id: investigationId, action_id: actionId }),
    }),
  rejectAction: (investigationId: string, actionId: string, reason: string) =>
    request('/actions/reject', {
      method: 'POST',
      body: JSON.stringify({ investigation_id: investigationId, action_id: actionId, reason }),
    }),
  
  // Agents
  getAgents: () => request<Agent[]>('/agents'),
  getAgent: (id: string) => request<Agent>(`/agents/${id}`),
  deployAgent: (id: string) =>
    request(`/agents/${id}/deploy`, { method: 'POST' }),
  stopAgent: (id: string) =>
    request(`/agents/${id}/stop`, { method: 'POST' }),
  
  // Skills
  getSkills: () => request<Skill[]>('/skills'),
  getSkill: (id: string) => request<Skill>(`/skills/${id}`),
  
  // Runbooks
  getRunbooks: () => request<Runbook[]>('/runbooks'),
  getRunbook: (id: string) => request<Runbook>(`/runbooks/${id}`),
  executeRunbook: (id: string, params?: Record<string, unknown>) =>
    request(`/runbooks/${id}/execute`, {
      method: 'POST',
      body: JSON.stringify(params || {}),
    }),
  
  // Metrics
  getMetrics: () => request<Metrics>('/metrics'),
};

// Types
export interface SystemStatus {
  version: string;
  uptime: number;
  integrations: {
    prometheus: { status: string; details?: string };
    kubernetes: { status: string; details?: string };
    llm: { status: string; details?: string };
  };
}

export interface Observation {
  source: string;
  type: string;
  summary: string;
  severity: 'info' | 'warning' | 'critical';
  timestamp: string;
  raw_data?: unknown;
}

export interface Action {
  id: string;
  description: string;
  command: string;
  risk: 'low' | 'medium' | 'high';
  status: 'pending' | 'approved' | 'rejected' | 'executing' | 'completed' | 'failed';
  requires_approval: boolean;
  output?: string;
  error?: string;
  executed_at?: string;
}

export interface Investigation {
  id: string;
  issue: string;
  namespace: string;
  status: 'running' | 'completed' | 'failed' | 'waiting_approval';
  started_at: string;
  completed_at?: string;
  observations: Observation[];
  root_cause?: string;
  confidence: number;
  actions: Action[];
  similar_incidents: string[];
  severity?: 'low' | 'medium' | 'high' | 'critical';
}

export interface Agent {
  id: string;
  name: string;
  type: 'investigator' | 'executor' | 'observer' | 'coordinator';
  status: 'running' | 'stopped' | 'error' | 'initializing';
  description: string;
  skills: string[];
  config: Record<string, unknown>;
  metrics?: {
    investigations_handled: number;
    actions_executed: number;
    success_rate: number;
    avg_response_time: number;
  };
  logs?: LogEntry[];
  last_active?: string;
}

export interface LogEntry {
  timestamp: string;
  level: 'debug' | 'info' | 'warn' | 'error';
  message: string;
  metadata?: Record<string, unknown>;
}

export interface Skill {
  id: string;
  name: string;
  category: 'diagnostic' | 'remediation' | 'monitoring' | 'communication';
  description: string;
  parameters: SkillParameter[];
  examples: string[];
  documentation: string;
}

export interface SkillParameter {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  required: boolean;
  description: string;
  default?: unknown;
}

export interface Runbook {
  id: string;
  name: string;
  description: string;
  category: string;
  steps: RunbookStep[];
  triggers: string[];
  last_executed?: string;
  execution_count: number;
  avg_duration?: number;
}

export interface RunbookStep {
  id: string;
  name: string;
  type: 'manual' | 'automated' | 'conditional';
  description: string;
  action?: string;
}

export interface Metrics {
  incidents: {
    total: number;
    active: number;
    resolved_today: number;
    mttr_minutes: number;
  };
  agents: {
    total: number;
    active: number;
  };
  actions: {
    pending_approval: number;
    executed_today: number;
    success_rate: number;
  };
  system: {
    cpu_usage: number;
    memory_usage: number;
    api_latency_ms: number;
  };
}
