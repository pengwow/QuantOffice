/**
 * App 根组件 — 路由 + 布局
 *
 * 布局（v0.2.3 起）：
 *  - 顶部 TopNav（导航，作为插件时由宿主提供菜单，组件本身仍渲染）
 *  - 顶部 TopBar（面包屑 + 关键指标）
 *  - 中间内容区
 *  - 右侧 RightPanel（Agent 详情 / 告警）
 *
 * 注意：之前是左侧 Sidebar，作为 QuantCell 插件时与宿主菜单冲突，
 *       已改为顶部 Tab。详见 docs/QuantOffice_Plugin_Architecture.md。
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect } from 'react';
import { TopNav } from '@/components/Layout/TopNav';
import { TopBar } from '@/components/Layout/TopBar';
import { RightPanel } from '@/components/Layout/RightPanel';
import { useAgentStore } from '@/stores/agentStore';
import { useUiStore } from '@/stores/uiStore';
import { wsBus } from '@/api/ws';
import { DashboardPage } from '@/pages/DashboardPage';
import { AgentsPage } from '@/pages/AgentsPage';
import { StrategiesPage } from '@/pages/StrategiesPage';
import { BacktestsPage } from '@/pages/BacktestsPage';
import { TradesPage } from '@/pages/TradesPage';
import { RiskPage } from '@/pages/RiskPage';
import { ReportsPage } from '@/pages/ReportsPage';
import { ChatPage } from '@/pages/ChatPage';
import { SettingsPage } from '@/pages/SettingsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 2_000,
      refetchOnWindowFocus: false,
    },
  },
});

function Shell() {
  return (
    <div className="flex flex-col" style={{ height: '100vh', width: '100vw' }}>
      <TopNav />
      <div className="flex flex-col flex-1" style={{ minWidth: 0, minHeight: 0 }}>
        <TopBar />
        <div className="flex flex-1" style={{ minHeight: 0 }}>
          <div className="flex-1" style={{ overflow: 'auto', minWidth: 0 }}>
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/agents" element={<AgentsPage />} />
              <Route path="/strategies" element={<StrategiesPage />} />
              <Route path="/backtests" element={<BacktestsPage />} />
              <Route path="/trades" element={<TradesPage />} />
              <Route path="/risk" element={<RiskPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/chat" element={<ChatPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </div>
          <RightPanel />
        </div>
      </div>
    </div>
  );
}

export function App() {
  useEffect(() => {
    wsBus.connect();
    return () => wsBus.close();
  }, []);

  // 预热 Agent store（fallback 数据）
  useEffect(() => {
    useAgentStore.getState().reset();
    useUiStore.getState().setWsConnected(false);
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Shell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
