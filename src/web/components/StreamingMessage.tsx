"use client";

import { useEffect, useState } from "react";

interface StreamingMessageProps {
  content: string;
  speed?: number;
}

export function StreamingMessage({ content, speed = 20 }: StreamingMessageProps) {
  const [displayedContent, setDisplayedContent] = useState("");
  const [isComplete, setIsComplete] = useState(false);

  useEffect(() => {
    // Reset when content changes
    setDisplayedContent("");
    setIsComplete(false);

    let currentIndex = 0;
    const intervalId = setInterval(() => {
      if (currentIndex < content.length) {
        // Add multiple characters at once for faster streaming
        const charsToAdd = Math.min(3, content.length - currentIndex);
        setDisplayedContent(content.slice(0, currentIndex + charsToAdd));
        currentIndex += charsToAdd;
      } else {
        setIsComplete(true);
        clearInterval(intervalId);
      }
    }, speed);

    return () => clearInterval(intervalId);
  }, [content, speed]);

  // If content is short or streaming is complete, just show it
  if (content.length < 20 || isComplete) {
    return <MessageContent content={content} />;
  }

  return (
    <div className="text-sm">
      <MessageContent content={displayedContent} />
      {!isComplete && <span className="cursor-blink" />}
    </div>
  );
}

function MessageContent({ content }: { content: string }) {
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
        if (line.startsWith("* ")) {
          return (
            <li key={i} className="ml-4">
              {line.slice(2)}
            </li>
          );
        }
        if (line.match(/^\d+\. /)) {
          return (
            <li key={i} className="ml-4 list-decimal">
              {line.replace(/^\d+\. /, "")}
            </li>
          );
        }
        if (line.startsWith("```")) {
          return null;
        }
        if (line.trim() === "") {
          return <br key={i} />;
        }
        // Handle inline code
        const parts = line.split(/(`[^`]+`)/g);
        return (
          <p key={i}>
            {parts.map((part, j) => {
              if (part.startsWith("`") && part.endsWith("`")) {
                return (
                  <code key={j} className="px-1 py-0.5 bg-muted rounded text-xs">
                    {part.slice(1, -1)}
                  </code>
                );
              }
              // Handle bold
              const boldParts = part.split(/(\*\*[^*]+\*\*)/g);
              return boldParts.map((bp, k) => {
                if (bp.startsWith("**") && bp.endsWith("**")) {
                  return <strong key={`${j}-${k}`}>{bp.slice(2, -2)}</strong>;
                }
                return bp;
              });
            })}
          </p>
        );
      })}
    </div>
  );
}
