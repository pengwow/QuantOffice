/**
 * Agent Store — 6 个 Agent 的实时状态
 *
 * 初始数据来自 GET /api/agents（轮询或 React Query）；
 * 后续增量由 WebSocket 事件 agent_status / agent_metric 推送。
 */

import { create } from 'zustand';
import type { Agent, AgentRole, AgentStatus } from '@/types';
import { AGENT_META, AGENT_ROLES } from '@/lib/agentMeta';

interface AgentState {
  agents: Record<AgentRole, Agent>;
  setAll: (agents: Agent[]) => void;
  update: (role: AgentRole, patch: Partial<Agent>) => void;
  setStatus: (role: AgentRole, status: AgentStatus, currentTask?: string) => void;
  setMetric: (role: AgentRole, key: string, value: number | string) => void;
  reset: () => void;
}

function makeFallback(): Record<AgentRole, Agent> {
  const now = new Date().toISOString();
  return AGENT_ROLES.reduce((acc, role) => {
    const meta = AGENT_META[role];
    acc[role] = {
      id: role,
      role,
      name: meta.name,
      emoji: meta.emoji,
      color: meta.color,
      position: meta.position,
      status: 'idle',
      metrics: {},
      updated_at: now,
    };
    return acc;
  }, {} as Record<AgentRole, Agent>);
}

export const useAgentStore = create<AgentState>((set) => ({
  agents: makeFallback(),

  setAll: (agents) =>
    set((s) => {
      const next = { ...s.agents };
      for (const a of agents) {
        const merged: Agent = { ...next[a.role], ...a, position: next[a.role]?.position ?? a.position };
        next[a.role] = merged;
      }
      return { agents: next };
    }),

  update: (role, patch) =>
    set((s) => ({
      agents: {
        ...s.agents,
        [role]: { ...s.agents[role], ...patch, updated_at: new Date().toISOString() },
      },
    })),

  setStatus: (role, status, currentTask) =>
    set((s) => ({
      agents: {
        ...s.agents,
        [role]: { ...s.agents[role], status, current_task: currentTask, updated_at: new Date().toISOString() },
      },
    })),

  setMetric: (role, key, value) =>
    set((s) => ({
      agents: {
        ...s.agents,
        [role]: {
          ...s.agents[role],
          metrics: { ...s.agents[role].metrics, [key]: value },
          updated_at: new Date().toISOString(),
        },
      },
    })),

  reset: () => set({ agents: makeFallback() }),
}));

/* 便捷 selector */
export const useAgentByRole = (role: AgentRole) =>
  useAgentStore((s) => s.agents[role]);

export const useAllAgents = () =>
  useAgentStore((s) => s.agents);
