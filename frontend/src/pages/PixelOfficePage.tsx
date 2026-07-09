/**
 * PixelOfficePage — 路由 "/" — 像素办公室（核心场景）
 */

import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { OfficeScene } from '@/components/PixelOffice/OfficeScene';
import { api } from '@/api/client';
import { useAgentStore } from '@/stores/agentStore';
import { useWsEvent } from '@/api/ws';
import { useUiStore } from '@/stores/uiStore';
import type { Agent } from '@/types';

export function PixelOfficePage() {
  const setAll = useAgentStore((s) => s.setAll);
  const updateAgent = useAgentStore((s) => s.update);
  const setWsConnected = useUiStore((s) => s.setWsConnected);
  const wsConnected = useUiStore((s) => s.wsConnected);

  // 初始加载 + 轮询
  const { data } = useQuery({
    queryKey: ['agents'],
    queryFn: api.listAgents,
    refetchInterval: 10_000,
  });
  useEffect(() => { if (data) setAll(data); }, [data, setAll]);

  // WebSocket 实时推送
  useWsEvent<Partial<Agent> & { id: string }>('agent_status', (d) => {
    const role = d.id as Agent['role'];
    if (role) updateAgent(role, d as Partial<Agent>);
  });
  useWsEvent<{ id: string; key: string; value: number | string }>('agent_metric', (d) => {
    const role = d.id as Agent['role'];
    if (role) {
      const m = { [d.key]: d.value };
      useAgentStore.getState().update(role, { metrics: { ...useAgentStore.getState().agents[role].metrics, ...m } });
    }
  });
  useWsEvent('heartbeat', () => setWsConnected(true));

  // 简易连通性检测：每次 fetch 后标记
  useEffect(() => {
    if (data) setWsConnected(true);
  }, [data, setWsConnected]);

  return <OfficeScene />;
}
