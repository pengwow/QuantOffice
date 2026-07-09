/**
 * StrategiesPage — 策略管理
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/api/client';
import type { Strategy } from '@/types';
import styles from './Pages.module.css';

export function StrategiesPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['strategies'], queryFn: api.listStrategies, refetchInterval: 10_000 });
  const toggle = useMutation({
    mutationFn: (s: Strategy) => api.updateStrategy(s.id, { status: s.status === 'live' ? 'paused' : 'live' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  });
  const del = useMutation({
    mutationFn: (id: string) => api.deleteStrategy(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategies'] }),
  });

  return (
    <div className={styles.scroll}>
      <div className={styles.pageHeader}>
        <div className={styles.pageTitle}>▣ 策略管理</div>
        <div className={styles.pageSubtitle}>查看 / 启停 / 删除量化策略</div>
      </div>

      {isLoading && <div className={styles.empty}>加载中…</div>}

      {data && data.length === 0 && (
        <div className={styles.empty}>暂无策略，请通过后端 API 创建</div>
      )}

      {data && data.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>名称</th><th>标的</th><th>状态</th>
              <th style={{ textAlign: 'right' }}>P&amp;L</th>
              <th style={{ textAlign: 'right' }}>夏普</th>
              <th style={{ textAlign: 'right' }}>回撤</th>
              <th>更新</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {data.map((s) => (
              <tr key={s.id}>
                <td><strong>{s.name}</strong></td>
                <td><code>{s.symbol}</code></td>
                <td><span className={`${styles.statusBadge} ${styles[s.status]}`}>{s.status}</span></td>
                <td style={{ textAlign: 'right', color: s.pnl >= 0 ? 'var(--status-success)' : 'var(--status-error)' }}>
                  {s.pnl >= 0 ? '+' : ''}{s.pnl.toFixed(2)}
                </td>
                <td style={{ textAlign: 'right' }}>{s.sharpe.toFixed(2)}</td>
                <td style={{ textAlign: 'right', color: 'var(--status-error)' }}>{(s.drawdown * 100).toFixed(1)}%</td>
                <td style={{ fontSize: 11, color: 'var(--pixel-gray)' }}>{new Date(s.updated_at).toLocaleString()}</td>
                <td>
                  <button className="pixel-btn" style={{ padding: '4px 8px', fontSize: 9, marginRight: 4 }} onClick={() => toggle.mutate(s)}>
                    {s.status === 'live' ? '⏸ 暂停' : '▶ 启动'}
                  </button>
                  <button className="pixel-btn danger" style={{ padding: '4px 8px', fontSize: 9 }} onClick={() => del.mutate(s.id)}>🗑</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
