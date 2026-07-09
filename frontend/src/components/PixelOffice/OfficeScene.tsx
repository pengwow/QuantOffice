/**
 * OfficeScene — 像素办公室主场景
 *
 * 1280×720 等比缩放至容器大小，包含：
 *  - 棋盘格地板
 *  - 顶部 / 底部状态栏
 *  - 4 角盆栽、墙饰、大屏、机柜
 *  - 6 个 Agent 工位
 *  - 点击工位回调（用于右侧详情面板）
 */

import { useEffect, useState } from 'react';
import { useAllAgents } from '@/stores/agentStore';
import { useUiStore } from '@/stores/uiStore';
import { Workstation } from './Workstation';
import styles from './OfficeScene.module.css';

interface Props {
  onSelectAgent?: (role: string) => void;
}

const OFFICE_W = 1280;
const OFFICE_H = 720;

export function OfficeScene({ onSelectAgent }: Props) {
  const agents = useAllAgents();
  const selected = useUiStore((s) => s.selectedAgentRole);
  const wsConnected = useUiStore((s) => s.wsConnected);
  const selectAgent = useUiStore((s) => s.selectAgent);
  const [tick, setTick] = useState(0);
  const [scale, setScale] = useState(1);

  // 时钟（让电视文字动起来）
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  // 自适应缩放
  useEffect(() => {
    const handle = () => {
      const w = window.innerWidth - 240 - 320;  // 减去侧栏 + 右栏
      const h = window.innerHeight;
      setScale(Math.min(w / OFFICE_W, h / OFFICE_H, 1.2));
    };
    handle();
    window.addEventListener('resize', handle);
    return () => window.removeEventListener('resize', handle);
  }, []);

  const tvText = wsConnected
    ? `MARKET\n${tick % 2 ? '▲' : '▼'} LIVE`
    : 'OFFLINE';

  return (
    <div className={styles.office}>
      <div className={styles.floor} />

      {/* 顶部状态条 */}
      <div className={styles.header}>
        <div className={styles.headerTitle}>▣ QUANT OFFICE — TRADING FLOOR</div>
        <div className={styles.headerStatus}>
          <span className={`${styles.headerDot} ${wsConnected ? styles.online : styles.offline}`} />
          {wsConnected ? 'WS ONLINE' : 'WS OFFLINE'}
        </div>
      </div>

      {/* 墙饰 */}
      <div className={styles.wall}>
        <div className={styles.wallArt}>
          <div>K-LINE</div><div>VOL</div><div>SHARPE</div><div>DD</div>
        </div>
        <div className={styles.wallArt}>
          <div>BUY</div><div>SELL</div><div>HOLD</div>
        </div>
        <div className={styles.wallArt}>
          <div>{`T-${tick % 60}`}</div>
        </div>
      </div>

      {/* 中心圆桌 */}
      <div className={styles.centerRound} />

      {/* 大屏 */}
      <div className={styles.tv} data-text={tvText} />

      {/* 服务器机柜 */}
      <div className={styles.server} />

      {/* 盆栽 */}
      <div className={`${styles.plant} ${styles.tl}`}>
        <div className={styles.plantLeaf} />
        <div className={styles.plantPot} />
      </div>
      <div className={`${styles.plant} ${styles.tr}`}>
        <div className={styles.plantLeaf} />
        <div className={styles.plantPot} />
      </div>
      <div className={`${styles.plant} ${styles.bl}`}>
        <div className={styles.plantLeaf} />
        <div className={styles.plantPot} />
      </div>
      <div className={`${styles.plant} ${styles.br}`}>
        <div className={styles.plantLeaf} />
        <div className={styles.plantPot} />
      </div>

      {/* 工位层（缩放至容器） */}
      <div
        className={styles.workstationLayer}
        style={{
          transform: `scale(${scale})`,
          transformOrigin: 'center center',
          width: OFFICE_W,
          height: OFFICE_H,
          left: '50%',
          top: '50%',
          marginLeft: -OFFICE_W / 2,
          marginTop: -OFFICE_H / 2,
        }}
      >
        {Object.values(agents).map((a) => (
          <Workstation
            key={a.role}
            agent={a}
            selected={selected === a.role}
            onClick={() => {
              selectAgent(a.role);
              onSelectAgent?.(a.role);
            }}
          />
        ))}
      </div>

      {/* 底部工具栏 */}
      <div className={styles.toolbar}>
        <div>FPS: 60  ·  AGENTS: 6  ·  STATUS: {wsConnected ? '●' : '○'}</div>
        <div className={styles.toolbarButtons}>
          <button className={styles.toolbarBtn}>⟳ Refresh</button>
          <button className={styles.toolbarBtn}>▶ Run</button>
          <button className={styles.toolbarBtn}>■ Stop</button>
        </div>
      </div>
    </div>
  );
}
