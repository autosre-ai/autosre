// AutoSRE Types

export interface Investigation {
  id: string;
  title: string;
  description: string;
  status: "pending" | "investigating" | "resolved" | "escalated";
  severity: "critical" | "high" | "medium" | "low";
  createdAt: string;
  updatedAt: string;
  hypotheses: Hypothesis[];
  findings: Finding[];
  timeline: TimelineEvent[];
}

export interface Hypothesis {
  id: string;
  content: string;
  confidence: number; // 0-1
  status: "investigating" | "confirmed" | "rejected" | "needs_more_data";
  evidence: Evidence[];
  createdAt: string;
}

export interface Evidence {
  id: string;
  type: "metric" | "log" | "trace" | "event" | "test_result";
  source: string;
  content: string;
  supports: boolean; // supports or contradicts hypothesis
  timestamp: string;
}

export interface Finding {
  id: string;
  type: "root_cause" | "contributing_factor" | "observation" | "recommendation";
  content: string;
  confidence: number;
  relatedHypotheses: string[];
}

export interface TimelineEvent {
  id: string;
  timestamp: string;
  type: "skill_start" | "skill_end" | "hypothesis" | "finding" | "message" | "error";
  content: string;
  metadata?: Record<string, unknown>;
}

export interface Skill {
  id: string;
  name: string;
  description: string;
  category: "observability" | "kubernetes" | "database" | "network" | "custom";
  enabled: boolean;
  parameters?: SkillParameter[];
}

export interface SkillParameter {
  name: string;
  type: "string" | "number" | "boolean" | "select";
  required: boolean;
  default?: string | number | boolean;
  options?: string[]; // for select type
}

export interface SkillExecution {
  id: string;
  skillId: string;
  skillName: string;
  status: "running" | "completed" | "failed";
  startedAt: string;
  completedAt?: string;
  input: Record<string, unknown>;
  output?: unknown;
  error?: string;
  duration?: number;
}

export interface Episode {
  id: string;
  investigationId: string;
  summary: string;
  outcome: "resolved" | "escalated" | "partial";
  rootCause?: string;
  strategy: string;
  embedding?: number[];
  createdAt: string;
  metadata: {
    duration: number;
    skillsUsed: string[];
    hypothesesCount: number;
  };
}

export interface Memory {
  episodes: Episode[];
  strategies: Strategy[];
  stats: MemoryStats;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  pattern: string;
  successRate: number;
  usageCount: number;
  steps: string[];
}

export interface MemoryStats {
  totalEpisodes: number;
  resolvedCount: number;
  averageDuration: number;
  topSkills: { skill: string; count: number }[];
  successRate: number;
}

export interface TeamConfig {
  agents: AgentConfig[];
  coordinator: CoordinatorConfig;
}

export interface AgentConfig {
  id: string;
  name: string;
  role: string;
  skills: string[];
  model: string;
  enabled: boolean;
}

export interface CoordinatorConfig {
  maxParallelAgents: number;
  escalationThreshold: number;
  timeoutMinutes: number;
}

export interface LLMConfig {
  provider: "anthropic" | "openai" | "ollama" | "custom";
  model: string;
  apiKey?: string;
  baseUrl?: string;
  temperature: number;
  maxTokens: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system" | "skill";
  content: string;
  timestamp: string;
  metadata?: {
    skillExecution?: SkillExecution;
    hypothesis?: Hypothesis;
    finding?: Finding;
  };
}

// SSE Event types
export interface SSEEvent {
  type: "message" | "skill_start" | "skill_end" | "hypothesis" | "finding" | "error" | "done";
  data: unknown;
}

export interface InvestigationRequest {
  description: string;
  context?: Record<string, unknown>;
  urgency?: "critical" | "high" | "medium" | "low";
}

export interface InvestigationListItem {
  id: string;
  title: string;
  status: Investigation["status"];
  severity: Investigation["severity"];
  createdAt: string;
  updatedAt: string;
  findingsCount: number;
}
