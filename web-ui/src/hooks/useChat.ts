import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRef, useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';
import type { ChatMessage, ChatHistoryResponse, ChatRole } from '@/types';

// Chat session type (not in API types, managed client-side)
export interface ChatSession {
  id: string;
  title?: string;
  messages: ChatMessage[];
  createdAt: string;
  updatedAt: string;
  investigationId?: string;
}

// ==================== Types ====================
export interface SendMessageParams {
  sessionId: string;
  content: string;
  attachments?: File[];
}

export interface ChatStreamMessage {
  type: 'token' | 'tool_call' | 'tool_result' | 'done' | 'error';
  content?: string;
  toolName?: string;
  toolInput?: Record<string, unknown>;
  toolOutput?: string;
  error?: string;
  messageId?: string;
}

export interface UseChatOptions {
  sessionId: string;
  onMessage?: (message: ChatStreamMessage) => void;
  onError?: (error: Error) => void;
}

// ==================== Query Keys ====================
export const chatKeys = {
  all: ['chat'] as const,
  sessions: () => [...chatKeys.all, 'sessions'] as const,
  session: (id: string) => [...chatKeys.sessions(), id] as const,
  messages: (sessionId: string) => [...chatKeys.session(sessionId), 'messages'] as const,
};

// ==================== WebSocket State ====================
const WS_URL = (import.meta as { env: { VITE_WS_URL?: string } }).env?.VITE_WS_URL || 
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/chat/ws`;

// ==================== Queries ====================

/**
 * Fetch all chat sessions
 */
export function useChatSessions() {
  return useQuery({
    queryKey: chatKeys.sessions(),
    queryFn: async () => {
      // API returns chat history for sessions - adapt as needed
      const response = await api.get<{ sessions: ChatSession[] }>('/v1/chat/sessions');
      return response.sessions || [];
    },
    staleTime: 30000,
  });
}

/**
 * Fetch a single chat session with messages
 */
export function useChatSession(id: string) {
  return useQuery({
    queryKey: chatKeys.session(id),
    queryFn: async (): Promise<ChatSession> => {
      const response = await api.get<ChatHistoryResponse>(`/v1/chat/sessions/${id}`);
      return {
        id: response.sessionId,
        messages: response.messages,
        createdAt: response.messages[0]?.timestamp || new Date().toISOString(),
        updatedAt: response.messages[response.messages.length - 1]?.timestamp || new Date().toISOString(),
      };
    },
    enabled: !!id,
    staleTime: 5000,
  });
}

// ==================== Mutations ====================

/**
 * Create a new chat session
 */
export function useCreateChatSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params?: { title?: string; investigationId?: string }) =>
      api.post<ChatSession>('/v1/chat/sessions', params),
    
    onSuccess: (newSession) => {
      // Add to sessions list
      queryClient.setQueryData<ChatSession[]>(
        chatKeys.sessions(),
        (old) => old ? [newSession, ...old] : [newSession]
      );
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: chatKeys.sessions() });
    },
  });
}

/**
 * Delete a chat session
 */
export function useDeleteChatSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.delete(`/v1/chat/sessions/${id}`),
    
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: chatKeys.sessions() });
      
      const previousSessions = queryClient.getQueryData<ChatSession[]>(chatKeys.sessions());
      
      // Optimistically remove from list
      queryClient.setQueryData<ChatSession[]>(
        chatKeys.sessions(),
        (old) => old?.filter(s => s.id !== id)
      );

      return { previousSessions };
    },
    
    onError: (_err, _id, context) => {
      if (context?.previousSessions) {
        queryClient.setQueryData(chatKeys.sessions(), context.previousSessions);
      }
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: chatKeys.sessions() });
    },
  });
}

/**
 * Rename a chat session
 */
export function useRenameChatSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      api.patch<ChatSession>(`/v1/chat/sessions/${id}`, { title }),
    
    onMutate: async ({ id, title }) => {
      await queryClient.cancelQueries({ queryKey: chatKeys.session(id) });
      
      const previousSession = queryClient.getQueryData<ChatSession>(chatKeys.session(id));
      
      if (previousSession) {
        queryClient.setQueryData<ChatSession>(chatKeys.session(id), {
          ...previousSession,
          title,
          updatedAt: new Date().toISOString(),
        });
      }

      return { previousSession };
    },
    
    onError: (_err, { id }, context) => {
      if (context?.previousSession) {
        queryClient.setQueryData(chatKeys.session(id), context.previousSession);
      }
    },
    
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: chatKeys.sessions() });
    },
  });
}

/**
 * Send a message (non-streaming, for simple use cases)
 */
export function useSendMessage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ sessionId, content, attachments }: SendMessageParams) => {
      if (attachments?.length) {
        // Handle file uploads
        const formData = new FormData();
        formData.append('content', content);
        attachments.forEach(file => formData.append('attachments', file));
        
        const response = await fetch(`/api/v1/chat/sessions/${sessionId}/messages`, {
          method: 'POST',
          body: formData,
        });
        
        if (!response.ok) throw new Error('Failed to send message');
        return response.json() as Promise<ChatMessage>;
      }
      
      return api.post<ChatMessage>(`/v1/chat/sessions/${sessionId}/messages`, { content });
    },
    
    onMutate: async ({ sessionId, content }) => {
      await queryClient.cancelQueries({ queryKey: chatKeys.session(sessionId) });
      
      const previousSession = queryClient.getQueryData<ChatSession>(chatKeys.session(sessionId));
      
      // Optimistically add user message
      const optimisticMessage: ChatMessage = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content,
        timestamp: new Date().toISOString(),
      };
      
      if (previousSession) {
        queryClient.setQueryData<ChatSession>(chatKeys.session(sessionId), {
          ...previousSession,
          messages: [...previousSession.messages, optimisticMessage],
          updatedAt: new Date().toISOString(),
        });
      }

      return { previousSession };
    },
    
    onError: (_err, { sessionId }, context) => {
      if (context?.previousSession) {
        queryClient.setQueryData(chatKeys.session(sessionId), context.previousSession);
      }
    },
    
    onSettled: (_data, _err, { sessionId }) => {
      queryClient.invalidateQueries({ queryKey: chatKeys.session(sessionId) });
    },
  });
}

// ==================== WebSocket Hook ====================

/**
 * Real-time chat with WebSocket streaming
 * Handles connection management, message streaming, and auto-reconnection
 */
export function useChat({ sessionId, onMessage, onError }: UseChatOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | undefined>(undefined);
  const reconnectAttemptsRef = useRef(0);
  const queryClient = useQueryClient();
  
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    
    const ws = new WebSocket(`${WS_URL}?sessionId=${sessionId}`);
    
    ws.onopen = () => {
      setIsConnected(true);
      reconnectAttemptsRef.current = 0;
    };
    
    ws.onmessage = (event) => {
      try {
        const message: ChatStreamMessage = JSON.parse(event.data);
        
        switch (message.type) {
          case 'token':
            setStreamingContent(prev => prev + (message.content || ''));
            break;
            
          case 'tool_call':
          case 'tool_result':
            onMessage?.(message);
            break;
            
          case 'done':
            setIsStreaming(false);
            setStreamingContent('');
            // Invalidate to get final message
            queryClient.invalidateQueries({ queryKey: chatKeys.session(sessionId) });
            break;
            
          case 'error':
            setIsStreaming(false);
            setStreamingContent('');
            onError?.(new Error(message.error || 'Unknown error'));
            break;
        }
        
        onMessage?.(message);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };
    
    ws.onclose = () => {
      setIsConnected(false);
      setIsStreaming(false);
      
      // Exponential backoff reconnection
      const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
      reconnectAttemptsRef.current++;
      
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, delay);
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      onError?.(new Error('WebSocket connection error'));
    };
    
    wsRef.current = ws;
  }, [sessionId, onMessage, onError, queryClient]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    wsRef.current?.close();
    wsRef.current = null;
    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      onError?.(new Error('WebSocket not connected'));
      return;
    }
    
    // Add user message to cache immediately
    queryClient.setQueryData<ChatSession>(
      chatKeys.session(sessionId),
      (old: ChatSession | undefined) => {
        if (!old) return old;
        const userMessage: ChatMessage = {
          id: `temp-${Date.now()}`,
          role: 'user' as ChatRole,
          content,
          timestamp: new Date().toISOString(),
        };
        return {
          ...old,
          messages: [...old.messages, userMessage],
          updatedAt: new Date().toISOString(),
        };
      }
    );
    
    setIsStreaming(true);
    setStreamingContent('');
    
    wsRef.current.send(JSON.stringify({ type: 'message', content }));
  }, [sessionId, queryClient, onError]);

  const cancelStream = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'cancel' }));
    }
    setIsStreaming(false);
    setStreamingContent('');
  }, []);

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    isConnected,
    isStreaming,
    streamingContent,
    sendMessage,
    cancelStream,
    reconnect: connect,
  };
}

// ==================== SSE Streaming Alternative ====================

/**
 * Stream chat response using Server-Sent Events
 * Alternative to WebSocket for simpler use cases
 */
export function useChatSSE(sessionId: string) {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [error, setError] = useState<Error | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const queryClient = useQueryClient();

  const sendMessage = useCallback(async (content: string) => {
    // Cancel any existing stream
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    
    setIsStreaming(true);
    setStreamingContent('');
    setError(null);
    
    // Optimistically add user message
    queryClient.setQueryData<ChatSession>(
      chatKeys.session(sessionId),
      (old: ChatSession | undefined) => {
        if (!old) return old;
        const userMessage: ChatMessage = {
          id: `temp-${Date.now()}`,
          role: 'user' as ChatRole,
          content,
          timestamp: new Date().toISOString(),
        };
        return {
          ...old,
          messages: [...old.messages, userMessage],
        };
      }
    );
    
    try {
      const response = await fetch(`/api/v1/chat/sessions/${sessionId}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
        signal: abortControllerRef.current.signal,
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');
      
      const decoder = new TextDecoder();
      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              setIsStreaming(false);
              queryClient.invalidateQueries({ queryKey: chatKeys.session(sessionId) });
              return;
            }
            
            try {
              const parsed: ChatStreamMessage = JSON.parse(data);
              if (parsed.type === 'token' && parsed.content) {
                setStreamingContent(prev => prev + parsed.content);
              }
            } catch {
              // Ignore parse errors
            }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError(err as Error);
      }
    } finally {
      setIsStreaming(false);
    }
  }, [sessionId, queryClient]);

  const cancelStream = useCallback(() => {
    abortControllerRef.current?.abort();
    setIsStreaming(false);
    setStreamingContent('');
  }, []);

  return {
    isStreaming,
    streamingContent,
    error,
    sendMessage,
    cancelStream,
  };
}
