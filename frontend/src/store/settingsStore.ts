import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { OperatorSettings, PerformanceConfig, PersistenceConfig, ProviderConfig, ReasoningConfig, SimulationParams } from '@/domain';

/**
 * Local draft of operator settings. Edits are held here until a backend is
 * connected and they can be submitted; nothing in this store drives behaviour
 * of the interface beyond the Settings forms themselves.
 */
interface SettingsStore {
  draft: OperatorSettings | null;
  dirty: boolean;

  hydrate: (settings: OperatorSettings) => void;
  /** Adopt settings the backend has just persisted: becomes the new baseline, clears dirty. */
  adopt: (settings: OperatorSettings) => void;
  reset: () => void;
  updateProvider: (id: string, patch: Partial<ProviderConfig>) => void;
  addProvider: () => void;
  removeProvider: (id: string) => void;
  updateReasoning: (patch: Partial<ReasoningConfig>) => void;
  updateSimulation: (patch: Partial<SimulationParams>) => void;
  updatePerformance: (patch: Partial<PerformanceConfig>) => void;
  updatePersistence: (patch: Partial<PersistenceConfig>) => void;
}

let baseline: OperatorSettings | null = null;

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      draft: null,
      dirty: false,

      hydrate: (settings) =>
        set((s) => {
          baseline = settings;
          // Keep a persisted dirty draft; otherwise adopt the loaded settings.
          return s.draft && s.dirty ? {} : { draft: settings, dirty: false };
        }),
      adopt: (settings) => {
        baseline = settings;
        set({ draft: settings, dirty: false });
      },
      reset: () => set({ draft: baseline, dirty: false }),

      updateProvider: (id, patch) =>
        set((s) =>
          s.draft ? { dirty: true, draft: { ...s.draft, providers: s.draft.providers.map((p) => (p.id === id ? { ...p, ...patch } : p)) } } : {},
        ),
      addProvider: () =>
        set((s) =>
          s.draft
            ? {
                dirty: true,
                draft: {
                  ...s.draft,
                  providers: [
                    ...s.draft.providers,
                    { id: `p-${Date.now().toString(36)}`, label: 'New provider', adapter: 'openai-compatible', baseUrl: '', model: '', hasCredential: false, enabled: false },
                  ],
                },
              }
            : {},
        ),
      removeProvider: (id) =>
        set((s) => (s.draft ? { dirty: true, draft: { ...s.draft, providers: s.draft.providers.filter((p) => p.id !== id) } } : {})),
      updateReasoning: (patch) => set((s) => (s.draft ? { dirty: true, draft: { ...s.draft, reasoning: { ...s.draft.reasoning, ...patch } } } : {})),
      updateSimulation: (patch) => set((s) => (s.draft ? { dirty: true, draft: { ...s.draft, simulation: { ...s.draft.simulation, ...patch } } } : {})),
      updatePerformance: (patch) => set((s) => (s.draft ? { dirty: true, draft: { ...s.draft, performance: { ...s.draft.performance, ...patch } } } : {})),
      updatePersistence: (patch) => set((s) => (s.draft ? { dirty: true, draft: { ...s.draft, persistence: { ...s.draft.persistence, ...patch } } } : {})),
    }),
    { name: 'recursion.settings-draft', partialize: (s) => ({ draft: s.draft, dirty: s.dirty }) },
  ),
);
