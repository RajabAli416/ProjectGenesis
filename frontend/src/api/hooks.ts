import { useCallback, useEffect, useRef, useState } from 'react';
import type { Agent, BenchmarkRecord, Civilization, DecisionRecord, Experiment, HostStatus, Hypothesis, InferenceStatus, OperatorSettings, Universe, WorldEvent } from '@/domain';
import type { WorldSnapshot } from '@/viewport/types';
import { dataSource } from './index';

export type ResourceStatus = 'loading' | 'ready' | 'error';

export interface Resource<T> {
  status: ResourceStatus;
  /** Last successfully loaded value; retained while a newer request is in flight. */
  data: T | undefined;
  error: Error | null;
  reload: () => void;
}

interface Settled<T> {
  key: string;
  data: T | undefined;
  error: Error | null;
}

/**
 * A deliberately small async-resource hook. There is no cache or
 * deduplication by design: when the backend exists, consumers can swap in a
 * proper query layer without changing the DataSource interface.
 *
 * Status is derived by comparing the requested key with the last settled key,
 * so no state is written synchronously inside the effect.
 */
export function useResource<T>(loader: (signal: AbortSignal) => Promise<T>, deps: readonly unknown[]): Resource<T> {
  const [nonce, setNonce] = useState(0);
  const key = JSON.stringify([...deps, nonce]);
  const [settled, setSettled] = useState<Settled<T>>({ key: '', data: undefined, error: null });

  const loaderRef = useRef(loader);
  useEffect(() => {
    loaderRef.current = loader;
  });

  useEffect(() => {
    const ctrl = new AbortController();
    loaderRef
      .current(ctrl.signal)
      .then((data) => {
        if (!ctrl.signal.aborted) setSettled({ key, data, error: null });
      })
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return;
        setSettled({ key, data: undefined, error: err instanceof Error ? err : new Error(String(err)) });
      });
    return () => ctrl.abort();
  }, [key]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  const status: ResourceStatus = settled.key !== key ? 'loading' : settled.error ? 'error' : 'ready';
  return { status, data: settled.data, error: settled.key === key ? settled.error : null, reload };
}

export const useUniverses = (): Resource<Universe[]> => useResource((s) => dataSource.listUniverses(s), []);

export const useUniverse = (id: string | null): Resource<Universe | null> =>
  useResource((s) => (id ? dataSource.getUniverse(id, s) : Promise.resolve(null)), [id]);

export const useUniverseSnapshot = (id: string | null): Resource<WorldSnapshot | null> =>
  useResource((s) => (id ? dataSource.getUniverseSnapshot(id, s) : Promise.resolve(null)), [id]);

export const useCivilization = (universeId: string | null): Resource<Civilization | null> =>
  useResource((s) => (universeId ? dataSource.getCivilization(universeId, s) : Promise.resolve(null)), [universeId]);

export const useAgents = (universeId?: string | null): Resource<Agent[]> =>
  useResource((s) => dataSource.listAgents(universeId ? { universeId } : undefined, s), [universeId ?? null]);

export const useAgent = (id: string | null): Resource<Agent | null> =>
  useResource((s) => (id ? dataSource.getAgent(id, s) : Promise.resolve(null)), [id]);

export const useEvents = (params?: { universeId?: string | null; limit?: number }): Resource<WorldEvent[]> =>
  useResource(
    (s) => dataSource.listEvents({ universeId: params?.universeId ?? undefined, limit: params?.limit }, s),
    [params?.universeId ?? null, params?.limit ?? null],
  );

export const useHypotheses = (): Resource<Hypothesis[]> => useResource((s) => dataSource.listHypotheses(s), []);

export const useExperiments = (): Resource<Experiment[]> => useResource((s) => dataSource.listExperiments(s), []);

export const useSettings = (): Resource<OperatorSettings> => useResource((s) => dataSource.getSettings(s), []);

export const useAgentDecisions = (agentId: string | null, limit = 50): Resource<DecisionRecord[]> =>
  useResource((s) => (agentId ? dataSource.listAgentDecisions(agentId, { limit }, s) : Promise.resolve([])), [agentId, limit]);

export const useInferenceStatus = (): Resource<InferenceStatus | null> => useResource((s) => dataSource.getInferenceStatus(s), []);

export const useBenchmarks = (): Resource<BenchmarkRecord[]> => useResource((s) => dataSource.listBenchmarks(s), []);

export const useHealth = (): Resource<HostStatus | null> => useResource((s) => dataSource.getHealth(s), []);

/** Re-run `reload` every `ms` milliseconds while mounted (0 disables). */
export function usePolling(reload: () => void, ms: number): void {
  useEffect(() => {
    if (ms <= 0) return;
    const id = window.setInterval(reload, ms);
    return () => window.clearInterval(id);
  }, [reload, ms]);
}

/** Reload whenever `signal` changes, at most once per `minIntervalMs`. */
export function useReloadOnSignal(reload: () => void, signal: unknown, minIntervalMs = 1000): void {
  const last = useRef(0);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    const now = Date.now();
    const wait = Math.max(0, minIntervalMs - (now - last.current));
    const id = window.setTimeout(() => {
      last.current = Date.now();
      reload();
    }, wait);
    return () => window.clearTimeout(id);
  }, [signal, reload, minIntervalMs]);
}
