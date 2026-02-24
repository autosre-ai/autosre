"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Shield,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Search,
  Play,
  Pause,
  RefreshCw,
  Terminal,
  Activity,
  Server,
  Database,
  Cpu,
  MemoryStick,
  Zap,
  Eye,
  Brain,
  Wrench,
  ChevronRight,
  ChevronDown,
} from "lucide-react";

// Types
interface Observation {
  source: string;
  type: string;
  summary: string;
  severity: string;
}

interface Action {
  id: string;
  description: string;
  command: string;
  risk: "low" | "medium" | "high";
  status: string;
  requires_approval: boolean;
}

interface Investigation {
  id: string;
  issue: string;
  namespace: string;
  status: string;
  started_at: string;
  completed_at?: string;
  observations: Observation[];
  root_cause: string;
  confidence: number;
  actions: Action[];
  similar_incidents: string[];
}

interface SystemStatus {
  version: string;
  integrations: {
    prometheus: { status: string; details?: string };
    kubernetes: { status: string; details?: string };
    llm: { status: string; details?: string };
  };
}

// API helpers
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api${path}`, options);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// Components
function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    connected: "bg-green-500/20 text-green-400 border-green-500/50",
    healthy: "bg-green-500/20 text-green-400 border-green-500/50",
    running: "bg-blue-500/20 text-blue-400 border-blue-500/50",
    completed: "bg-green-500/20 text-green-400 border-green-500/50",
    error: "bg-red-500/20 text-red-400 border-red-500/50",
    failed: "bg-red-500/20 text-red-400 border-red-500/50",
    timeout: "bg-yellow-500/20 text-yellow-400 border-yellow-500/50",
    pending: "bg-yellow-500/20 text-yellow-400 border-yellow-500/50",
  };

  return (
    <span
      className={`px-2 py-1 text-xs font-medium rounded-full border ${
        styles[status] || "bg-gray-500/20 text-gray-400 border-gray-500/50"
      }`}
    >
      {status}
    </span>
  );
}

function RiskBadge({ risk }: { risk: string }) {
  const styles: Record<string, string> = {
    low: "bg-green-500/20 text-green-400",
    medium: "bg-yellow-500/20 text-yellow-400",
    high: "bg-red-500/20 text-red-400",
  };

  return (
    <span
      className={`px-2 py-0.5 text-xs font-medium rounded ${
        styles[risk] || "bg-gray-500/20 text-gray-400"
      }`}
    >
      {risk}
    </span>
  );
}

function SeverityIcon({ severity }: { severity: string }) {
  switch (severity) {
    case "critical":
      return <XCircle className="w-4 h-4 text-red-500" />;
    case "warning":
      return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
    default:
      return <CheckCircle className="w-4 h-4 text-blue-500" />;
  }
}

function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`bg-gray-900 border border-gray-800 rounded-lg ${className}`}
    >
      {children}
    </div>
  );
}

function IntegrationStatus({ status }: { status: SystemStatus | null }) {
  if (!status) {
    return (
      <div className="flex items-center gap-2 text-gray-400">
        <RefreshCw className="w-4 h-4 animate-spin" />
        <span>Loading...</span>
      </div>
    );
  }

  const integrations = [
    { name: "Prometheus", key: "prometheus", icon: Activity },
    { name: "Kubernetes", key: "kubernetes", icon: Server },
    { name: "LLM", key: "llm", icon: Brain },
  ] as const;

  return (
    <div className="flex items-center gap-4">
      {integrations.map(({ name, key, icon: Icon }) => {
        const int = status.integrations[key];
        const isConnected = int.status === "connected";
        return (
          <div
            key={key}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${
              isConnected ? "bg-green-500/10" : "bg-red-500/10"
            }`}
          >
            <Icon
              className={`w-4 h-4 ${
                isConnected ? "text-green-500" : "text-red-500"
              }`}
            />
            <span className="text-sm">{name}</span>
            <div
              className={`w-2 h-2 rounded-full ${
                isConnected ? "bg-green-500" : "bg-red-500"
              }`}
            />
          </div>
        );
      })}
    </div>
  );
}

function InvestigationCard({
  investigation,
  onSelect,
  isSelected,
}: {
  investigation: Investigation;
  onSelect: () => void;
  isSelected: boolean;
}) {
  return (
    <Card
      className={`p-4 cursor-pointer transition-all hover:border-gray-700 ${
        isSelected ? "border-blue-500 glow-blue" : ""
      }`}
    >
      <div onClick={onSelect}>
        <div className="flex items-start justify-between mb-2">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-blue-500" />
            <span className="font-medium truncate max-w-[200px]">
              {investigation.issue}
            </span>
          </div>
          <StatusBadge status={investigation.status} />
        </div>

        <div className="text-sm text-gray-400 mb-2">
          Namespace: {investigation.namespace}
        </div>

        {investigation.root_cause && (
          <div className="text-sm mt-2 p-2 bg-gray-800 rounded">
            <div className="flex items-center gap-2 mb-1">
              <Brain className="w-4 h-4 text-yellow-500" />
              <span className="text-yellow-500">
                Root Cause ({Math.round(investigation.confidence * 100)}%)
              </span>
            </div>
            <p className="text-gray-300 text-xs">{investigation.root_cause}</p>
          </div>
        )}

        <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
          <div className="flex items-center gap-1">
            <Eye className="w-3 h-3" />
            {investigation.observations?.length || 0} observations
          </div>
          <div className="flex items-center gap-1">
            <Wrench className="w-3 h-3" />
            {investigation.actions?.length || 0} actions
          </div>
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {new Date(investigation.started_at).toLocaleTimeString()}
          </div>
        </div>
      </div>
    </Card>
  );
}

function ObservationsList({ observations }: { observations: Observation[] }) {
  if (!observations?.length) {
    return (
      <div className="text-gray-500 text-center py-4">No observations yet</div>
    );
  }

  return (
    <div className="space-y-2">
      {observations.map((obs, i) => (
        <div
          key={i}
          className="flex items-start gap-3 p-3 bg-gray-800/50 rounded-lg"
        >
          <SeverityIcon severity={obs.severity} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-medium text-gray-400 uppercase">
                {obs.source}
              </span>
              <span className="text-xs text-gray-600">•</span>
              <span className="text-xs text-gray-500">{obs.type}</span>
            </div>
            <p className="text-sm text-gray-200">{obs.summary}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function ActionsList({
  actions,
  investigationId,
  onActionUpdate,
}: {
  actions: Action[];
  investigationId: string;
  onActionUpdate: () => void;
}) {
  const [expandedAction, setExpandedAction] = useState<string | null>(null);
  const [executing, setExecuting] = useState<string | null>(null);

  const handleApprove = async (actionId: string) => {
    setExecuting(actionId);
    try {
      await fetchApi("/actions/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          investigation_id: investigationId,
          action_id: actionId,
        }),
      });
      onActionUpdate();
    } catch (error) {
      console.error("Failed to approve action:", error);
    }
    setExecuting(null);
  };

  const handleReject = async (actionId: string) => {
    try {
      await fetchApi("/actions/reject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          investigation_id: investigationId,
          action_id: actionId,
          reason: "Rejected by user",
        }),
      });
      onActionUpdate();
    } catch (error) {
      console.error("Failed to reject action:", error);
    }
  };

  if (!actions?.length) {
    return (
      <div className="text-gray-500 text-center py-4">
        No actions suggested yet
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {actions.map((action) => (
        <div key={action.id} className="bg-gray-800/50 rounded-lg">
          <div
            className="flex items-center gap-3 p-3 cursor-pointer"
            onClick={() =>
              setExpandedAction(expandedAction === action.id ? null : action.id)
            }
          >
            {expandedAction === action.id ? (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400" />
            )}

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-200">
                  {action.description}
                </span>
                <RiskBadge risk={action.risk} />
                <StatusBadge status={action.status} />
              </div>
            </div>

            {action.status === "pending" && action.requires_approval && (
              <div className="flex items-center gap-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleApprove(action.id);
                  }}
                  disabled={executing === action.id}
                  className="px-3 py-1 text-xs bg-green-600 hover:bg-green-700 rounded-md disabled:opacity-50"
                >
                  {executing === action.id ? "..." : "Approve"}
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleReject(action.id);
                  }}
                  className="px-3 py-1 text-xs bg-red-600 hover:bg-red-700 rounded-md"
                >
                  Reject
                </button>
              </div>
            )}
          </div>

          {expandedAction === action.id && (
            <div className="px-3 pb-3 pt-0">
              <div className="bg-gray-900 rounded-md p-3 font-mono text-sm text-green-400">
                $ {action.command}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function InvestigationDetail({
  investigation,
  onUpdate,
}: {
  investigation: Investigation;
  onUpdate: () => void;
}) {
  const [activeTab, setActiveTab] = useState<
    "observations" | "analysis" | "actions"
  >("observations");

  return (
    <Card className="h-full flex flex-col">
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold">{investigation.issue}</h2>
          <StatusBadge status={investigation.status} />
        </div>
        <div className="text-sm text-gray-400">
          Started: {new Date(investigation.started_at).toLocaleString()}
        </div>
      </div>

      <div className="flex border-b border-gray-800">
        {(["observations", "analysis", "actions"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 px-4 py-3 text-sm font-medium capitalize transition-colors ${
              activeTab === tab
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto p-4">
        {activeTab === "observations" && (
          <ObservationsList observations={investigation.observations} />
        )}

        {activeTab === "analysis" && (
          <div className="space-y-4">
            {investigation.root_cause ? (
              <>
                <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <Brain className="w-5 h-5 text-yellow-500" />
                    <span className="font-medium text-yellow-500">
                      Root Cause Analysis
                    </span>
                    <span className="text-sm text-yellow-400">
                      ({Math.round(investigation.confidence * 100)}% confidence)
                    </span>
                  </div>
                  <p className="text-gray-200">{investigation.root_cause}</p>
                </div>

                {investigation.similar_incidents?.length > 0 && (
                  <div className="p-4 bg-gray-800/50 rounded-lg">
                    <h4 className="text-sm font-medium text-gray-400 mb-2">
                      Similar Past Incidents
                    </h4>
                    <ul className="space-y-1">
                      {investigation.similar_incidents.map((inc, i) => (
                        <li key={i} className="text-sm text-gray-300">
                          • {inc}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <div className="text-gray-500 text-center py-4">
                Analysis in progress...
              </div>
            )}
          </div>
        )}

        {activeTab === "actions" && (
          <ActionsList
            actions={investigation.actions}
            investigationId={investigation.id}
            onActionUpdate={onUpdate}
          />
        )}
      </div>
    </Card>
  );
}

function NewInvestigationForm({ onSubmit }: { onSubmit: () => void }) {
  const [issue, setIssue] = useState("");
  const [namespace, setNamespace] = useState("default");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!issue.trim()) return;

    setLoading(true);
    try {
      await fetchApi("/investigate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ issue, namespace }),
      });
      setIssue("");
      onSubmit();
    } catch (error) {
      console.error("Failed to start investigation:", error);
    }
    setLoading(false);
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <div className="flex-1 relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
        <input
          type="text"
          value={issue}
          onChange={(e) => setIssue(e.target.value)}
          placeholder="Describe the issue... (e.g., 'high latency on payment-service')"
          className="w-full pl-10 pr-4 py-3 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-blue-500 text-white placeholder-gray-500"
        />
      </div>
      <select
        value={namespace}
        onChange={(e) => setNamespace(e.target.value)}
        className="px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-blue-500 text-white"
      >
        <option value="default">default</option>
        <option value="production">production</option>
        <option value="staging">staging</option>
        <option value="kube-system">kube-system</option>
      </select>
      <button
        type="submit"
        disabled={loading || !issue.trim()}
        className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg font-medium transition-colors flex items-center gap-2"
      >
        {loading ? (
          <RefreshCw className="w-5 h-5 animate-spin" />
        ) : (
          <Zap className="w-5 h-5" />
        )}
        Investigate
      </button>
    </form>
  );
}

// Main Page
export default function Home() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedInvestigation, setSelectedInvestigation] =
    useState<Investigation | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await fetchApi<SystemStatus>("/status");
      setStatus(data);
    } catch (error) {
      console.error("Failed to fetch status:", error);
    }
  }, []);

  const fetchInvestigations = useCallback(async () => {
    try {
      const data = await fetchApi<Investigation[]>("/investigations");
      setInvestigations(data);
    } catch (error) {
      console.error("Failed to fetch investigations:", error);
    }
  }, []);

  const fetchSelectedInvestigation = useCallback(async () => {
    if (!selectedId) return;
    try {
      const data = await fetchApi<Investigation>(`/investigations/${selectedId}`);
      setSelectedInvestigation(data);
    } catch (error) {
      console.error("Failed to fetch investigation:", error);
    }
  }, [selectedId]);

  useEffect(() => {
    fetchStatus();
    fetchInvestigations();

    // Poll for updates
    const interval = setInterval(() => {
      fetchInvestigations();
      if (selectedId) fetchSelectedInvestigation();
    }, 5000);

    return () => clearInterval(interval);
  }, [fetchStatus, fetchInvestigations, selectedId, fetchSelectedInvestigation]);

  useEffect(() => {
    if (selectedId) {
      fetchSelectedInvestigation();
    }
  }, [selectedId, fetchSelectedInvestigation]);

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Shield className="w-8 h-8 text-blue-500" />
              <div>
                <h1 className="text-xl font-bold">SRE-Agent</h1>
                <p className="text-xs text-gray-400">
                  AI-Powered Incident Investigation
                </p>
              </div>
            </div>
            <IntegrationStatus status={status} />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6">
        {/* Investigation Input */}
        <Card className="p-4 mb-6">
          <NewInvestigationForm onSubmit={fetchInvestigations} />
        </Card>

        {/* Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Investigations List */}
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-gray-200">
              Investigations
            </h2>
            {investigations.length === 0 ? (
              <Card className="p-8 text-center text-gray-500">
                <Terminal className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No investigations yet</p>
                <p className="text-sm mt-2">
                  Start by describing an issue above
                </p>
              </Card>
            ) : (
              <div className="space-y-3">
                {investigations.map((inv) => (
                  <InvestigationCard
                    key={inv.id}
                    investigation={inv as Investigation}
                    onSelect={() => setSelectedId(inv.id)}
                    isSelected={selectedId === inv.id}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Investigation Detail */}
          <div>
            {selectedInvestigation ? (
              <InvestigationDetail
                investigation={selectedInvestigation}
                onUpdate={fetchSelectedInvestigation}
              />
            ) : (
              <Card className="p-8 text-center text-gray-500 h-96 flex flex-col items-center justify-center">
                <Eye className="w-12 h-12 mb-4 opacity-50" />
                <p>Select an investigation to view details</p>
              </Card>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-4 text-center text-gray-500 text-sm">
        SRE-Agent v{status?.version || "0.1.0"} • Built with 🛡️ by SREs, for
        SREs
      </footer>
    </div>
  );
}
