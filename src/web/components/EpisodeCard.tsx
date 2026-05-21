"use client";

import { Brain, Clock, CheckCircle, AlertTriangle, ChevronRight } from "lucide-react";
import type { Episode } from "@/lib/types";
import { formatRelativeTime, formatDuration, cn } from "@/lib/utils";
import Link from "next/link";

interface EpisodeCardProps {
  episode: Episode;
}

export function EpisodeCard({ episode }: EpisodeCardProps) {
  const outcomeConfig = {
    resolved: {
      icon: CheckCircle,
      color: "text-green-500",
      bg: "bg-green-500/10",
    },
    escalated: {
      icon: AlertTriangle,
      color: "text-red-500",
      bg: "bg-red-500/10",
    },
    partial: {
      icon: Brain,
      color: "text-yellow-500",
      bg: "bg-yellow-500/10",
    },
  };

  const config = outcomeConfig[episode.outcome];
  const OutcomeIcon = config.icon;

  return (
    <Link
      href={`/investigate/${episode.investigationId}`}
      className="block p-4 rounded-lg border hover:bg-muted/50 transition-colors"
    >
      <div className="flex items-start gap-4">
        <div className={cn("p-2 rounded-lg", config.bg)}>
          <OutcomeIcon className={cn("w-5 h-5", config.color)} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className={cn("text-xs font-medium px-2 py-0.5 rounded", config.bg, config.color)}>
              {episode.outcome}
            </span>
            <span className="text-xs text-muted-foreground">
              {formatRelativeTime(episode.createdAt)}
            </span>
          </div>

          <h3 className="font-medium mb-1 line-clamp-2">{episode.summary}</h3>

          {episode.rootCause && (
            <p className="text-sm text-muted-foreground mb-2 line-clamp-2">
              Root cause: {episode.rootCause}
            </p>
          )}

          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              <span>{formatDuration(episode.metadata.duration)}</span>
            </div>
            <span>•</span>
            <span>{episode.metadata.skillsUsed.length} skills used</span>
            <span>•</span>
            <span>{episode.metadata.hypothesesCount} hypotheses</span>
          </div>

          {/* Skills used */}
          {episode.metadata.skillsUsed.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1">
              {episode.metadata.skillsUsed.slice(0, 5).map((skill) => (
                <span
                  key={skill}
                  className="text-xs px-2 py-0.5 bg-muted rounded"
                >
                  {skill}
                </span>
              ))}
              {episode.metadata.skillsUsed.length > 5 && (
                <span className="text-xs px-2 py-0.5 bg-muted rounded text-muted-foreground">
                  +{episode.metadata.skillsUsed.length - 5} more
                </span>
              )}
            </div>
          )}
        </div>

        <ChevronRight className="w-5 h-5 text-muted-foreground" />
      </div>
    </Link>
  );
}
