import { create } from 'zustand';
import type { CameraState, ViewportTool } from '@/viewport/types';

interface SelectionState {
  /** Entity selected in the viewport (agent, structure, resource, portal). */
  selectedEntityId: string | null;
  /** Agent selected in the Agents explorer. */
  selectedAgentId: string | null;
  tool: ViewportTool;
  /** Last camera reported by the stage; persisted per universe in memory only. */
  cameras: Record<string, CameraState>;

  selectEntity: (id: string | null) => void;
  selectAgent: (id: string | null) => void;
  setTool: (tool: ViewportTool) => void;
  rememberCamera: (universeId: string, camera: CameraState) => void;
}

export const useSelectionStore = create<SelectionState>()((set) => ({
  selectedEntityId: null,
  selectedAgentId: null,
  tool: 'select',
  cameras: {},

  selectEntity: (id) => set({ selectedEntityId: id }),
  selectAgent: (id) => set({ selectedAgentId: id }),
  setTool: (tool) => set({ tool }),
  rememberCamera: (universeId, camera) => set((s) => ({ cameras: { ...s.cameras, [universeId]: camera } })),
}));
