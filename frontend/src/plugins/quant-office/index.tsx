/**
 * QuantOffice 前端插件入口（QuantCell 模式）。
 *
 * 当作为独立应用运行时，main.tsx 直接渲染；当作为 QuantCell 插件时，
 * 由宿主加载此文件并调用 registerPlugin() 注册菜单 / 路由 / 资源。
 */

import { pluginRegistry } from '@/plugins';

const API_PREFIX =
  (import.meta as any).env?.VITE_PLUGIN_MODE === 'quantcell'
    ? '/api/plugins/quant-office'
    : '/api';

export { API_PREFIX };

// 注册菜单
pluginRegistry.registerMenu({
  key: 'quant-office',
  label: 'QuantOffice',
  icon: '🏢',
  pluginName: 'quant-office',
  children: [
    { key: 'pixel-office', label: '像素办公室', icon: '🖥️' },
    { key: 'agent-dashboard', label: 'Agent 面板', icon: '🤖' },
    { key: 'strategy-manager', label: '策略管理', icon: '📈' },
    { key: 'risk-monitor', label: '风控监控', icon: '🛡️' },
    { key: 'backtest-lab', label: '回测实验室', icon: '🔬' },
  ],
});

// 注册路由（占位，宿主应替换为真实组件）
pluginRegistry.registerRoute({
  path: '/plugins/quant-office',
  element: { type: 'div', props: { children: 'Pixel Office — 见 src/components' } } as any,
  pluginName: 'quant-office',
});

// Godot WASM 资源
pluginRegistry.registerAsset({
  pluginName: 'quant-office',
  js: `${API_PREFIX}/assets/godot/quant_office.js`,
  wasm: `${API_PREFIX}/assets/godot/quant_office.wasm`,
  pck: `${API_PREFIX}/assets/godot/quant_office.pck`,
});
