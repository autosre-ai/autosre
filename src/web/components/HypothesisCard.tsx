"use client";

import { Lightbulb, CheckCircle, XCircle, HelpCircle, Search } from "lucide-react";
import type { Hypothesis } from "@/lib/types";
import { cn } from "@/lib/utils";

interface HypothesisCardProps {
  hypothesis: Hypothesis;
  onClick?: () => void;
}

export function HypothesisCard({ hypothesis, onClick }: HypothesisCardProps) {
  const statusConfig = {
    investigating: {
      icon: Search,
      color: "text-blue-500",
      bg: "bg-blue-500/10",
      border: "border-blue-500/20",
    },
    confirmed: {
      icon: CheckCircle,
      color: "text-green-500",
      bg: "bg-green-500/10",
      border: "border-green-500/20",
    },
    rejected: {
      icon: XCircle,
      color: "text-red-500",
      bg: "bg-red-500/10",
      border: "border-red-500/20",
    },
    needs_more_data: {
      icon: HelpCircle,
      color: "text-yellow-500",
      bg: "bg-yellow-500/10",
      border: "border-yellow-500/20",
    },
  };

  const config = statusConfig[hypothesis.status];
  const StatusIcon = config.icon;
  const confidencePercent = Math.round(hypothesis.confidence * 100);

  return (
    <div
      className={cn(
        "p-3 rounded-lg border transition-colors",
        config.border,
        config.bg,
        onClick && "cursor-pointer hover:opacity-80"
      )}
      onClick={onClick}
    >
      <div className="flex items-start gap-3">
        <div className={cn("p-1.5 rounded", config.bg)}>
          <Lightbulb className={cn("w-4 h-4", config.color)} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <StatusIcon className={cn("w-3.5 h-3.5", config.color)} />
              <span className={cn("text-xs font-medium", config.color)}>
                {hypothesis.status.replace("_", " ")}
              </span>
            </div>
            <span className="text-xs text-muted-foreground">
              {confidencePercent}%
            </span>
          </div>

          <p className="text-sm">{hypothesis.content}</p>

          {/* Confidence bar */}
          <div className="mt-2 h-1 bg-muted rounded-full overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all", config.bg.replace("/10", ""))}
              style={{ width: `${confidencePercent}%` }}
            />
          </div>

          {/* Evidence count */}
          {hypothesis.evidence && hypothesis.evidence.length > 0 && (
            <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              <span>
                {hypothesis.evidence.filter((e) => e.supports).length} supporting
              </span>
              <span>•</span>
              <span>
                {hypothesis.evidence.filter((e) => !e.supports).length} contradicting
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
