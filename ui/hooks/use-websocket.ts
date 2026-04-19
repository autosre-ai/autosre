'use client';

import { useEffect, useRef, useCallback, useState } from 'react';

interface WebSocketMessage {
  type: string;
  payload: unknown;
}

interface UseWebSocketOptions {
  url: string;
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  reconnect?: boolean;
  reconnectInterval?: number;
}

export function useWebSocket({
  url,
  onMessage,
  onConnect,
  onDisconnect,
  reconnect = true,
  reconnectInterval = 3000,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = () => {
        setIsConnected(true);
        onConnect?.();
      };

      wsRef.current.onclose = () => {
        setIsConnected(false);
        onDisconnect?.();
        
        if (reconnect) {
          reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval);
        }
      };

      wsRef.current.onerror = () => {
        wsRef.current?.close();
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WebSocketMessage;
          onMessage?.(message);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };
    } catch (e) {
      console.error('Failed to create WebSocket:', e);
    }
  }, [url, onMessage, onConnect, onDisconnect, reconnect, reconnectInterval]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    wsRef.current?.close();
  }, []);

  const send = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { isConnected, send, connect, disconnect };
}

// Hook for real-time incident updates
export function useIncidentUpdates(onUpdate: (incident: unknown) => void) {
  const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';
  
  return useWebSocket({
    url: `${wsUrl}/incidents`,
    onMessage: (message) => {
      if (message.type === 'incident_update') {
        onUpdate(message.payload);
      }
    },
  });
}

// Hook for agent log streaming
export function useAgentLogs(agentId: string, onLog: (log: unknown) => void) {
  const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';
  
  return useWebSocket({
    url: `${wsUrl}/agents/${agentId}/logs`,
    onMessage: (message) => {
      if (message.type === 'log') {
        onLog(message.payload);
      }
    },
  });
}
