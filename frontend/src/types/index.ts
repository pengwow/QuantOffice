/**
 * QuantOffice 前端类型定义
 *
 * 与后端 FastAPI 响应字段保持一致（quant_office/api/*.py）。
 */

export type AgentRole =
  | 'chief'
  | 'data'
  | 'strategy'
  | 'risk'
  | 'execution'
  | 'report';

export type AgentStatus = 'idle' | 'busy' | 'success' | 'warning' | 'error';

export interface AgentMetrics {
  cpu_pct?: number;
  mem_mb?: number;
  tasks_done?: number;
  tasks_running?: number;
  last_latency_ms?: number;
  pnl_today?: number;
  sharpe?: number;
  drawdown?: number;
  [k: string]: number | string | undefined;
}

export interface Agent {
  id: string;
  role: AgentRole;
  name: string;
  emoji: string;
  status: AgentStatus;
  color: string;
  position: { x: number; y: number };  // 像素风办公室内的相对坐标
  metrics: AgentMetrics;
  current_task?: string;
  updated_at: string;
}

export interface Strategy {
  id: string;
  name: string;
  symbol: string;
  status: 'draft' | 'live' | 'paused' | 'stopped';
  params: Record<string, number | string | boolean>;
  pnl: number;
  sharpe: number;
  drawdown: number;
  created_at: string;
  updated_at: string;
}

export interface BacktestResult {
  id: string;
  strategy_id: string;
  period: { start: string; end: string };
  total_return: number;
  annual_return: number;
  sharpe: number;
  max_drawdown: number;
  win_rate: number;
  trades: number;
  equity_curve: { date: string; equity: number }[];
  created_at: string;
}

export interface Trade {
  id: string;
  strategy_id: string;
  symbol: string;
  side: 'buy' | 'sell';
  qty: number;
  price: number;
  pnl: number;
  status: 'pending' | 'filled' | 'rejected' | 'cancelled';
  created_at: string;
}

export interface RiskAlert {
  id: string;
  level: 'info' | 'warning' | 'critical';
  rule: string;
  message: string;
  symbol?: string;
  metric?: string;
  value?: number;
  threshold?: number;
  created_at: string;
}

export interface Report {
  id: string;
  title: string;
  period: { start: string; end: string };
  summary: string;
  sections: { title: string; body: string }[];
  created_at: string;
}

export interface DashboardSummary {
  total_pnl: number;
  daily_pnl: number;
  total_strategies: number;
  active_strategies: number;
  total_trades: number;
  win_rate: number;
  sharpe: number;
  drawdown: number;
  agents: Agent[];
  recent_alerts: RiskAlert[];
  equity_curve: { date: string; equity: number }[];
}

/* ============ WebSocket 事件 ============ */
export type WsEventType =
  | 'agent_status'
  | 'agent_metric'
  | 'trade'
  | 'risk_alert'
  | 'report_ready'
  | 'heartbeat';

export interface WsEvent<T = unknown> {
  type: WsEventType;
  ts: string;
  data: T;
}
