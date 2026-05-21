"use client";

import { useState } from "react";
import { Settings, Users, Zap, Brain, Save, RotateCcw } from "lucide-react";
import {
  useSkills,
  useTeamConfig,
  useLLMConfig,
  useToggleSkill,
  useUpdateTeamConfig,
  useUpdateLLMConfig,
} from "@/lib/hooks";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import type { Skill, LLMConfig, TeamConfig } from "@/lib/types";

export default function ConfigPage() {
  const [activeTab, setActiveTab] = useState<"skills" | "team" | "llm">("skills");

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <Settings className="w-8 h-8" />
          Configuration
        </h1>
        <p className="text-muted-foreground mt-1">
          Manage skills, team settings, and LLM configuration
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b">
        <button
          onClick={() => setActiveTab("skills")}
          className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
            activeTab === "skills"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Zap className="w-4 h-4" />
          Skills
        </button>
        <button
          onClick={() => setActiveTab("team")}
          className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
            activeTab === "team"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Users className="w-4 h-4" />
          Team
        </button>
        <button
          onClick={() => setActiveTab("llm")}
          className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
            activeTab === "llm"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Brain className="w-4 h-4" />
          LLM
        </button>
      </div>

      {/* Content */}
      {activeTab === "skills" && <SkillsConfig />}
      {activeTab === "team" && <TeamConfigPanel />}
      {activeTab === "llm" && <LLMConfigPanel />}
    </div>
  );
}

function SkillsConfig() {
  const { data: skills, isLoading } = useSkills();
  const { mutate: toggleSkill, isPending } = useToggleSkill();

  const categories = ["observability", "kubernetes", "database", "network", "custom"] as const;

  const skillsByCategory = categories.reduce((acc, cat) => {
    acc[cat] = skills?.filter((s) => s.category === cat) || [];
    return acc;
  }, {} as Record<string, Skill[]>);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-48 bg-muted animate-pulse rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {categories.map((category) => {
        const categorySkills = skillsByCategory[category];
        if (categorySkills.length === 0) return null;

        return (
          <Card key={category}>
            <CardHeader>
              <CardTitle className="capitalize">{category}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {categorySkills.map((skill) => (
                  <div
                    key={skill.id}
                    className="flex items-start justify-between p-4 rounded-lg border"
                  >
                    <div className="flex-1">
                      <h4 className="font-medium">{skill.name}</h4>
                      <p className="text-sm text-muted-foreground mt-1">
                        {skill.description}
                      </p>
                    </div>
                    <button
                      onClick={() =>
                        toggleSkill({ id: skill.id, enabled: !skill.enabled })
                      }
                      disabled={isPending}
                      className={`relative w-11 h-6 rounded-full transition-colors ${
                        skill.enabled ? "bg-primary" : "bg-muted"
                      }`}
                    >
                      <span
                        className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                          skill.enabled ? "translate-x-5" : "translate-x-0"
                        }`}
                      />
                    </button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        );
      })}

      {(!skills || skills.length === 0) && (
        <Card>
          <CardContent className="py-12 text-center">
            <Zap className="w-12 h-12 mx-auto mb-4 text-muted-foreground opacity-50" />
            <p className="text-lg font-medium">No skills configured</p>
            <p className="text-sm text-muted-foreground">
              Skills will appear here once registered with the API
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function TeamConfigPanel() {
  const { data: config, isLoading } = useTeamConfig();
  const { mutate: updateConfig, isPending } = useUpdateTeamConfig();
  const [localConfig, setLocalConfig] = useState<Partial<TeamConfig>>({});

  const currentConfig = { ...config, ...localConfig };

  const handleSave = () => {
    if (Object.keys(localConfig).length > 0) {
      updateConfig(localConfig);
      setLocalConfig({});
    }
  };

  const handleReset = () => {
    setLocalConfig({});
  };

  if (isLoading) {
    return <div className="h-96 bg-muted animate-pulse rounded-lg" />;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Coordinator Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">
              Max Parallel Agents
            </label>
            <input
              type="number"
              value={currentConfig.coordinator?.maxParallelAgents || 3}
              onChange={(e) =>
                setLocalConfig({
                  ...localConfig,
                  coordinator: {
                    ...currentConfig.coordinator,
                    maxParallelAgents: parseInt(e.target.value),
                  } as TeamConfig["coordinator"],
                })
              }
              className="w-full px-4 py-2 bg-background border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              min={1}
              max={10}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Maximum number of agents that can work simultaneously
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Escalation Threshold
            </label>
            <input
              type="number"
              value={currentConfig.coordinator?.escalationThreshold || 3}
              onChange={(e) =>
                setLocalConfig({
                  ...localConfig,
                  coordinator: {
                    ...currentConfig.coordinator,
                    escalationThreshold: parseInt(e.target.value),
                  } as TeamConfig["coordinator"],
                })
              }
              className="w-full px-4 py-2 bg-background border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              min={1}
              max={10}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Number of failed attempts before escalating
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">
              Timeout (minutes)
            </label>
            <input
              type="number"
              value={currentConfig.coordinator?.timeoutMinutes || 30}
              onChange={(e) =>
                setLocalConfig({
                  ...localConfig,
                  coordinator: {
                    ...currentConfig.coordinator,
                    timeoutMinutes: parseInt(e.target.value),
                  } as TeamConfig["coordinator"],
                })
              }
              className="w-full px-4 py-2 bg-background border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              min={5}
              max={120}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Maximum time for an investigation before timing out
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Agents</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {currentConfig.agents?.map((agent, idx) => (
              <div
                key={agent.id}
                className="flex items-center justify-between p-4 rounded-lg border"
              >
                <div>
                  <h4 className="font-medium">{agent.name}</h4>
                  <p className="text-sm text-muted-foreground">{agent.role}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Model: {agent.model} • Skills: {agent.skills.length}
                  </p>
                </div>
                <button
                  onClick={() => {
                    const updatedAgents = [...(currentConfig.agents || [])];
                    updatedAgents[idx] = { ...agent, enabled: !agent.enabled };
                    setLocalConfig({ ...localConfig, agents: updatedAgents });
                  }}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    agent.enabled ? "bg-primary" : "bg-muted"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                      agent.enabled ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
            ))}
            {(!currentConfig.agents || currentConfig.agents.length === 0) && (
              <p className="text-sm text-muted-foreground text-center py-8">
                No agents configured
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Save/Reset buttons */}
      {Object.keys(localConfig).length > 0 && (
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={handleReset} disabled={isPending}>
            <RotateCcw className="w-4 h-4 mr-2" />
            Reset
          </Button>
          <Button onClick={handleSave} disabled={isPending}>
            <Save className="w-4 h-4 mr-2" />
            {isPending ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      )}
    </div>
  );
}

function LLMConfigPanel() {
  const { data: config, isLoading } = useLLMConfig();
  const { mutate: updateConfig, isPending } = useUpdateLLMConfig();
  const [localConfig, setLocalConfig] = useState<Partial<LLMConfig>>({});

  const currentConfig = { ...config, ...localConfig };

  const handleSave = () => {
    if (Object.keys(localConfig).length > 0) {
      updateConfig(localConfig);
      setLocalConfig({});
    }
  };

  const handleReset = () => {
    setLocalConfig({});
  };

  if (isLoading) {
    return <div className="h-96 bg-muted animate-pulse rounded-lg" />;
  }

  const providers = ["anthropic", "openai", "ollama", "custom"] as const;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>LLM Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Provider</label>
            <select
              value={currentConfig.provider || "anthropic"}
              onChange={(e) =>
                setLocalConfig({
                  ...localConfig,
                  provider: e.target.value as LLMConfig["provider"],
                })
              }
              className="w-full px-4 py-2 bg-background border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {providers.map((p) => (
                <option key={p} value={p}>
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Model</label>
            <input
              type="text"
              value={currentConfig.model || ""}
              onChange={(e) =>
                setLocalConfig({ ...localConfig, model: e.target.value })
              }
              placeholder="claude-sonnet-4-20250514"
              className="w-full px-4 py-2 bg-background border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          {currentConfig.provider === "custom" && (
            <div>
              <label className="block text-sm font-medium mb-2">Base URL</label>
              <input
                type="url"
                value={currentConfig.baseUrl || ""}
                onChange={(e) =>
                  setLocalConfig({ ...localConfig, baseUrl: e.target.value })
                }
                placeholder="https://api.example.com/v1"
                className="w-full px-4 py-2 bg-background border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-2">API Key</label>
            <input
              type="password"
              value={currentConfig.apiKey || ""}
              onChange={(e) =>
                setLocalConfig({ ...localConfig, apiKey: e.target.value })
              }
              placeholder="••••••••••••"
              className="w-full px-4 py-2 bg-background border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Leave blank to use environment variable
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Temperature
              </label>
              <input
                type="number"
                value={currentConfig.temperature ?? 0.7}
                onChange={(e) =>
                  setLocalConfig({
                    ...localConfig,
                    temperature: parseFloat(e.target.value),
                  })
                }
                className="w-full px-4 py-2 bg-background border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                min={0}
                max={2}
                step={0.1}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2">
                Max Tokens
              </label>
              <input
                type="number"
                value={currentConfig.maxTokens || 4096}
                onChange={(e) =>
                  setLocalConfig({
                    ...localConfig,
                    maxTokens: parseInt(e.target.value),
                  })
                }
                className="w-full px-4 py-2 bg-background border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                min={256}
                max={32000}
                step={256}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Save/Reset buttons */}
      {Object.keys(localConfig).length > 0 && (
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={handleReset} disabled={isPending}>
            <RotateCcw className="w-4 h-4 mr-2" />
            Reset
          </Button>
          <Button onClick={handleSave} disabled={isPending}>
            <Save className="w-4 h-4 mr-2" />
            {isPending ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      )}
    </div>
  );
}
