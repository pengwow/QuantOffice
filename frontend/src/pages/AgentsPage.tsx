/**
 * AgentsPage — Agent 列表 / 控制面板
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import { useAgentByRole } from '@/stores/agentStore';
import { useUiStore } from '@/stores/uiStore';
import { AGENT_META, AGENT_ROLES } from '@/lib/agentMeta';
import type { AgentRole } from '@/types';
import { AgentAvatar } from '@/components/AgentAvatar/AgentAvatar';
import styles from './Pages.module.css';

export function AgentsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['agents'], queryFn: api.listAgents, refetchInterval: 5_000 });
  const startMut = useMutation({ mutationFn: (id: string) => api.startAgent(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['agents'] }) });
  const stopMut  = useMutation({ mutationFn: (id: string) => api.stopAgent(id),  onSuccess: () => qc.invalidateQueries({ queryKey: ['agents'] }) });

  const selectAgent = useUiStore((s) => s.selectAgent);

  return (
    <div className={styles.scroll}>
      <div className={styles.pageHeader}>
        <div className={styles.pageTitle}>▣ Agent 面板</div>
        <div className={styles.pageSubtitle}>1 名首席交易员 + 5 名专业 Agent · 实时状态</div>
      </div>

      {isLoading && <div className={styles.empty}>加载中…</div>}

      <div className={styles.agentGrid}>
        {AGENT_ROLES.map((role) => (
          <AgentCard
            key={role}
            role={role}
            onStart={() => startMut.mutate(role)}
            onStop={() => stopMut.mutate(role)}
            onView={() => selectAgent(role)}
          />
        ))}
      </div>
    </div>
  );
}

function AgentCard({ role, onStart, onStop, onView }: { role: AgentRole; onStart: () => void; onStop: () => void; onView: () => void }) {
  const meta = AGENT_META[role];
  const live = useAgentByRole(role);
  const status = live?.status ?? 'idle';
  const task = live?.current_task;

  return (
    <div className={styles.agentCard} onClick={onView}>
      <div className={styles.agentCardHead}>
        <AgentAvatar role={role} status={status} size="sm" />
        <div>
          <div className={styles.agentCardName}>{meta.name}</div>
          <div className={styles.agentCardRole}>{role.toUpperCase()}</div>
        </div>
        <span className={`pixel-badge ${status}`}>{status}</span>
      </div>

      {task && <div style={{ fontSize: 11, color: 'var(--pixel-gray)', fontFamily: 'var(--font-mono)' }}>▸ {task}</div>}

      <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
        <button className="pixel-btn primary" style={{ flex: 1, padding: '4px 8px', fontSize: 9 }} onClick={(e) => { e.stopPropagation(); onStart(); }}>▶ 启动</button>
        <button className="pixel-btn danger"  style={{ flex: 1, padding: '4px 8px', fontSize: 9 }} onClick={(e) => { e.stopPropagation(); onStop();  }}>■ 停止</button>
      </div>
    </div>
  );
}
