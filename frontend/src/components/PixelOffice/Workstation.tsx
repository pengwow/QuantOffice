/**
 * Workstation — 单个工位（角色 + 办公桌 + 电脑 + 状态徽章 + 名牌）
 */

import { memo } from 'react';
import clsx from 'clsx';
import type { Agent, AgentStatus } from '@/types';
import { AgentCharacter } from './AgentCharacter';
import styles from './Workstation.module.css';

interface Props {
  agent: Agent;
  selected?: boolean;
  onClick?: () => void;
}

const STATUS_EMOJI: Record<AgentStatus, string> = {
  idle: '💤',
  busy: '⚙️',
  success: '✅',
  warning: '⚠️',
  error: '🚨',
};

function WorkstationImpl({ agent, selected, onClick }: Props) {
  const { position, name, color, status, current_task } = agent;
  return (
    <div
      className={clsx(styles.workstation, selected && styles.selected)}
      style={{ left: position.x, top: position.y }}
      onClick={onClick}
      role="button"
      tabIndex={0}
    >
      {current_task && status === 'busy' && (
        <div className={styles.taskBubble}>{current_task}</div>
      )}

      <div className={styles.characterWrap}>
        <div className={styles.statusBadge} title={status}>
          {STATUS_EMOJI[status]}
        </div>
        <AgentCharacter role={agent.role} status={status} size="md" selected={selected} />
      </div>

      <div className={styles.desk} style={{ ['--screen' as string]: color }} />
      <div className={styles.nameplate}>{name}</div>
    </div>
  );
}

export const Workstation = memo(WorkstationImpl);
