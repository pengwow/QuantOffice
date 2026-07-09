/**
 * ReportsPage — 报告中心
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/api/client';
import styles from './Pages.module.css';

export function ReportsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['reports'], queryFn: api.listReports, refetchInterval: 30_000 });
  const gen = useMutation({
    mutationFn: () => api.generateReport({
      start: new Date(Date.now() - 30 * 86400_000).toISOString().slice(0, 10),
      end:   new Date().toISOString().slice(0, 10),
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reports'] }),
  });

  const [openId, setOpenId] = useState<string | null>(null);
  const report = data?.find((r) => r.id === openId);

  return (
    <div className={styles.scroll}>
      <div className={styles.pageHeader}>
        <div className={styles.pageTitle}>▣ 报告中心</div>
        <div className={styles.pageSubtitle}>自动化报告生成与归档</div>
        <div style={{ marginTop: 12 }}>
          <button className="pixel-btn primary" disabled={gen.isPending} onClick={() => gen.mutate()}>
            {gen.isPending ? '生成中…' : '✚ 生成 30 天报告'}
          </button>
        </div>
      </div>

      {isLoading && <div className={styles.empty}>加载中…</div>}

      {data && data.length === 0 && (
        <div className={styles.empty}>暂无报告，点击上方按钮生成</div>
      )}

      {data && data.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
          {data.map((r) => (
            <div key={r.id} className={styles.agentCard} onClick={() => setOpenId(r.id)}>
              <div style={{ fontFamily: 'var(--font-pixel)', fontSize: 11, color: 'var(--pixel-dark)' }}>📝 {r.title}</div>
              <div style={{ fontSize: 10, color: 'var(--pixel-gray)' }}>{r.period.start} → {r.period.end}</div>
              <div style={{ fontSize: 12, marginTop: 6 }}>{r.summary.slice(0, 80)}{r.summary.length > 80 ? '…' : ''}</div>
              <div style={{ fontSize: 10, color: 'var(--pixel-gray)', marginTop: 8 }}>{new Date(r.created_at).toLocaleString()}</div>
            </div>
          ))}
        </div>
      )}

      {report && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          }}
          onClick={() => setOpenId(null)}
        >
          <div className={styles.chartCard} style={{ maxWidth: 720, width: '90%', maxHeight: '80vh', overflow: 'auto' }} onClick={(e) => e.stopPropagation()}>
            <div className={styles.chartTitle}>📝 {report.title}</div>
            <p style={{ marginBottom: 12, fontSize: 12, color: 'var(--pixel-gray)' }}>{report.period.start} → {report.period.end}</p>
            <p style={{ marginBottom: 16 }}>{report.summary}</p>
            {report.sections.map((s, i) => (
              <div key={i} style={{ marginBottom: 12 }}>
                <h3 style={{ fontFamily: 'var(--font-pixel)', fontSize: 11, marginBottom: 4 }}>{s.title}</h3>
                <p style={{ fontSize: 13, lineHeight: 1.6 }}>{s.body}</p>
              </div>
            ))}
            <button className="pixel-btn" onClick={() => setOpenId(null)}>关闭</button>
          </div>
        </div>
      )}
    </div>
  );
}
