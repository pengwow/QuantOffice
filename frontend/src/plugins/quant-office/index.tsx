/**
 * QuantOffice — QuantCell 插件入口
 *
 * 加载策略（与之前的 placeholder 行为兼容）：
 *  1. 宿主通过 dynamic import 加载本文件
 *  2. 宿主从 default export 拿到 QuantOfficeApp 组件，挂到 <Route path="/plugins/quant-office/*" />
 *  3. 宿主调用 registerMenu() / registerRoutes() 注入导航
 *
 * 同时支持直接以独立 SPA 模式启动（作为 window.QuantOfficePlugin 暴露）。
 */

import { lazy, Suspense, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AGENT_META, AGENT_ROLES } from '@/lib/agentMeta';
import { useAgentStore } from '@/stores/agentStore';

const DashboardPage = lazy(() => import('@/pages/DashboardPage').then((m) => ({ default: m.DashboardPage })));
const AgentsPage     = lazy(() => import('@/pages/AgentsPage').then((m) => ({ default: m.AgentsPage })));
const StrategiesPage = lazy(() => import('@/pages/StrategiesPage').then((m) => ({ default: m.StrategiesPage })));
const BacktestsPage  = lazy(() => import('@/pages/BacktestsPage').then((m) => ({ default: m.BacktestsPage })));
const TradesPage     = lazy(() => import('@/pages/TradesPage').then((m) => ({ default: m.TradesPage })));
const RiskPage       = lazy(() => import('@/pages/RiskPage').then((m) => ({ default: m.RiskPage })));
const ReportsPage    = lazy(() => import('@/pages/ReportsPage').then((m) => ({ default: m.ReportsPage })));
const PixelOfficePage = lazy(() => import('@/pages/PixelOfficePage').then((m) => ({ default: m.PixelOfficePage })));

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 2_000, refetchOnWindowFocus: false } },
});

function PluginShell() {
  useEffect(() => {
    useAgentStore.getState().reset();
  }, []);
  return (
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<div style={{ padding: 16 }}>加载中…</div>}>
        <Routes>
          <Route index element={<PixelOfficePage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="agents" element={<AgentsPage />} />
          <Route path="strategies" element={<StrategiesPage />} />
          <Route path="backtests" element={<BacktestsPage />} />
          <Route path="trades" element={<TradesPage />} />
          <Route path="risk" element={<RiskPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="*" element={<Navigate to="." replace />} />
        </Routes>
      </Suspense>
    </QueryClientProvider>
  );
}

export default PluginShell;

/* ============================================================
 * QuantCell 宿主侧 API（占位协议，宿主应替换为真实实现）
 * ============================================================ */

const PLUGIN_NAME = 'quant-office';

const pluginRegistry = (typeof window !== 'undefined' && (window as any).pluginRegistry) || {
  registerMenu: (m: unknown) => console.info('[quant-office] registerMenu', m),
  registerRoute: (r: unknown) => console.info('[quant-office] registerRoute', r),
  registerAsset: (a: unknown) => console.info('[quant-office] registerAsset', a),
  mount: (el: HTMLElement) => {
    console.info('[quant-office] mount into', el);
  },
};

// 注册菜单
pluginRegistry.registerMenu({
  key: PLUGIN_NAME,
  label: 'QuantOffice',
  icon: '🏢',
  pluginName: PLUGIN_NAME,
  children: AGENT_ROLES.map((r) => ({
    key: r,
    label: AGENT_META[r].name,
    icon: AGENT_META[r].emoji,
  })),
});

// 注册路由（默认入口）
pluginRegistry.registerRoute({
  path: `/plugins/${PLUGIN_NAME}/*`,
  element: PluginShell,
  pluginName: PLUGIN_NAME,
});

/* 暴露给宿主 */
if (typeof window !== 'undefined') {
  (window as any).QuantOfficePlugin = {
    name: PLUGIN_NAME,
    App: PluginShell,
    routes: AGENT_ROLES,
  };
}

export { PluginShell as QuantOfficeApp };
