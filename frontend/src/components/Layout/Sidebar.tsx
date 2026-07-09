/**
 * Sidebar — 左侧导航
 */

import { NavLink } from 'react-router-dom';
import styles from './Sidebar.module.css';

const NAV_ITEMS = [
  { group: '概览', children: [
    { to: '/',              label: '像素办公室', icon: '🏢' },
    { to: '/dashboard',     label: '总览仪表盘', icon: '📊' },
  ]},
  { group: 'Agent', children: [
    { to: '/agents',        label: 'Agent 面板', icon: '🤖' },
  ]},
  { group: '交易', children: [
    { to: '/strategies',    label: '策略管理', icon: '📈' },
    { to: '/backtests',     label: '回测实验室', icon: '🔬' },
    { to: '/trades',        label: '成交记录', icon: '💹' },
  ]},
  { group: '风控 / 报告', children: [
    { to: '/risk',          label: '风控监控', icon: '🛡️' },
    { to: '/reports',       label: '报告中心', icon: '📝' },
  ]},
];

export function Sidebar() {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <h1>QUANT OFFICE</h1>
        <div className={styles.subtitle}>像素风格量化交易指挥中枢</div>
      </div>

      <div className={styles.searchBox}>
        <input className="pixel-input" placeholder="🔎 搜索策略 / 标的 / Agent" />
      </div>

      <nav className={styles.navSection}>
        {NAV_ITEMS.map((section) => (
          <div key={section.group}>
            <div className={styles.navTitle}>{section.group}</div>
            {section.children.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `${styles.navItem} ${isActive ? styles.active : ''}`
                }
              >
                <span className={styles.navIcon}>{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className={styles.footer}>
        v0.1.0 · MIT © 2026
      </div>
    </aside>
  );
}
