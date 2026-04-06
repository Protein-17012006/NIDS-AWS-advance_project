import { useEffect, useRef, useState, useCallback } from 'react';
import { LivePredictionEvent } from '../types';

function getWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws/live`;
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<LivePredictionEvent | null>(null);
  const eventQueue = useRef<LivePredictionEvent[]>([]);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(getWsUrl());
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, 3000);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg && msg.type && msg.data && typeof msg.data === 'object') {
          const evt = msg as LivePredictionEvent;
          eventQueue.current.push(evt);
          setLastEvent(evt);
        }
      } catch { /* ignore malformed */ }
    };
  }, []);

  const drainEvents = useCallback((): LivePredictionEvent[] => {
    const events = eventQueue.current;
    eventQueue.current = [];
    return events;
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected, lastEvent, drainEvents };
}
