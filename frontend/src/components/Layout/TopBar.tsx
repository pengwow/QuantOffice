/**
 * TopBar — 顶部面包屑 + 关键指标
 */

import { useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import styles from './TopBar.module.css';

const TITLES: Record<string, string> = {
  '/':            '像素办公室',
  '/dashboard':   '总览仪表盘',
  '/agents':      'Agent 面板',
  '/strategies':  '策略管理',
  '/backtests':   '回测实验室',
  '/trades':      '成交记录',
  '/risk':        '风控监控',
  '/reports':     '报告中心',
};

export function TopBar() {
  const { pathname } = useLocation();
  const title = TITLES[pathname] ?? 'QuantOffice';
  const { data } = useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard });

  const dailyPnl = data?.daily_pnl ?? 0;
  const pnlUp = dailyPnl >= 0;

  return (
    <header className={styles.topbar}>
      <div className={styles.crumbs}>
        <span>QUANT OFFICE</span>
        <span>›</span>
        <strong>{title}</strong>
      </div>
      <div className={styles.actions}>
        <div className={styles.metric}>
          <span className={styles.metricLabel}>日盈亏</span>
          <span className={`${styles.metricValue} ${pnlUp ? styles.up : styles.down}`}>
            {pnlUp ? '+' : ''}{dailyPnl.toFixed(2)}
          </span>
        </div>
        <div className={styles.metric}>
          <span className={styles.metricLabel}>活跃策略</span>
          <span className={styles.metricValue}>{data?.active_strategies ?? 0}</span>
        </div>
        <div className={styles.metric}>
          <span className={styles.metricLabel}>夏普</span>
          <span className={styles.metricValue}>{(data?.sharpe ?? 0).toFixed(2)}</span>
        </div>
      </div>
    </header>
  );
}
