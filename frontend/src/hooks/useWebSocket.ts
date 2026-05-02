import { useEffect, useRef, useState, useCallback } from 'react';
import { createWebSocket } from '../api/client';
import type { WsMessage } from '../types';

type WsStatus = 'connecting' | 'connected' | 'disconnected';

export function useWebSocket(onMessage: (msg: WsMessage) => void) {
  const [status, setStatus] = useState<WsStatus>('connecting');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus('connecting');
    const ws = createWebSocket();
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      // Ping every 25s to keep alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, 25000);
      (ws as WebSocket & { _pingInterval?: ReturnType<typeof setInterval> })._pingInterval = pingInterval;
    };

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        onMessage(msg);
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setStatus('disconnected');
      const ws_ = ws as WebSocket & { _pingInterval?: ReturnType<typeof setInterval> };
      if (ws_._pingInterval) clearInterval(ws_._pingInterval);
      // Auto-reconnect after 3s
      reconnectTimeout.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [onMessage]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { status };
}
