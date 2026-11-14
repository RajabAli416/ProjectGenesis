import { useEffect, useMemo, type ReactNode } from 'react';
import { usePolling, useReloadOnSignal, useUniverses } from '@/api/hooks';
import { env } from '@/api/env';
import { useUiStore } from '@/store/uiStore';
import { useConnectionStore } from '@/store/connectionStore';
import { UniverseCtx, type UniverseContextValue } from './universeContext';

/**
 * Loads the universe catalogue and exposes the operator's active universe.
 * Live clock updates from the WebSocket are merged in here so every section
 * reads a consistent view; `universe.changed` frames trigger a (throttled)
 * reload of the catalogue so new, paused or archived universes appear.
 */
export function UniverseProvider({ children }: { children: ReactNode }) {
  const resource = useUniverses();
  const activeId = useUiStore((s) => s.activeUniverseId);
  const setActive = useUiStore((s) => s.setActiveUniverse);
  const liveClocks = useConnectionStore((s) => s.clocks);
  const catalogRevision = useConnectionStore((s) => s.catalogRevision);
  useReloadOnSignal(resource.reload, catalogRevision, 1500);
  // Population and stage figures only travel over REST; refresh them slowly while an engine is attached.
  usePolling(resource.reload, env.dataSource === 'http' ? 5000 : 0);

  const universes = useMemo(() => {
    const list = resource.data ?? [];
    return list.map((u) => (liveClocks[u.id] ? { ...u, clock: liveClocks[u.id] } : u));
  }, [resource.data, liveClocks]);

  const byId = useMemo(() => new Map(universes.map((u) => [u.id, u])), [universes]);

  // Choose a sensible default once the catalogue arrives. This writes to an
  // external store (zustand), not React state, so it is a legitimate effect.
  // Only re-pick while the catalogue is settled: a just-created universe may be
  // selected before the refreshed list that contains it has arrived.
  useEffect(() => {
    if (resource.status !== 'ready' || !resource.data || resource.data.length === 0) return;
    if (activeId && byId.has(activeId)) return;
    const preferred = resource.data.find((u) => u.status === 'running') ?? resource.data[0];
    setActive(preferred.id);
  }, [resource.status, resource.data, activeId, byId, setActive]);

  const value = useMemo<UniverseContextValue>(
    () => ({ resource, universes, byId, active: activeId ? (byId.get(activeId) ?? null) : null, setActive }),
    [resource, universes, byId, activeId, setActive],
  );

  return <UniverseCtx.Provider value={value}>{children}</UniverseCtx.Provider>;
}
