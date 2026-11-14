import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UiState {
  railCollapsed: boolean;
  inspectorOpen: boolean;
  /** Universe currently in focus across sections. */
  activeUniverseId: string | null;

  toggleRail: () => void;
  setRailCollapsed: (v: boolean) => void;
  setInspectorOpen: (v: boolean) => void;
  toggleInspector: () => void;
  setActiveUniverse: (id: string | null) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      railCollapsed: false,
      inspectorOpen: true,
      activeUniverseId: null,

      toggleRail: () => set((s) => ({ railCollapsed: !s.railCollapsed })),
      setRailCollapsed: (v) => set({ railCollapsed: v }),
      setInspectorOpen: (v) => set({ inspectorOpen: v }),
      toggleInspector: () => set((s) => ({ inspectorOpen: !s.inspectorOpen })),
      setActiveUniverse: (id) => set({ activeUniverseId: id }),
    }),
    {
      name: 'recursion.ui',
      partialize: (s) => ({ railCollapsed: s.railCollapsed, inspectorOpen: s.inspectorOpen, activeUniverseId: s.activeUniverseId }),
    },
  ),
);
