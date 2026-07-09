/**
 * TopNav — 顶部主导航（替代原左侧 Sidebar）
 *
 * 设计要点：
 *  - 作为 QuantCell 插件运行时，左侧菜单由宿主提供，插件本身只显示顶部 Tab
 *  - 独立运行时，本组件就是页面顶栏
 */

import { NavLink } from 'react-router-dom';
import { useUiStore } from '@/stores/uiStore';
import styles from './TopNav.module.css';

const TABS = [
  { to: '/dashboard',   label: '总览',   icon: '📊' },
  { to: '/agents',      label: 'Agent', icon: '🤖' },
  { to: '/strategies',  label: '策略',   icon: '📈' },
  { to: '/backtests',   label: '回测',   icon: '🔬' },
  { to: '/trades',      label: '成交',   icon: '💹' },
  { to: '/risk',        label: '风控',   icon: '🛡️' },
  { to: '/reports',     label: '报告',   icon: '📝' },
  { to: '/chat',        label: 'AI 对话', icon: '💬' },
  { to: '/settings',    label: '设置',   icon: '⚙️' },
];

export function TopNav() {
  const wsConnected = useUiStore((s) => s.wsConnected);

  return (
    <header className={styles.topnav}>
      <div className={styles.brand}>
        <span className={styles.brandIcon}>▣</span>
        <div>
          <div className={styles.brandText}>QUANT OFFICE</div>
          <div className={styles.brandSub}>v0.2.2 · 量化交易指挥中枢</div>
        </div>
      </div>

      <nav className={styles.tabs}>
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) => `${styles.tab} ${isActive ? styles.active : ''}`}
          >
            <span className={styles.tabIcon}>{t.icon}</span>
            <span>{t.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className={styles.actions}>
        <div className={`${styles.indicator} ${wsConnected ? styles.online : styles.offline}`} title="WebSocket 状态">
          <span className={styles.indicatorDot} />
          {wsConnected ? 'ONLINE' : 'OFFLINE'}
        </div>
        <button className={styles.userBtn} title="用户">U</button>
      </div>
    </header>
  );
}
