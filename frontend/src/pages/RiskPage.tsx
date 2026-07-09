/**
 * RiskPage — 风控监控
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import styles from './Pages.module.css';

export function RiskPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['alerts'], queryFn: api.listAlerts, refetchInterval: 5_000 });
  const ack = useMutation({ mutationFn: (id: string) => api.ackAlert(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }) });

  const colorOf = (level: string) => level === 'critical' ? styles.stopped : level === 'warning' ? styles.paused : styles.draft;

  return (
    <div className={styles.scroll}>
      <div className={styles.pageHeader}>
        <div className={styles.pageTitle}>▣ 风控监控</div>
        <div className={styles.pageSubtitle}>实时风控告警 · 5 秒刷新</div>
      </div>

      {isLoading && <div className={styles.empty}>加载中…</div>}

      {data && data.length === 0 && (
        <div className={styles.empty}>✅ 一切正常，暂无告警</div>
      )}

      {data && data.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>时间</th><th>级别</th><th>规则</th>
              <th>消息</th><th>指标</th><th>触发值</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            {data.map((a) => (
              <tr key={a.id}>
                <td style={{ fontSize: 11, color: 'var(--pixel-gray)' }}>{new Date(a.created_at).toLocaleString()}</td>
                <td><span className={`${styles.statusBadge} ${colorOf(a.level)}`}>{a.level.toUpperCase()}</span></td>
                <td><code>{a.rule}</code></td>
                <td>{a.message}</td>
                <td>
                  {a.metric ?? '-'} = {a.value ?? '-'} / 阈值 {a.threshold ?? '-'}
                </td>
                <td>
                  <button className="pixel-btn" style={{ padding: '4px 8px', fontSize: 9 }} onClick={() => ack.mutate(a.id)}>✓ 确认</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
