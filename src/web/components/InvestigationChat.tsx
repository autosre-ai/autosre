"use client";

import { useRef, useEffect } from "react";
import { Bot, User, Zap, AlertCircle } from "lucide-react";
import { useInvestigationStore } from "@/lib/hooks";
import { StreamingMessage } from "./StreamingMessage";
import { cn } from "@/lib/utils";
import type { Message } from "@/lib/types";

export function InvestigationChat() {
  const { messages, isStreaming } = useInvestigationStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-auto p-4 space-y-4">
        {messages.length === 0 && !isStreaming && (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <div className="text-center">
              <Bot className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>Waiting for investigation to start...</p>
            </div>
          </div>
        )}

        {messages.map((message, idx) => (
          <ChatMessage
            key={message.id}
            message={message}
            isLast={idx === messages.length - 1}
            isStreaming={isStreaming && idx === messages.length - 1}
          />
        ))}

        {isStreaming && messages.length === 0 && (
          <div className="flex items-start gap-3 animate-slide-in">
            <div className="p-2 rounded-lg bg-primary/10">
              <Bot className="w-5 h-5 text-primary" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium">AutoSRE</p>
              <div className="mt-1 p-3 rounded-lg bg-muted">
                <span className="cursor-blink">Starting investigation</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ChatMessage({
  message,
  isLast,
  isStreaming,
}: {
  message: Message;
  isLast: boolean;
  isStreaming: boolean;
}) {
  const isUser = message.role === "user";
  const isSkill = message.role === "skill";
  const isSystem = message.role === "system";

  return (
    <div
      className={cn(
        "flex items-start gap-3 animate-slide-in",
        isUser && "flex-row-reverse"
      )}
    >
      <div
        className={cn(
          "p-2 rounded-lg",
          isUser
            ? "bg-blue-500/10"
            : isSkill
            ? "bg-orange-500/10"
            : isSystem
            ? "bg-red-500/10"
            : "bg-primary/10"
        )}
      >
        {isUser ? (
          <User className="w-5 h-5 text-blue-500" />
        ) : isSkill ? (
          <Zap className="w-5 h-5 text-orange-500" />
        ) : isSystem ? (
          <AlertCircle className="w-5 h-5 text-red-500" />
        ) : (
          <Bot className="w-5 h-5 text-primary" />
        )}
      </div>

      <div className={cn("flex-1", isUser && "text-right")}>
        <p className="text-sm font-medium">
          {isUser
            ? "You"
            : isSkill
            ? message.metadata?.skillExecution?.skillName || "Skill"
            : isSystem
            ? "System"
            : "AutoSRE"}
        </p>
        <div
          className={cn(
            "mt-1 p-3 rounded-lg inline-block max-w-[80%]",
            isUser
              ? "bg-blue-500 text-white text-left"
              : isSystem
              ? "bg-red-500/10 border border-red-500/20"
              : "bg-muted"
          )}
        >
          {isLast && isStreaming && !isUser ? (
            <StreamingMessage content={message.content} />
          ) : (
            <MessageContent content={message.content} isSkill={isSkill} />
          )}
        </div>

        {/* Skill execution details */}
        {isSkill && message.metadata?.skillExecution && (
          <div className="mt-2 text-xs text-muted-foreground">
            Duration:{" "}
            {message.metadata.skillExecution.duration
              ? `${message.metadata.skillExecution.duration}ms`
              : "N/A"}{" "}
            • Status: {message.metadata.skillExecution.status}
          </div>
        )}
      </div>
    </div>
  );
}

function MessageContent({
  content,
  isSkill,
}: {
  content: string;
  isSkill: boolean;
}) {
  // For skill outputs, try to format as code
  if (isSkill) {
    try {
      const parsed = JSON.parse(content);
      return (
        <pre className="text-sm overflow-x-auto whitespace-pre-wrap">
          <code>{JSON.stringify(parsed, null, 2)}</code>
        </pre>
      );
    } catch {
      // Not JSON, render as-is
    }
  }

  // Simple markdown-like rendering
  const lines = content.split("\n");
  return (
    <div className="text-sm space-y-1">
      {lines.map((line, i) => {
        if (line.startsWith("# ")) {
          return (
            <h3 key={i} className="font-bold text-base">
              {line.slice(2)}
            </h3>
          );
        }
        if (line.startsWith("## ")) {
          return (
            <h4 key={i} className="font-semibold">
              {line.slice(3)}
            </h4>
          );
        }
        if (line.startsWith("- ")) {
          return (
            <li key={i} className="ml-4">
              {line.slice(2)}
            </li>
          );
        }
        if (line.startsWith("```")) {
          return null; // Skip code fence markers
        }
        if (line.trim() === "") {
          return <br key={i} />;
        }
        return <p key={i}>{line}</p>;
      })}
    </div>
  );
}
