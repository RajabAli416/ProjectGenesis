import type { DataSource } from './dataSource';
import {
  SAMPLE_DATA,
  buildSampleSnapshot,
  sampleAgents,
  sampleCivilizations,
  sampleEvents,
  sampleExperiments,
  sampleHypotheses,
  sampleSettings,
  sampleUniverses,
} from '@/sample';
import type { WorldSnapshot } from '@/viewport/types';

/** Small artificial latency so loading states are exercised in development. */
const settle = <T>(value: T, ms = 60): Promise<T> => new Promise((resolve) => setTimeout(() => resolve(value), ms));

const snapshotCache = new Map<string, WorldSnapshot | null>();

export const staticDataSource: DataSource = {
  kind: 'static',
  label: SAMPLE_DATA.label,

  listUniverses: () => settle(sampleUniverses),
  getUniverse: (id) => settle(sampleUniverses.find((u) => u.id === id) ?? null),
  getUniverseSnapshot: (id) => {
    if (!snapshotCache.has(id)) {
      const u = sampleUniverses.find((x) => x.id === id);
      snapshotCache.set(id, u ? buildSampleSnapshot(u) : null);
    }
    return settle(snapshotCache.get(id) ?? null, 90);
  },
  getCivilization: (universeId) => settle(sampleCivilizations[universeId] ?? null),

  listAgents: (params) =>
    settle(params?.universeId ? sampleAgents.filter((a) => a.universeId === params.universeId) : sampleAgents),
  getAgent: (id) => settle(sampleAgents.find((a) => a.id === id) ?? null),

  listEvents: (params) => {
    let list = params?.universeId ? sampleEvents.filter((e) => e.universeId === params.universeId) : sampleEvents;
    list = [...list].sort((a, b) => b.tick - a.tick);
    if (params?.limit) list = list.slice(0, params.limit);
    return settle(list);
  },

  listHypotheses: () => settle(sampleHypotheses),
  getHypothesis: (id) => settle(sampleHypotheses.find((h) => h.id === id) ?? null),

  listExperiments: () => settle(sampleExperiments),
  getExperiment: (id) => settle(sampleExperiments.find((e) => e.id === id) ?? null),

  getSettings: () => settle(sampleSettings),

  // No engine, no inference: these are honestly empty rather than fabricated.
  listAgentDecisions: () => settle([]),
  getInferenceStatus: () => settle(null),
  listBenchmarks: () => settle([]),
  getHealth: () => settle(null),
};
