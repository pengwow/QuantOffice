/**
 * WebSocket 客户端 — 自动重连 + 频道订阅
 *
 * 后端 FastAPI 暴露 /ws（standalone）或 /api/plugins/quant-office/ws（plugin）
 */

import { useEffect, useRef, useState } from 'react';
import type { WsEvent, WsEventType } from '@/types';

const PLUGIN_MODE = import.meta.env.VITE_PLUGIN_MODE === 'quantcell';
const WS_BASE = import.meta.env.VITE_WS_BASE ?? (PLUGIN_MODE ? '/api/plugins/quant-office' : '');

type Listener = (event: WsEvent) => void;

class WsBus {
  private ws: WebSocket | null = null;
  private listeners = new Set<Listener>();
  private retry = 0;
  private closed = false;
  private url: string;

  constructor() {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    this.url = `${proto}://${window.location.host}${WS_BASE}/ws`;
  }

  connect() {
    if (this.closed) return;
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    try {
      this.ws = new WebSocket(this.url);
    } catch (err) {
      console.error('[ws] failed to create', err);
      this.scheduleReconnect();
      return;
    }
    this.ws.onopen = () => {
      this.retry = 0;
      console.info('[ws] connected', this.url);
    };
    this.ws.onmessage = (e) => {
      try {
        const event: WsEvent = JSON.parse(e.data);
        this.listeners.forEach((fn) => fn(event));
      } catch (err) {
        console.warn('[ws] bad payload', err);
      }
    };
    this.ws.onclose = () => {
      this.scheduleReconnect();
    };
    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private scheduleReconnect() {
    if (this.closed) return;
    const delay = Math.min(15000, 500 * Math.pow(2, this.retry++));
    setTimeout(() => this.connect(), delay);
  }

  subscribe(fn: Listener) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  close() {
    this.closed = true;
    this.ws?.close();
    this.listeners.clear();
  }
}

export const wsBus = new WsBus();

/** 订阅指定类型事件的 React Hook */
export function useWsEvent<T = unknown>(type: WsEventType, handler: (data: T) => void) {
  const ref = useRef(handler);
  ref.current = handler;
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const off = wsBus.subscribe((event) => {
      if (event.type === type) ref.current(event.data as T);
    });
    return () => { off(); };
  }, [type]);

  useEffect(() => {
    wsBus.connect();
    const id = setInterval(() => setConnected(wsBus['ws']?.readyState === WebSocket.OPEN), 1000);
    return () => clearInterval(id);
  }, []);

  return connected;
}
