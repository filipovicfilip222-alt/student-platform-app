/**
 * ui.ts — Client-only UI state (no server data).
 *
 * Currently just tracks the mobile sidebar toggle. Extend with theme / compact
 * mode / feature flags as needed. Do not put server state here — that belongs
 * in TanStack Query.
 */

import { create } from "zustand"

interface UiState {
  sidebarOpen: boolean

  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
}

export const useUiStore = create<UiState>((set) => ({
  sidebarOpen: false,

  toggleSidebar: () =>
    set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}))
