"use client";

import { useParams } from "next/navigation";
import { useInvestigation, useInvestigationStream, useInvestigationStore } from "@/lib/hooks";
import { InvestigationChat } from "@/components/InvestigationChat";
import { HypothesisCard } from "@/components/HypothesisCard";
import { SkillExecution } from "@/components/SkillExecution";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { formatRelativeTime, getSeverityColor, getStatusColor, formatDuration } from "@/lib/utils";
import { ArrowLeft, Clock, Target, Lightbulb, AlertCircle } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

export default function InvestigationDetailPage() {
  const params = useParams();
  const id = params.id as string;
  
  const { data: investigation, isLoading } = useInvestigation(id);
  const store = useInvestigationStore();
  
  // Connect to SSE stream for live updates
  useInvestigationStream(investigation?.status === "investigating" ? id : null);
  
  // Initialize store from investigation data
  useEffect(() => {
    if (investigation) {
      store.setCurrentInvestigation(investigation);
      // Populate hypotheses and findings from investigation
      investigation.hypotheses?.forEach((h) => {
        if (!store.hypotheses.find((sh) => sh.id === h.id)) {
          store.addHypothesis(h);
        }
      });
      investigation.findings?.forEach((f) => {
        if (!store.findings.find((sf) => sf.id === f.id)) {
          store.addFinding(f);
        }
      });
    }
  }, [investigation, store]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!investigation) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <AlertCircle className="w-12 h-12 text-muted-foreground" />
        <p className="text-lg">Investigation not found</p>
        <Link href="/investigate" className="text-primary hover:underline">
          ← Back to investigations
        </Link>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b bg-card/50">
        <div className="flex items-start gap-4">
          <Link
            href="/investigate"
            className="p-2 rounded-lg hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${getSeverityColor(investigation.severity)}`}>
                {investigation.severity}
              </span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(investigation.status)}`}>
                {investigation.status}
              </span>
              {store.isStreaming && (
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-500/10 text-blue-500 animate-pulse-subtle">
                  Live
                </span>
              )}
            </div>
            <h1 className="text-xl font-bold">{investigation.title}</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {investigation.description}
            </p>
          </div>
          <div className="text-right text-sm text-muted-foreground">
            <p>Started {formatRelativeTime(investigation.createdAt)}</p>
            {investigation.updatedAt !== investigation.createdAt && (
              <p>Updated {formatRelativeTime(investigation.updatedAt)}</p>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Main Chat */}
        <div className="flex-1 flex flex-col">
          <InvestigationChat />
        </div>

        {/* Right Sidebar */}
        <div className="w-96 border-l bg-card/50 flex flex-col overflow-hidden">
          {/* Stats */}
          <div className="p-4 border-b grid grid-cols-3 gap-3">
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 text-muted-foreground mb-1">
                <Clock className="w-3 h-3" />
                <span className="text-xs">Duration</span>
              </div>
              <p className="font-semibold">
                {investigation.timeline?.length > 0
                  ? formatDuration(
                      new Date(investigation.updatedAt).getTime() -
                        new Date(investigation.createdAt).getTime()
                    )
                  : "—"}
              </p>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 text-muted-foreground mb-1">
                <Lightbulb className="w-3 h-3" />
                <span className="text-xs">Hypotheses</span>
              </div>
              <p className="font-semibold">{investigation.hypotheses?.length || 0}</p>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center gap-1 text-muted-foreground mb-1">
                <Target className="w-3 h-3" />
                <span className="text-xs">Findings</span>
              </div>
              <p className="font-semibold">{investigation.findings?.length || 0}</p>
            </div>
          </div>

          {/* Active Skills */}
          {store.activeSkills.filter((s) => s.status === "running").length > 0 && (
            <div className="p-4 border-b">
              <h3 className="font-semibold mb-3 text-sm">Running Skills</h3>
              <div className="space-y-2">
                {store.activeSkills
                  .filter((s) => s.status === "running")
                  .map((skill) => (
                    <SkillExecution key={skill.id} execution={skill} />
                  ))}
              </div>
            </div>
          )}

          {/* Hypotheses */}
          <div className="flex-1 overflow-auto p-4">
            <h3 className="font-semibold mb-3 text-sm">Hypotheses</h3>
            <div className="space-y-3">
              {(investigation.hypotheses || store.hypotheses).map((h) => (
                <HypothesisCard key={h.id} hypothesis={h} />
              ))}
              {(investigation.hypotheses?.length || 0) === 0 &&
                store.hypotheses.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No hypotheses yet
                  </p>
                )}
            </div>
          </div>

          {/* Findings */}
          {(investigation.findings?.length || store.findings.length) > 0 && (
            <div className="p-4 border-t max-h-64 overflow-auto">
              <h3 className="font-semibold mb-3 text-sm">Findings</h3>
              <div className="space-y-2">
                {(investigation.findings || store.findings).map((f) => (
                  <Card key={f.id} className="bg-muted/30">
                    <CardContent className="p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <span
                          className={`px-1.5 py-0.5 rounded text-xs ${
                            f.type === "root_cause"
                              ? "bg-red-500/10 text-red-500"
                              : f.type === "recommendation"
                              ? "bg-green-500/10 text-green-500"
                              : "bg-blue-500/10 text-blue-500"
                          }`}
                        >
                          {f.type.replace("_", " ")}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {Math.round(f.confidence * 100)}% confidence
                        </span>
                      </div>
                      <p className="text-sm">{f.content}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
