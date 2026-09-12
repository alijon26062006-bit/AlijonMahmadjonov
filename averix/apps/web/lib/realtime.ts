'use client';

import { useEffect, useRef, useState } from 'react';
import type { Message } from './types';

export type RealtimeEvent = {
  type: 'message' | 'read' | 'conversation';
  conversation_id: string;
  message?: Message;
  user_id?: string;
  read_at?: string;
  unread_count?: number;
  sent_at: string;
};

/**
 * One socket per person, carrying events for every thread they are on.
 *
 * The socket is a live update, never the record: everything it delivers is
 * already in the database, so a dropped frame costs a refresh and nothing
 * else. Nothing is ever sent over it — every write goes through an ordinary
 * authenticated request.
 */
export function useRealtime(onEvent: (event: RealtimeEvent) => void) {
  const [connected, setConnected] = useState(false);
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    if (typeof window === 'undefined') return;

    let socket: WebSocket | null = null;
    let closed = false;
    let attempt = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    function connect() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/ws`);

      socket.onopen = () => {
        attempt = 0;
        setConnected(true);
      };

      socket.onmessage = (event) => {
        try {
          handler.current(JSON.parse(event.data) as RealtimeEvent);
        } catch {
          // A frame we cannot parse is not worth breaking the page over.
        }
      };

      socket.onclose = () => {
        setConnected(false);
        if (closed) return;
        // Backing off rather than hammering: a server that just restarted does
        // not need every open tab reconnecting at once.
        attempt += 1;
        const delay = Math.min(1000 * 2 ** attempt, 30000);
        timer = setTimeout(connect, delay + Math.random() * 500);
      };

      socket.onerror = () => socket?.close();
    }

    connect();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      socket?.close();
    };
  }, []);

  return { connected };
}
