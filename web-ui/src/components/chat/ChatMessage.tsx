import { useState } from 'react';
import {
  User,
  Bot,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  RefreshCw,
  Terminal,
  AlertTriangle,
  CheckCircle,
  Clock,
  Wrench,
} from 'lucide-react';
import { CodeBlock } from './CodeBlock';
import { cn, formatRelativeTime } from '@/lib/utils';
import type { ChatMessage as ChatMessageType } from '@/types';

interface ChatMessageProps {
  message: ChatMessageType;
  isLast?: boolean;
  onRetry?: () => void;
  onCopy?: () => void;
  className?: string;
}

// Parse markdown-style content to extract code blocks and text
function parseContent(content: string): Array<{ type: 'text' | 'code'; content: string; language?: string }> {
  const parts: Array<{ type: 'text' | 'code'; content: string; language?: string }> = [];
  const codeBlockRegex = /```(\w*)\n?([\s\S]*?)```/g;
  
  let lastIndex = 0;
  let match;
  
  while ((match = codeBlockRegex.exec(content)) !== null) {
    // Add text before code block
    if (match.index > lastIndex) {
      const textBefore = content.slice(lastIndex, match.index).trim();
      if (textBefore) {
        parts.push({ type: 'text', content: textBefore });
      }
    }
    
    // Add code block
    parts.push({
      type: 'code',
      content: match[2].trim(),
      language: match[1] || 'bash',
    });
    
    lastIndex = match.index + match[0].length;
  }
  
  // Add remaining text
  if (lastIndex < content.length) {
    const remaining = content.slice(lastIndex).trim();
    if (remaining) {
      parts.push({ type: 'text', content: remaining });
    }
  }
  
  // If no parts found, return the whole content as text
  if (parts.length === 0) {
    parts.push({ type: 'text', content: content });
  }
  
  return parts;
}

// Simple markdown text renderer
function renderMarkdownText(text: string): React.ReactNode {
  // Split by lines to handle lists and paragraphs
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  
  let currentParagraph: string[] = [];
  
  const flushParagraph = () => {
    if (currentParagraph.length > 0) {
      elements.push(
        <p key={elements.length} className="mb-3 last:mb-0">
          {renderInlineMarkdown(currentParagraph.join(' '))}
        </p>
      );
      currentParagraph = [];
    }
  };
  
  lines.forEach((line, i) => {
    const trimmed = line.trim();
    
    // Headers
    if (trimmed.startsWith('### ')) {
      flushParagraph();
      elements.push(
        <h4 key={i} className="text-sm font-semibold text-white mt-4 mb-2 first:mt-0">
          {trimmed.slice(4)}
        </h4>
      );
    } else if (trimmed.startsWith('## ')) {
      flushParagraph();
      elements.push(
        <h3 key={i} className="text-base font-semibold text-white mt-4 mb-2 first:mt-0">
          {trimmed.slice(3)}
        </h3>
      );
    } else if (trimmed.startsWith('# ')) {
      flushParagraph();
      elements.push(
        <h2 key={i} className="text-lg font-bold text-white mt-4 mb-2 first:mt-0">
          {trimmed.slice(2)}
        </h2>
      );
    }
    // List items
    else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      flushParagraph();
      elements.push(
        <div key={i} className="flex gap-2 mb-1">
          <span className="text-stone-500">•</span>
          <span>{renderInlineMarkdown(trimmed.slice(2))}</span>
        </div>
      );
    }
    // Numbered list
    else if (/^\d+\.\s/.test(trimmed)) {
      flushParagraph();
      const match = trimmed.match(/^(\d+)\.\s(.*)$/);
      if (match) {
        elements.push(
          <div key={i} className="flex gap-2 mb-1">
            <span className="text-stone-500 w-4 text-right">{match[1]}.</span>
            <span>{renderInlineMarkdown(match[2])}</span>
          </div>
        );
      }
    }
    // Empty line = paragraph break
    else if (trimmed === '') {
      flushParagraph();
    }
    // Regular text
    else {
      currentParagraph.push(trimmed);
    }
  });
  
  flushParagraph();
  return <>{elements}</>;
}

// Render inline markdown (bold, italic, code, links)
function renderInlineMarkdown(text: string): React.ReactNode {
  const elements: React.ReactNode[] = [];
  
  // Pattern for inline formatting: **bold**, *italic*, `code`, [link](url)
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  const parts = text.split(pattern);
  
  parts.forEach((part, i) => {
    if (!part) return;
    
    // Bold
    if (part.startsWith('**') && part.endsWith('**')) {
      elements.push(
        <strong key={i} className="font-semibold text-white">
          {part.slice(2, -2)}
        </strong>
      );
    }
    // Italic
    else if (part.startsWith('*') && part.endsWith('*') && !part.startsWith('**')) {
      elements.push(
        <em key={i} className="italic">
          {part.slice(1, -1)}
        </em>
      );
    }
    // Inline code
    else if (part.startsWith('`') && part.endsWith('`')) {
      elements.push(
        <code key={i} className="px-1.5 py-0.5 rounded bg-stone-800 text-forest-light font-mono text-sm">
          {part.slice(1, -1)}
        </code>
      );
    }
    // Link
    else if (part.startsWith('[') && part.includes('](')) {
      const match = part.match(/\[([^\]]+)\]\(([^)]+)\)/);
      if (match) {
        elements.push(
          <a
            key={i}
            href={match[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="text-forest hover:text-forest-light underline"
          >
            {match[1]}
          </a>
        );
      } else {
        elements.push(part);
      }
    }
    // Plain text
    else {
      elements.push(part);
    }
  });
  
  return <>{elements}</>;
}

// Tool output component
function ToolOutput({ toolName, output }: { toolName: string; output: string }) {
  return (
    <div className="mt-3 p-3 rounded-lg bg-stone-800/50 border border-stone-700">
      <div className="flex items-center gap-2 mb-2 text-xs text-stone-400">
        <Terminal className="w-3.5 h-3.5" />
        <span>Output from {toolName}</span>
      </div>
      <pre className="text-xs text-stone-300 font-mono whitespace-pre-wrap overflow-x-auto">
        {output}
      </pre>
    </div>
  );
}

export function ChatMessage({ message, isLast, onRetry, onCopy, className }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);
  
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const isTool = message.role === 'tool';
  
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      onCopy?.();
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };
  
  const parsedContent = parseContent(message.content);
  
  // System message styling
  if (isSystem) {
    return (
      <div className={cn('flex justify-center py-2', className)}>
        <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-stone-800/50 border border-stone-700">
          <AlertTriangle className="w-4 h-4 text-yellow-500" />
          <span className="text-sm text-stone-400">{message.content}</span>
        </div>
      </div>
    );
  }
  
  // Tool result message styling
  if (isTool) {
    return (
      <div className={cn('flex gap-3 px-4 md:px-6 py-2', className)}>
        <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-stone-700 flex items-center justify-center">
          <Wrench className="w-4 h-4 text-stone-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-stone-400">Tool Result</span>
            {message.metadata?.toolName && (
              <span className="px-1.5 py-0.5 rounded text-xs bg-stone-700 text-stone-300">
                {message.metadata.toolName}
              </span>
            )}
          </div>
          <CodeBlock code={message.content} language="json" />
        </div>
      </div>
    );
  }
  
  return (
    <div
      className={cn(
        'group flex gap-3 px-4 md:px-6 py-4 transition-colors',
        isUser ? 'bg-transparent' : 'bg-stone-800/30',
        className
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center',
          isUser ? 'bg-forest' : 'bg-gradient-to-br from-purple-500 to-blue-500'
        )}
      >
        {isUser ? (
          <User className="w-5 h-5 text-white" />
        ) : (
          <Bot className="w-5 h-5 text-white" />
        )}
      </div>
      
      {/* Content */}
      <div className="flex-1 min-w-0 space-y-2">
        {/* Header */}
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">
            {isUser ? 'You' : 'SRE Assistant'}
          </span>
          <span className="text-xs text-stone-500">
            {formatRelativeTime(message.timestamp)}
          </span>
        </div>
        
        {/* Message content */}
        <div className="text-stone-300 leading-relaxed">
          {parsedContent.map((part, i) => (
            part.type === 'code' ? (
              <CodeBlock
                key={i}
                code={part.content}
                language={part.language}
                className="my-3"
              />
            ) : (
              <div key={i}>{renderMarkdownText(part.content)}</div>
            )
          ))}
        </div>
        
        {/* Tool output if present */}
        {message.metadata?.toolOutput && (
          <ToolOutput
            toolName={message.metadata.toolName || 'command'}
            output={message.metadata.toolOutput}
          />
        )}
        
        {/* Actions (only for assistant messages) */}
        {!isUser && (
          <div className="flex items-center gap-1 pt-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={handleCopy}
              className="p-1.5 text-stone-500 hover:text-stone-300 hover:bg-stone-700 rounded transition-colors"
              title="Copy message"
            >
              {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
            </button>
            
            <button
              onClick={() => setFeedback('up')}
              className={cn(
                'p-1.5 rounded transition-colors',
                feedback === 'up'
                  ? 'text-green-400 bg-green-500/10'
                  : 'text-stone-500 hover:text-stone-300 hover:bg-stone-700'
              )}
              title="Good response"
            >
              <ThumbsUp className="w-4 h-4" />
            </button>
            
            <button
              onClick={() => setFeedback('down')}
              className={cn(
                'p-1.5 rounded transition-colors',
                feedback === 'down'
                  ? 'text-red-400 bg-red-500/10'
                  : 'text-stone-500 hover:text-stone-300 hover:bg-stone-700'
              )}
              title="Bad response"
            >
              <ThumbsDown className="w-4 h-4" />
            </button>
            
            {isLast && onRetry && (
              <button
                onClick={onRetry}
                className="p-1.5 text-stone-500 hover:text-stone-300 hover:bg-stone-700 rounded transition-colors"
                title="Regenerate response"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Typing indicator for when AI is generating
export function TypingIndicator({ className }: { className?: string }) {
  return (
    <div className={cn('flex gap-3 px-4 md:px-6 py-4 bg-stone-800/30', className)}>
      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
        <Bot className="w-5 h-5 text-white" />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm font-medium text-white">SRE Assistant</span>
          <span className="text-xs text-stone-500">typing</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-stone-500 animate-bounce [animation-delay:-0.3s]" />
          <div className="w-2 h-2 rounded-full bg-stone-500 animate-bounce [animation-delay:-0.15s]" />
          <div className="w-2 h-2 rounded-full bg-stone-500 animate-bounce" />
        </div>
      </div>
    </div>
  );
}

// Investigation update message component
export function InvestigationUpdate({
  status,
  title,
  description,
  timestamp,
  className,
}: {
  status: 'running' | 'success' | 'pending';
  title: string;
  description?: string;
  timestamp?: string;
  className?: string;
}) {
  const icons = {
    running: <Clock className="w-4 h-4 text-blue-400 animate-pulse" />,
    success: <CheckCircle className="w-4 h-4 text-green-400" />,
    pending: <Clock className="w-4 h-4 text-yellow-400" />,
  };
  
  const colors = {
    running: 'border-blue-500/30 bg-blue-500/5',
    success: 'border-green-500/30 bg-green-500/5',
    pending: 'border-yellow-500/30 bg-yellow-500/5',
  };
  
  return (
    <div className={cn('flex gap-3 px-4 md:px-6 py-3', className)}>
      <div className="flex-shrink-0 w-8 flex justify-center pt-1">
        {icons[status]}
      </div>
      <div
        className={cn(
          'flex-1 p-3 rounded-lg border',
          colors[status]
        )}
      >
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-white">{title}</span>
          {timestamp && (
            <span className="text-xs text-stone-500">{formatRelativeTime(timestamp)}</span>
          )}
        </div>
        {description && (
          <p className="text-sm text-stone-400 mt-1">{description}</p>
        )}
      </div>
    </div>
  );
}
