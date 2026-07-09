/**
 * TradesPage — 成交记录
 */

import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import styles from './Pages.module.css';

export function TradesPage() {
  const { data, isLoading } = useQuery({ queryKey: ['trades'], queryFn: () => api.listTrades({ limit: 200 }), refetchInterval: 5_000 });

  return (
    <div className={styles.scroll}>
      <div className={styles.pageHeader}>
        <div className={styles.pageTitle}>▣ 成交记录</div>
        <div className={styles.pageSubtitle}>最近 200 笔实盘成交 · 5 秒刷新</div>
      </div>

      {isLoading && <div className={styles.empty}>加载中…</div>}

      {data && data.length === 0 && (
        <div className={styles.empty}>暂无成交记录</div>
      )}

      {data && data.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>时间</th><th>标的</th><th>方向</th>
              <th style={{ textAlign: 'right' }}>数量</th>
              <th style={{ textAlign: 'right' }}>价格</th>
              <th style={{ textAlign: 'right' }}>P&amp;L</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {data.map((t) => (
              <tr key={t.id}>
                <td style={{ fontSize: 11, color: 'var(--pixel-gray)' }}>{new Date(t.created_at).toLocaleString()}</td>
                <td><code>{t.symbol}</code></td>
                <td><span className={`${styles.statusBadge} ${t.side === 'buy' ? styles.live : styles.stopped}`}>{t.side === 'buy' ? '▲ BUY' : '▼ SELL'}</span></td>
                <td style={{ textAlign: 'right' }}>{t.qty}</td>
                <td style={{ textAlign: 'right' }}>{t.price.toFixed(2)}</td>
                <td style={{ textAlign: 'right', color: t.pnl >= 0 ? 'var(--status-success)' : 'var(--status-error)' }}>
                  {t.pnl >= 0 ? '+' : ''}{t.pnl.toFixed(2)}
                </td>
                <td><span className={`${styles.statusBadge} ${styles[t.status] ?? ''}`}>{t.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
