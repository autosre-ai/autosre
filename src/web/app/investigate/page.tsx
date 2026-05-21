"use client";

import { useState } from "react";
import { Send, Loader2, Plus } from "lucide-react";
import { useInvestigationStore, useStartInvestigation, useInvestigations } from "@/lib/hooks";
import { InvestigationChat } from "@/components/InvestigationChat";
import { HypothesisCard } from "@/components/HypothesisCard";
import { SkillExecution } from "@/components/SkillExecution";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import Link from "next/link";
import { formatRelativeTime, getSeverityColor, getStatusColor } from "@/lib/utils";

export default function InvestigatePage() {
  const [description, setDescription] = useState("");
  const [urgency, setUrgency] = useState<"critical" | "high" | "medium" | "low">("medium");
  
  const store = useInvestigationStore();
  const { mutate: startInvestigation, isPending } = useStartInvestigation();
  const { data: investigations } = useInvestigations();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim() || isPending || store.isStreaming) return;
    
    startInvestigation({
      description: description.trim(),
      urgency,
    });
    setDescription("");
  };

  const isActive = store.isStreaming || store.messages.length > 0;

  return (
    <div className="h-full flex">
      {/* Left Panel - Investigation List */}
      <div className="w-72 border-r bg-card/50 flex flex-col">
        <div className="p-4 border-b">
          <h2 className="font-semibold">Investigations</h2>
        </div>
        <div className="flex-1 overflow-auto p-2 space-y-1">
          {investigations?.map((inv) => (
            <Link
              key={inv.id}
              href={`/investigate/${inv.id}`}
              className="block p-3 rounded-lg hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`px-1.5 py-0.5 rounded text-xs ${getSeverityColor(inv.severity)}`}>
                  {inv.severity}
                </span>
                <span className={`px-1.5 py-0.5 rounded text-xs ${getStatusColor(inv.status)}`}>
                  {inv.status}
                </span>
              </div>
              <p className="text-sm font-medium truncate">{inv.title}</p>
              <p className="text-xs text-muted-foreground">
                {formatRelativeTime(inv.createdAt)}
              </p>
            </Link>
          ))}
          {(!investigations || investigations.length === 0) && (
            <p className="text-sm text-muted-foreground text-center py-8">
              No investigations yet
            </p>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {!isActive ? (
          /* New Investigation Form */
          <div className="flex-1 flex items-center justify-center p-8">
            <Card className="w-full max-w-2xl">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Plus className="w-5 h-5" />
                  Start New Investigation
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Describe the incident
                    </label>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="e.g., API latency increased to 2s for /users endpoint in production..."
                      className="w-full h-32 px-4 py-3 bg-background border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-primary"
                      disabled={isPending}
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Urgency
                    </label>
                    <div className="flex gap-2">
                      {(["critical", "high", "medium", "low"] as const).map((level) => (
                        <button
                          key={level}
                          type="button"
                          onClick={() => setUrgency(level)}
                          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                            urgency === level
                              ? getSeverityColor(level)
                              : "bg-muted hover:bg-muted/80"
                          }`}
                        >
                          {level.charAt(0).toUpperCase() + level.slice(1)}
                        </button>
                      ))}
                    </div>
                  </div>

                  <Button
                    type="submit"
                    size="lg"
                    className="w-full gap-2"
                    disabled={!description.trim() || isPending}
                  >
                    {isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Starting...
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4" />
                        Start Investigation
                      </>
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        ) : (
          /* Active Investigation */
          <div className="flex-1 flex">
            {/* Chat Area */}
            <div className="flex-1 flex flex-col">
              <InvestigationChat />
            </div>

            {/* Right Sidebar - Hypotheses & Skills */}
            <div className="w-80 border-l bg-card/50 flex flex-col">
              {/* Active Skills */}
              <div className="p-4 border-b">
                <h3 className="font-semibold mb-3">Active Skills</h3>
                <div className="space-y-2">
                  {store.activeSkills
                    .filter((s) => s.status === "running")
                    .map((skill) => (
                      <SkillExecution key={skill.id} execution={skill} />
                    ))}
                  {store.activeSkills.filter((s) => s.status === "running").length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      No skills running
                    </p>
                  )}
                </div>
              </div>

              {/* Hypotheses */}
              <div className="flex-1 overflow-auto p-4">
                <h3 className="font-semibold mb-3">Hypotheses</h3>
                <div className="space-y-3">
                  {store.hypotheses.map((h) => (
                    <HypothesisCard key={h.id} hypothesis={h} />
                  ))}
                  {store.hypotheses.length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      No hypotheses yet
                    </p>
                  )}
                </div>
              </div>

              {/* Findings Summary */}
              {store.findings.length > 0 && (
                <div className="p-4 border-t">
                  <h3 className="font-semibold mb-2">Findings</h3>
                  <div className="space-y-2">
                    {store.findings.slice(0, 3).map((f) => (
                      <div
                        key={f.id}
                        className="text-sm p-2 rounded bg-muted/50"
                      >
                        <span className="text-xs text-muted-foreground">
                          {f.type}:
                        </span>
                        <p className="truncate">{f.content}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
