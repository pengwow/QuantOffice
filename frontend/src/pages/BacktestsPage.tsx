/**
 * BacktestsPage — 回测实验室
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/api/client';
import styles from './Pages.module.css';

export function BacktestsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['backtests'], queryFn: api.listBacktests, refetchInterval: 10_000 });
  const run = useMutation({
    mutationFn: (params: { strategy_id: string; start: string; end: string }) => api.runBacktest(params.strategy_id, { start: params.start, end: params.end }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['backtests'] }),
  });

  const [strategyId, setStrategyId] = useState('demo-strategy-1');
  const [start, setStart] = useState('2025-01-01');
  const [end, setEnd] = useState('2025-12-31');

  return (
    <div className={styles.scroll}>
      <div className={styles.pageHeader}>
        <div className={styles.pageTitle}>▣ 回测实验室</div>
        <div className={styles.pageSubtitle}>运行历史回测并查看绩效指标</div>
      </div>

      <div className={styles.chartCard} style={{ marginBottom: 24 }}>
        <div className={styles.chartTitle}>新建回测</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: 12, alignItems: 'end' }}>
          <div>
            <label style={{ fontSize: 10, color: 'var(--pixel-gray)' }}>策略 ID</label>
            <input className="pixel-input" value={strategyId} onChange={(e) => setStrategyId(e.target.value)} />
          </div>
          <div>
            <label style={{ fontSize: 10, color: 'var(--pixel-gray)' }}>开始</label>
            <input className="pixel-input" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div>
            <label style={{ fontSize: 10, color: 'var(--pixel-gray)' }}>结束</label>
            <input className="pixel-input" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
          <button
            className="pixel-btn primary"
            disabled={run.isPending}
            onClick={() => run.mutate({ strategy_id: strategyId, start, end })}
          >
            {run.isPending ? '运行中…' : '▶ 启动回测'}
          </button>
        </div>
        {run.isError && (
          <div style={{ marginTop: 8, color: 'var(--status-error)', fontSize: 12 }}>
            回测启动失败：{String((run.error as Error).message ?? run.error)}
          </div>
        )}
      </div>

      {isLoading && <div className={styles.empty}>加载中…</div>}

      {data && data.length === 0 && (
        <div className={styles.empty}>暂无回测记录</div>
      )}

      {data && data.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>ID</th><th>策略</th>
              <th style={{ textAlign: 'right' }}>总收益</th>
              <th style={{ textAlign: 'right' }}>年化</th>
              <th style={{ textAlign: 'right' }}>夏普</th>
              <th style={{ textAlign: 'right' }}>最大回撤</th>
              <th style={{ textAlign: 'right' }}>胜率</th>
              <th style={{ textAlign: 'right' }}>成交数</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            {data.map((b) => (
              <tr key={b.id}>
                <td><code>{b.id.slice(0, 8)}</code></td>
                <td><code>{b.strategy_id.slice(0, 12)}</code></td>
                <td style={{ textAlign: 'right', color: b.total_return >= 0 ? 'var(--status-success)' : 'var(--status-error)' }}>
                  {(b.total_return * 100).toFixed(1)}%
                </td>
                <td style={{ textAlign: 'right' }}>{(b.annual_return * 100).toFixed(1)}%</td>
                <td style={{ textAlign: 'right' }}>{b.sharpe.toFixed(2)}</td>
                <td style={{ textAlign: 'right', color: 'var(--status-error)' }}>{(b.max_drawdown * 100).toFixed(1)}%</td>
                <td style={{ textAlign: 'right' }}>{(b.win_rate * 100).toFixed(1)}%</td>
                <td style={{ textAlign: 'right' }}>{b.trades}</td>
                <td style={{ fontSize: 11, color: 'var(--pixel-gray)' }}>{new Date(b.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
