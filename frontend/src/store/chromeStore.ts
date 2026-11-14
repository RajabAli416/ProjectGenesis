import { useEffect } from 'react';
import { create } from 'zustand';

/**
 * Route-driven shell chrome. Sections declare what the header and status bar
 * should show for them; the shell reads it. Keeps the shell free of per-route
 * conditionals.
 */
interface ChromeState {
  detail: string | null;
  inspectorAvailable: boolean;
  statusLeft: string | null;
  statusRight: string | null;
  set: (patch: Partial<Omit<ChromeState, 'set'>>) => void;
}

export const useChromeStore = create<ChromeState>()((set) => ({
  detail: null,
  inspectorAvailable: false,
  statusLeft: null,
  statusRight: null,
  set: (patch) => set(patch),
}));

export function useChrome(opts: { detail?: string | null; inspectorAvailable?: boolean; statusLeft?: string | null; statusRight?: string | null }) {
  const set = useChromeStore((s) => s.set);
  const { detail = null, inspectorAvailable = false, statusLeft = null, statusRight = null } = opts;
  useEffect(() => {
    set({ detail, inspectorAvailable, statusLeft, statusRight });
    return () => set({ detail: null, inspectorAvailable: false, statusLeft: null, statusRight: null });
  }, [detail, inspectorAvailable, statusLeft, statusRight, set]);
}
