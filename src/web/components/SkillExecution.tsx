"use client";

import { Loader2, CheckCircle, XCircle, Zap } from "lucide-react";
import type { SkillExecution as SkillExecutionType } from "@/lib/types";
import { formatDuration } from "@/lib/utils";

interface SkillExecutionProps {
  execution: SkillExecutionType;
  compact?: boolean;
}

export function SkillExecution({ execution, compact = false }: SkillExecutionProps) {
  const isRunning = execution.status === "running";
  const isCompleted = execution.status === "completed";
  const isFailed = execution.status === "failed";

  if (compact) {
    return (
      <div className="flex items-center gap-2 text-sm">
        {isRunning && <Loader2 className="w-3 h-3 animate-spin text-blue-500" />}
        {isCompleted && <CheckCircle className="w-3 h-3 text-green-500" />}
        {isFailed && <XCircle className="w-3 h-3 text-red-500" />}
        <span className="truncate">{execution.skillName}</span>
      </div>
    );
  }

  return (
    <div
      className={`p-3 rounded-lg border transition-colors ${
        isRunning
          ? "border-blue-500/30 bg-blue-500/5"
          : isCompleted
          ? "border-green-500/30 bg-green-500/5"
          : "border-red-500/30 bg-red-500/5"
      }`}
    >
      <div className="flex items-start gap-3">
        <div
          className={`p-1.5 rounded ${
            isRunning
              ? "bg-blue-500/10"
              : isCompleted
              ? "bg-green-500/10"
              : "bg-red-500/10"
          }`}
        >
          {isRunning ? (
            <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
          ) : isCompleted ? (
            <CheckCircle className="w-4 h-4 text-green-500" />
          ) : (
            <XCircle className="w-4 h-4 text-red-500" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-sm truncate">{execution.skillName}</h4>
            {execution.duration && (
              <span className="text-xs text-muted-foreground">
                {formatDuration(execution.duration)}
              </span>
            )}
          </div>

          {isRunning && (
            <p className="text-xs text-muted-foreground mt-1 animate-pulse-subtle">
              Executing...
            </p>
          )}

          {isFailed && execution.error && (
            <p className="text-xs text-red-400 mt-1 truncate">{execution.error}</p>
          )}

          {isCompleted && execution.output && (
            <details className="mt-2">
              <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                View output
              </summary>
              <pre className="mt-1 text-xs bg-muted p-2 rounded overflow-x-auto max-h-32">
                {typeof execution.output === "string"
                  ? execution.output
                  : JSON.stringify(execution.output, null, 2)}
              </pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}
