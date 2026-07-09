/**
 * DashboardPage — 总览仪表盘
 */

import { useQuery } from '@tanstack/react-query';
import ReactECharts from 'echarts-for-react';
import { api } from '@/api/client';
import styles from './Pages.module.css';

export function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: api.dashboard,
    refetchInterval: 5_000,
  });

  if (isLoading || !data) {
    return <div className={styles.empty}>加载中…</div>;
  }

  const equityOption = {
    grid: { left: 40, right: 16, top: 16, bottom: 24 },
    xAxis: { type: 'category', data: data.equity_curve.map((p) => p.date), axisLine: { lineStyle: { color: '#2d3436' } } },
    yAxis: { type: 'value', axisLine: { lineStyle: { color: '#2d3436' } }, splitLine: { lineStyle: { color: '#dfe6e9' } } },
    series: [{
      type: 'line',
      data: data.equity_curve.map((p) => p.equity),
      smooth: false,
      symbol: 'none',
      lineStyle: { width: 2, color: '#00b894' },
      areaStyle: { color: 'rgba(0, 184, 148, 0.15)' },
    }],
  };

  return (
    <div className={styles.scroll}>
      <div className={styles.pageHeader}>
        <div className={styles.pageTitle}>▣ 总览仪表盘</div>
        <div className={styles.pageSubtitle}>实时关键指标 · 每 5 秒自动刷新</div>
      </div>

      <div className={styles.kpiGrid}>
        <Kpi label="总盈亏" value={data.total_pnl} suffix="" />
        <Kpi label="日盈亏" value={data.daily_pnl} suffix="" signed />
        <Kpi label="活跃策略" value={data.active_strategies} suffix={`/ ${data.total_strategies}`} />
        <Kpi label="总成交" value={data.total_trades} />
        <Kpi label="胜率" value={(data.win_rate * 100).toFixed(1)} suffix="%" />
        <Kpi label="夏普" value={data.sharpe.toFixed(2)} />
        <Kpi label="最大回撤" value={(data.drawdown * 100).toFixed(2)} suffix="%" negative />
      </div>

      <div className={styles.charts}>
        <div className={styles.chartCard}>
          <div className={styles.chartTitle}>▣ 净值曲线</div>
          <ReactECharts option={equityOption} style={{ height: 280 }} />
        </div>
        <div className={styles.chartCard}>
          <div className={styles.chartTitle}>▣ Agent 状态</div>
          <AgentStatusChart agents={data.agents} />
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, suffix = '', signed, negative }: {
  label: string; value: number | string; suffix?: string; signed?: boolean; negative?: boolean;
}) {
  const num = typeof value === 'number' ? value : parseFloat(value);
  const isUp = signed ? num >= 0 : !negative;
  const display = typeof value === 'number'
    ? `${signed && num >= 0 ? '+' : ''}${num.toFixed(2)}`
    : value;
  return (
    <div className={styles.kpi}>
      <div className={styles.kpiLabel}>{label}</div>
      <div className={`${styles.kpiValue} ${negative ? styles.down : isUp && signed ? styles.up : ''}`}>
        {display}{suffix}
      </div>
    </div>
  );
}

function AgentStatusChart({ agents }: { agents: { role: string; status: string }[] }) {
  const counts: Record<string, number> = { idle: 0, busy: 0, success: 0, warning: 0, error: 0 };
  agents.forEach((a) => { counts[a.status] = (counts[a.status] ?? 0) + 1; });
  const option = {
    grid: { left: 40, right: 16, top: 16, bottom: 24 },
    xAxis: { type: 'category', data: Object.keys(counts) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      type: 'bar',
      data: Object.values(counts).map((v, i) => ({
        value: v,
        itemStyle: {
          color: ['#b2bec3', '#74b9ff', '#00b894', '#fdcb6e', '#ff7675'][i],
          borderColor: '#2d3436',
          borderWidth: 2,
        },
      })),
      barWidth: '60%',
    }],
  };
  return <ReactECharts option={option} style={{ height: 280 }} />;
}
