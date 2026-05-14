/**
 * Chat Types for AutoSRE V2
 */

export enum MessageRole {
  user = 'user',
  assistant = 'assistant',
  system = 'system',
}

export enum MessageStatus {
  pending = 'pending',
  streaming = 'streaming',
  completed = 'completed',
  error = 'error',
}

export enum ChatSessionStatus {
  active = 'active',
  archived = 'archived',
  deleted = 'deleted',
}

export interface MessageAttachment {
  id: string;
  type: 'image' | 'file' | 'code' | 'chart' | 'table';
  name: string;
  url?: string;
  content?: string;
  mimeType?: string;
  size?: number;
  metadata?: Record<string, unknown>;
}

export interface MessageToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  result?: unknown;
  status: 'pending' | 'running' | 'completed' | 'error';
  error?: string;
  duration?: number;
}

export interface MessageContext {
  alertId?: string;
  investigationId?: string;
  runbookId?: string;
  service?: string;
  timeRange?: {
    start: string;
    end: string;
  };
  metadata?: Record<string, unknown>;
}

export interface MessageFeedback {
  rating?: 'positive' | 'negative';
  comment?: string;
  categories?: string[];
  timestamp: string;
}

export interface Message {
  id: string;
  sessionId: string;
  role: MessageRole;
  content: string;
  status: MessageStatus;
  attachments?: MessageAttachment[];
  toolCalls?: MessageToolCall[];
  context?: MessageContext;
  feedback?: MessageFeedback;
  parentId?: string;
  replyTo?: string;
  tokens?: {
    input: number;
    output: number;
  };
  model?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ChatSession {
  id: string;
  title: string;
  status: ChatSessionStatus;
  messages: Message[];
  context?: MessageContext;
  systemPrompt?: string;
  model?: string;
  temperature?: number;
  maxTokens?: number;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  lastMessageAt?: string;
  messageCount: number;
  totalTokens?: {
    input: number;
    output: number;
  };
  tags?: string[];
  pinned?: boolean;
  metadata?: Record<string, unknown>;
}

export interface ChatSessionSummary {
  id: string;
  title: string;
  status: ChatSessionStatus;
  lastMessageAt?: string;
  messageCount: number;
  preview?: string;
  createdAt: string;
  tags?: string[];
  pinned?: boolean;
}

export interface ChatFilter {
  status?: ChatSessionStatus[];
  search?: string;
  tags?: string[];
  createdBy?: string;
  createdAfter?: string;
  createdBefore?: string;
  hasAlertContext?: boolean;
  hasInvestigationContext?: boolean;
  pinned?: boolean;
  limit?: number;
  offset?: number;
  sortBy?: 'createdAt' | 'updatedAt' | 'lastMessageAt' | 'title';
  sortOrder?: 'asc' | 'desc';
}

export interface SendMessageRequest {
  content: string;
  role?: MessageRole;
  attachments?: Omit<MessageAttachment, 'id'>[];
  context?: MessageContext;
  parentId?: string;
  replyTo?: string;
  stream?: boolean;
}

export interface CreateSessionRequest {
  title?: string;
  context?: MessageContext;
  systemPrompt?: string;
  model?: string;
  temperature?: number;
  maxTokens?: number;
  tags?: string[];
  initialMessage?: string;
}

export interface UpdateSessionRequest {
  title?: string;
  status?: ChatSessionStatus;
  systemPrompt?: string;
  model?: string;
  temperature?: number;
  maxTokens?: number;
  tags?: string[];
  pinned?: boolean;
}

export interface StreamingChunk {
  type: 'content' | 'tool_call_start' | 'tool_call_result' | 'done' | 'error';
  messageId: string;
  content?: string;
  toolCall?: Partial<MessageToolCall>;
  error?: string;
  tokens?: {
    input: number;
    output: number;
  };
}

export interface ChatStats {
  totalSessions: number;
  totalMessages: number;
  totalTokens: {
    input: number;
    output: number;
  };
  avgMessagesPerSession: number;
  avgTokensPerMessage: number;
  sessionsThisWeek: number;
}
