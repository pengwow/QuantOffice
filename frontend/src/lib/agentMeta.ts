/**
 * 6 个 Agent 的静态元数据 — 名称 / 颜色 / 工位位置 / 图标
 * 位置坐标对应仪表盘 Agent 看板内的工位布局
 */

import type { Agent } from '@/types';

export const AGENT_META: Record<
  Agent['role'],
  { name: string; emoji: string; color: string; position: { x: number; y: number } }
> = {
  chief:     { name: '首席交易员', emoji: '🎩', color: '#00b894', position: { x: 640, y: 360 } },
  data:      { name: '数据分析师', emoji: '📊', color: '#74b9ff', position: { x: 240, y: 360 } },
  strategy:  { name: '策略研究员', emoji: '📈', color: '#e17055', position: { x: 360, y: 520 } },
  risk:      { name: '风控官',     emoji: '🛡️', color: '#ff7675', position: { x: 920, y: 520 } },
  execution: { name: '执行交易员', emoji: '⚡', color: '#a29bfe', position: { x: 1040, y: 360 } },
  report:    { name: '报告专员',   emoji: '📝', color: '#fdcb6e', position: { x: 640, y: 600 } },
};

export const AGENT_ROLES: Agent['role'][] = [
  'chief',
  'data',
  'strategy',
  'risk',
  'execution',
  'report',
];

/** 把 Agent[] 转成按 role 索引的 Record */
export function indexByRole(agents: Agent[]): Partial<Record<Agent['role'], Agent>> {
  return agents.reduce((acc, a) => {
    acc[a.role] = a;
    return acc;
  }, {} as Partial<Record<Agent['role'], Agent>>);
}
