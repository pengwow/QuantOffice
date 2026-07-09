/**
 * App 根组件 — 路由 + 布局
 */

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect } from 'react';
import { Sidebar } from '@/components/Layout/Sidebar';
import { TopBar } from '@/components/Layout/TopBar';
import { RightPanel } from '@/components/Layout/RightPanel';
import { useAgentStore } from '@/stores/agentStore';
import { useUiStore } from '@/stores/uiStore';
import { wsBus } from '@/api/ws';
import { PixelOfficePage } from '@/pages/PixelOfficePage';
import { DashboardPage } from '@/pages/DashboardPage';
import { AgentsPage } from '@/pages/AgentsPage';
import { StrategiesPage } from '@/pages/StrategiesPage';
import { BacktestsPage } from '@/pages/BacktestsPage';
import { TradesPage } from '@/pages/TradesPage';
import { RiskPage } from '@/pages/RiskPage';
import { ReportsPage } from '@/pages/ReportsPage';

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
    <div className="flex" style={{ height: '100vh', width: '100vw' }}>
      <Sidebar />
      <div className="flex flex-col flex-1" style={{ minWidth: 0 }}>
        <TopBar />
        <Routes>
          <Route path="/" element={<PixelOfficePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/strategies" element={<StrategiesPage />} />
          <Route path="/backtests" element={<BacktestsPage />} />
          <Route path="/trades" element={<TradesPage />} />
          <Route path="/risk" element={<RiskPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      <RightPanel />
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
