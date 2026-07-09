/**
 * RightPanel — 右侧 Agent 详情面板
 *
 * 显示当前选中 Agent 的指标 / 当前任务 / 控制按钮。
 * 未选中时显示全局告警简报。
 */

import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { useAgentByRole } from '@/stores/agentStore';
import { useUiStore } from '@/stores/uiStore';
import type { AgentRole } from '@/types';
import styles from './RightPanel.module.css';

const ROLE_LABEL: Record<AgentRole, string> = {
  chief: '首席交易员',
  data: '数据分析师',
  strategy: '策略研究员',
  risk: '风控官',
  execution: '执行交易员',
  report: '报告专员',
};

export function RightPanel() {
  const selected = useUiStore((s) => s.selectedAgentRole);
  const selectAgent = useUiStore((s) => s.selectAgent);
  const agent = useAgentByRole((selected as AgentRole) ?? 'chief');

  const { data: alerts } = useQuery({
    queryKey: ['alerts'],
    queryFn: api.listAlerts,
    refetchInterval: 10_000,
  });

  if (!selected || !agent) {
    return (
      <aside className={styles.panel}>
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>👈</div>
          <div>点击工位上的<br />Agent 查看详情</div>
        </div>
        {alerts && alerts.length > 0 && (
          <div className={styles.content}>
            <div className={styles.section}>
              <div className={styles.sectionTitle}>最近告警</div>
              {alerts.slice(0, 5).map((a) => (
                <div key={a.id} className={styles.taskBox} style={{ marginBottom: 6 }}>
                  <div style={{ fontWeight: 700 }}>
                    [{a.level.toUpperCase()}] {a.rule}
                  </div>
                  <div style={{ color: 'var(--pixel-gray)' }}>{a.message}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>
    );
  }

  const metrics = agent.metrics ?? {};
  const pnlToday = Number(metrics.pnl_today ?? 0);
  const sharpe = Number(metrics.sharpe ?? 0);
  const drawdown = Number(metrics.drawdown ?? 0);

  return (
    <aside className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.headerEmoji}>{agent.emoji}</div>
        <div className={styles.headerName}>{ROLE_LABEL[agent.role]}</div>
        <button
          className={styles.headerClose}
          onClick={() => selectAgent(null)}
          title="关闭"
          aria-label="关闭"
        >×</button>
      </div>

      <div className={styles.content}>
        <div className={styles.section}>
          <div className={styles.sectionTitle}>基础</div>
          <div className={styles.metricRow}>
            <span className="k">状态</span>
            <span className={`pixel-badge ${agent.status}`}>{agent.status}</span>
          </div>
          <div className={styles.metricRow}>
            <span className="k">ID</span>
            <span className="v">{agent.id}</span>
          </div>
          <div className={styles.metricRow}>
            <span className="k">更新</span>
            <span className="v">{new Date(agent.updated_at).toLocaleTimeString()}</span>
          </div>
        </div>

        {agent.current_task && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>当前任务</div>
            <div className={styles.taskBox}>▸ {agent.current_task}</div>
          </div>
        )}

        <div className={styles.section}>
          <div className={styles.sectionTitle}>指标</div>
          {Object.entries(metrics).map(([k, v]) => (
            <div key={k} className={styles.metricRow}>
              <span className="k">{k}</span>
              <span className="v">{String(v)}</span>
            </div>
          ))}
          {Object.keys(metrics).length === 0 && (
            <div style={{ color: 'var(--pixel-gray)', fontSize: 12 }}>暂无数据</div>
          )}
        </div>

        {agent.role !== 'chief' && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>关键指标</div>
            <div className={styles.metricRow}>
              <span className="k">P&L 当日</span>
              <span className={`v ${pnlToday >= 0 ? 'up' : 'down'}`}>
                {pnlToday >= 0 ? '+' : ''}{pnlToday.toFixed(2)}
              </span>
            </div>
            <div className={styles.metricRow}>
              <span className="k">Sharpe</span>
              <span className="v">{sharpe.toFixed(2)}</span>
            </div>
            <div className={styles.metricRow}>
              <span className="k">Drawdown</span>
              <span className="v down">{(drawdown * 100).toFixed(2)}%</span>
            </div>
          </div>
        )}

        <div className={styles.section}>
          <div className={styles.sectionTitle}>控制</div>
          <div className={styles.actionRow}>
            <button className="pixel-btn primary" style={{ flex: 1 }}>▶ 启动</button>
            <button className="pixel-btn danger" style={{ flex: 1 }}>■ 停止</button>
          </div>
        </div>
      </div>
    </aside>
  );
}
