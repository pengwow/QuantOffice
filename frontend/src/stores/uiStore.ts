/**
 * UI Store — 全局 UI 状态
 */

import { create } from 'zustand';

interface UiState {
  sidebarCollapsed: boolean;
  rightPanelOpen: boolean;
  selectedAgentRole: string | null;
  wsConnected: boolean;
  toggleSidebar: () => void;
  setRightPanel: (open: boolean) => void;
  selectAgent: (role: string | null) => void;
  setWsConnected: (v: boolean) => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  rightPanelOpen: true,
  selectedAgentRole: null,
  wsConnected: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setRightPanel: (open) => set({ rightPanelOpen: open }),
  selectAgent: (role) => set({ selectedAgentRole: role }),
  setWsConnected: (v) => set({ wsConnected: v }),
}));
