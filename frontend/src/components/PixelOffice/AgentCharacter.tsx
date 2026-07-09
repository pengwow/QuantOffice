/**
 * AgentCharacter — 纯 CSS 像素角色
 *
 * 用 box-shadow + 多个伪元素拼出"16-bit"风格的小人，
 * 通过 CSS 变量（--uniform / --hat / --accent / --leg）区分 6 个角色。
 */

import { memo } from 'react';
import clsx from 'clsx';
import type { Agent, AgentRole } from '@/types';
import styles from './AgentCharacter.module.css';

interface Props {
  role: AgentRole;
  status: Agent['status'];
  size?: 'sm' | 'md' | 'lg';
  selected?: boolean;
  onClick?: () => void;
}

// 角色配色：uniform(躯干) / hat(头部装饰) / accent(配饰) / leg(裤子) / skin(肤色)
const PALETTE: Record<AgentRole, { uniform: string; hat: string; accent: string; leg: string; skin: string }> = {
  chief:     { uniform: '#2d3436', hat: '#00b894', accent: '#fdcb6e', leg: '#2d3436', skin: '#ffe0bd' },
  data:      { uniform: '#74b9ff', hat: '#0984e3', accent: '#ffffff', leg: '#2d3436', skin: '#ffe0bd' },
  strategy:  { uniform: '#e17055', hat: '#d63031', accent: '#ffffff', leg: '#2d3436', skin: '#ffe0bd' },
  risk:      { uniform: '#ff7675', hat: '#d63031', accent: '#ffffff', leg: '#2d3436', skin: '#ffe0bd' },
  execution: { uniform: '#a29bfe', hat: '#6c5ce7', accent: '#ffffff', leg: '#2d3436', skin: '#ffe0bd' },
  report:    { uniform: '#fdcb6e', hat: '#f39c12', accent: '#ffffff', leg: '#2d3436', skin: '#ffe0bd' },
};

const SIZE = { sm: 0.75, md: 1, lg: 1.5 } as const;

function AgentCharacterImpl({ role, status, size = 'md', selected, onClick }: Props) {
  const palette = PALETTE[role];
  const scale = SIZE[size];

  return (
    <div
      className={clsx(styles.character, status && styles[status], selected && styles.selected)}
      onClick={onClick}
      role="img"
      aria-label={`${role} agent, status: ${status}`}
      style={{
        transform: `scale(${scale})`,
        ['--uniform' as string]: palette.uniform,
        ['--hat' as string]: palette.hat,
        ['--accent' as string]: palette.accent,
        ['--leg' as string]: palette.leg,
        ['--skin' as string]: palette.skin,
      }}
    >
      <div className={styles.head}>
        <div className={styles.hat} />
      </div>
      <div className={styles.body}>
        <span className={clsx(styles.arm, styles.left)} />
        <span className={clsx(styles.arm, styles.right)} />
      </div>
      <div className={styles.legs} />
    </div>
  );
}

export const AgentCharacter = memo(AgentCharacterImpl);
