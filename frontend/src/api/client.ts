/**
 * REST API 客户端
 *
 * - standalone 模式: /api/*
 * - quantcell 模式: /api/plugins/quant-office/*
 *
 * baseURL 在 Vite 代理下指向相对路径，无需后端 CORS 配置。
 */

import type {
  Agent,
  BacktestResult,
  DashboardSummary,
  Report,
  RiskAlert,
  Strategy,
  Trade,
} from '@/types';

const PLUGIN_MODE = import.meta.env.VITE_PLUGIN_MODE === 'quantcell';
const API_BASE = import.meta.env.VITE_API_BASE ?? (PLUGIN_MODE ? '/api/plugins/quant-office' : '/api');

class ApiError extends Error {
  constructor(public status: number, public body: unknown, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    let body: unknown = null;
    try { body = await res.json(); } catch { /* ignore */ }
    throw new ApiError(res.status, body, `${init?.method ?? 'GET'} ${url} -> ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // ----- 概览 -----
  dashboard: () => request<DashboardSummary>('/dashboard'),

  // ----- Agents -----
  listAgents:   () => request<Agent[]>('/agents'),
  getAgent:     (id: string) => request<Agent>(`/agents/${id}`),
  startAgent:   (id: string) => request<Agent>(`/agents/${id}/start`, { method: 'POST' }),
  stopAgent:    (id: string) => request<Agent>(`/agents/${id}/stop`,  { method: 'POST' }),

  // ----- 策略 -----
  listStrategies:   () => request<Strategy[]>('/strategies'),
  getStrategy:      (id: string) => request<Strategy>(`/strategies/${id}`),
  createStrategy:   (body: Partial<Strategy>) =>
    request<Strategy>('/strategies', { method: 'POST', body: JSON.stringify(body) }),
  updateStrategy:   (id: string, body: Partial<Strategy>) =>
    request<Strategy>(`/strategies/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteStrategy:   (id: string) =>
    request<void>(`/strategies/${id}`, { method: 'DELETE' }),

  // ----- 回测 -----
  listBacktests:    () => request<BacktestResult[]>('/backtests'),
  runBacktest:      (strategyId: string, params: { start: string; end: string }) =>
    request<BacktestResult>('/backtests', {
      method: 'POST',
      body: JSON.stringify({ strategy_id: strategyId, ...params }),
    }),

  // ----- 交易 -----
  listTrades:       (params?: { limit?: number; symbol?: string }) => {
    const qs = new URLSearchParams();
    if (params?.limit)  qs.set('limit',  String(params.limit));
    if (params?.symbol) qs.set('symbol', params.symbol);
    return request<Trade[]>(`/trades${qs.toString() ? `?${qs}` : ''}`);
  },
  submitTrade:      (body: { strategy_id: string; symbol: string; side: 'buy' | 'sell'; qty: number; price?: number }) =>
    request<Trade>('/trades', { method: 'POST', body: JSON.stringify(body) }),

  // ----- 风控 -----
  listAlerts:       () => request<RiskAlert[]>('/risk/alerts'),
  ackAlert:         (id: string) =>
    request<RiskAlert>(`/risk/alerts/${id}/ack`, { method: 'POST' }),

  // ----- 报告 -----
  listReports:      () => request<Report[]>('/reports'),
  generateReport:   (period: { start: string; end: string }) =>
    request<Report>('/reports', { method: 'POST', body: JSON.stringify(period) }),

  // ----- 健康检查 -----
  health: () => request<{ status: string; ts: string }>('/health'),

  // ----- 设置 -----
  listLlmPresets:    () => request<Array<{ key: string; label: string; base_url: string; default_model: string }>>('/settings/llm-presets'),
  listExchangePresets: () => request<Array<{ key: string; label: string; base_url: string; testnet_base_url: string }>>('/settings/exchange-presets'),
  getLlm:            () => request<Record<string, unknown>>('/settings/llm'),
  updateLlm:         (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/settings/llm', { method: 'PUT', body: JSON.stringify(body) }),
  testLlm:           () => request<Record<string, unknown>>('/settings/llm/test', { method: 'POST' }),
  getExchange:       () => request<Record<string, unknown>>('/settings/exchange'),
  updateExchange:    (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/settings/exchange', { method: 'PUT', body: JSON.stringify(body) }),
  testExchange:      () => request<Record<string, unknown>>('/settings/exchange/test', { method: 'POST' }),
  getRisk:           () => request<Record<string, unknown>>('/settings/risk'),
  updateRisk:        (body: Record<string, unknown>) =>
    request<Record<string, unknown>>('/settings/risk', { method: 'PUT', body: JSON.stringify(body) }),
  settingsSnapshot:  () => request<Record<string, unknown>>('/settings/snapshot'),

  // ----- Chat -----
  chatStatus:        () => request<Record<string, unknown>>('/chat/status'),
};

export { ApiError };
