/**
 * AutoSRE V2 - Chat API Service
 * 
 * API service for chat functionality including REST endpoints
 * and WebSocket real-time streaming.
 */

import api, { tokenManager } from './api';
import type { AxiosResponse } from 'axios';
import type {
  ChatSession,
  ChatSessionSummary,
  ChatFilter,
  Message,
  SendMessageRequest,
  CreateSessionRequest,
  UpdateSessionRequest,
  StreamingChunk,
  ChatStats,
  MessageFeedback,
  PaginatedResponse,
  ApiResponse,
} from '../types';

// Response types
export type ChatSessionsListResponse = ApiResponse<PaginatedResponse<ChatSessionSummary>>;
export type ChatSessionResponse = ApiResponse<ChatSession>;
export type MessagesResponse = ApiResponse<Message[]>;
export type MessageResponse = ApiResponse<Message>;
export type ChatStatsResponse = ApiResponse<ChatStats>;

// WebSocket configuration
const WS_BASE_URL = import.meta.env.VITE_WS_URL || 
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/ws`;

/**
 * WebSocket connection manager for chat streaming
 */
export class ChatWebSocket {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private sessionId: string | null = null;
  private messageHandlers: Set<(chunk: StreamingChunk) => void> = new Set();
  private errorHandlers: Set<(error: Error) => void> = new Set();
  private connectionHandlers: Set<(connected: boolean) => void> = new Set();

  /**
   * Connect to the chat WebSocket
   */
  connect(sessionId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        if (this.sessionId === sessionId) {
          resolve();
          return;
        }
        this.disconnect();
      }

      this.sessionId = sessionId;
      const token = tokenManager.getAccessToken();
      const url = `${WS_BASE_URL}/chat/${sessionId}?token=${token}`;

      try {
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
          this.reconnectAttempts = 0;
          this.notifyConnectionChange(true);
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const chunk: StreamingChunk = JSON.parse(event.data);
            this.notifyMessage(chunk);
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };

        this.ws.onerror = (event) => {
          const error = new Error('WebSocket error');
          this.notifyError(error);
          reject(error);
        };

        this.ws.onclose = (event) => {
          this.notifyConnectionChange(false);
          
          // Attempt reconnection if not intentionally closed
          if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => {
              if (this.sessionId) {
                this.connect(this.sessionId).catch(console.error);
              }
            }, this.reconnectDelay * this.reconnectAttempts);
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * Disconnect from the WebSocket
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
      this.sessionId = null;
      this.reconnectAttempts = this.maxReconnectAttempts; // Prevent reconnection
    }
  }

  /**
   * Send a message through WebSocket (for streaming)
   */
  sendMessage(content: string, options?: Partial<SendMessageRequest>): void {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not connected');
    }

    this.ws.send(
      JSON.stringify({
        type: 'message',
        content,
        ...options,
      })
    );
  }

  /**
   * Cancel the current streaming response
   */
  cancelStream(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'cancel' }));
    }
  }

  /**
   * Subscribe to message chunks
   */
  onMessage(handler: (chunk: StreamingChunk) => void): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  /**
   * Subscribe to errors
   */
  onError(handler: (error: Error) => void): () => void {
    this.errorHandlers.add(handler);
    return () => this.errorHandlers.delete(handler);
  }

  /**
   * Subscribe to connection state changes
   */
  onConnectionChange(handler: (connected: boolean) => void): () => void {
    this.connectionHandlers.add(handler);
    return () => this.connectionHandlers.delete(handler);
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private notifyMessage(chunk: StreamingChunk): void {
    this.messageHandlers.forEach((handler) => handler(chunk));
  }

  private notifyError(error: Error): void {
    this.errorHandlers.forEach((handler) => handler(error));
  }

  private notifyConnectionChange(connected: boolean): void {
    this.connectionHandlers.forEach((handler) => handler(connected));
  }
}

// Singleton WebSocket instance
export const chatWebSocket = new ChatWebSocket();

/**
 * Chat API service (REST endpoints)
 */
export const chatApi = {
  // Session management

  /**
   * List chat sessions
   */
  listSessions: (
    params?: ChatFilter
  ): Promise<AxiosResponse<ChatSessionsListResponse>> => {
    return api.get('/chat/sessions', { params });
  },

  /**
   * Get a single chat session with messages
   */
  getSession: (id: string): Promise<AxiosResponse<ChatSessionResponse>> => {
    return api.get(`/chat/sessions/${id}`);
  },

  /**
   * Create a new chat session
   */
  createSession: (
    data?: CreateSessionRequest
  ): Promise<AxiosResponse<ChatSessionResponse>> => {
    return api.post('/chat/sessions', data);
  },

  /**
   * Update a chat session
   */
  updateSession: (
    id: string,
    data: UpdateSessionRequest
  ): Promise<AxiosResponse<ChatSessionResponse>> => {
    return api.patch(`/chat/sessions/${id}`, data);
  },

  /**
   * Delete a chat session
   */
  deleteSession: (id: string): Promise<AxiosResponse<ApiResponse<void>>> => {
    return api.delete(`/chat/sessions/${id}`);
  },

  /**
   * Archive a chat session
   */
  archiveSession: (id: string): Promise<AxiosResponse<ChatSessionResponse>> => {
    return api.post(`/chat/sessions/${id}/archive`);
  },

  /**
   * Pin/unpin a chat session
   */
  pinSession: (
    id: string,
    pinned: boolean
  ): Promise<AxiosResponse<ChatSessionResponse>> => {
    return api.patch(`/chat/sessions/${id}`, { pinned });
  },

  // Message operations

  /**
   * Get messages for a session
   */
  getMessages: (
    sessionId: string,
    params?: { limit?: number; before?: string; after?: string }
  ): Promise<AxiosResponse<MessagesResponse>> => {
    return api.get(`/chat/sessions/${sessionId}/messages`, { params });
  },

  /**
   * Send a message (non-streaming)
   */
  sendMessage: (
    sessionId: string,
    data: SendMessageRequest
  ): Promise<AxiosResponse<MessageResponse>> => {
    return api.post(`/chat/sessions/${sessionId}/messages`, {
      ...data,
      stream: false,
    });
  },

  /**
   * Send a message with streaming (initiates stream, returns message ID)
   * Use ChatWebSocket for receiving the stream
   */
  sendMessageStreaming: (
    sessionId: string,
    data: Omit<SendMessageRequest, 'stream'>
  ): Promise<AxiosResponse<ApiResponse<{ messageId: string }>>> => {
    return api.post(`/chat/sessions/${sessionId}/messages`, {
      ...data,
      stream: true,
    });
  },

  /**
   * Regenerate the last assistant message
   */
  regenerateMessage: (
    sessionId: string,
    messageId: string
  ): Promise<AxiosResponse<MessageResponse>> => {
    return api.post(`/chat/sessions/${sessionId}/messages/${messageId}/regenerate`);
  },

  /**
   * Edit a user message and regenerate response
   */
  editMessage: (
    sessionId: string,
    messageId: string,
    content: string
  ): Promise<AxiosResponse<MessageResponse>> => {
    return api.put(`/chat/sessions/${sessionId}/messages/${messageId}`, {
      content,
    });
  },

  /**
   * Delete a message
   */
  deleteMessage: (
    sessionId: string,
    messageId: string
  ): Promise<AxiosResponse<ApiResponse<void>>> => {
    return api.delete(`/chat/sessions/${sessionId}/messages/${messageId}`);
  },

  /**
   * Submit feedback for a message
   */
  submitFeedback: (
    sessionId: string,
    messageId: string,
    feedback: MessageFeedback
  ): Promise<AxiosResponse<MessageResponse>> => {
    return api.post(
      `/chat/sessions/${sessionId}/messages/${messageId}/feedback`,
      feedback
    );
  },

  // Context operations

  /**
   * Update session context (e.g., link to alert/investigation)
   */
  updateContext: (
    sessionId: string,
    context: ChatSession['context']
  ): Promise<AxiosResponse<ChatSessionResponse>> => {
    return api.patch(`/chat/sessions/${sessionId}/context`, context);
  },

  /**
   * Create a session with alert context
   */
  createFromAlert: (
    alertId: string,
    initialMessage?: string
  ): Promise<AxiosResponse<ChatSessionResponse>> => {
    return api.post('/chat/sessions', {
      context: { alertId },
      initialMessage,
    });
  },

  /**
   * Create a session with investigation context
   */
  createFromInvestigation: (
    investigationId: string,
    initialMessage?: string
  ): Promise<AxiosResponse<ChatSessionResponse>> => {
    return api.post('/chat/sessions', {
      context: { investigationId },
      initialMessage,
    });
  },

  // Statistics

  /**
   * Get chat usage statistics
   */
  getStats: (params?: {
    timeRange?: 'day' | 'week' | 'month' | 'all';
  }): Promise<AxiosResponse<ChatStatsResponse>> => {
    return api.get('/chat/stats', { params });
  },

  // Search

  /**
   * Search across chat sessions and messages
   */
  search: (
    query: string,
    params?: { limit?: number; sessionId?: string }
  ): Promise<
    AxiosResponse<
      ApiResponse<{
        sessions: ChatSessionSummary[];
        messages: Array<Message & { sessionTitle: string }>;
      }>
    >
  > => {
    return api.get('/chat/search', { params: { query, ...params } });
  },

  // Bulk operations

  /**
   * Delete multiple sessions
   */
  bulkDelete: (
    sessionIds: string[]
  ): Promise<AxiosResponse<ApiResponse<{ deleted: number }>>> => {
    return api.post('/chat/sessions/bulk/delete', { sessionIds });
  },

  /**
   * Archive multiple sessions
   */
  bulkArchive: (
    sessionIds: string[]
  ): Promise<AxiosResponse<ApiResponse<{ archived: number }>>> => {
    return api.post('/chat/sessions/bulk/archive', { sessionIds });
  },

  // Export

  /**
   * Export a chat session
   */
  exportSession: (
    sessionId: string,
    format: 'json' | 'markdown' | 'txt'
  ): Promise<AxiosResponse<Blob>> => {
    return api.get(`/chat/sessions/${sessionId}/export`, {
      params: { format },
      responseType: 'blob',
    });
  },
};

export default chatApi;
