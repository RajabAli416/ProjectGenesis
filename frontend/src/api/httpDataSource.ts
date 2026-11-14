import type {
  Agent,
  BenchmarkRecord,
  Civilization,
  DecisionRecord,
  Experiment,
  HostStatus,
  Hypothesis,
  InferenceStatus,
  OperatorSettings,
  Universe,
  WorldEvent,
} from '@/domain';
import type { WorldSnapshot } from '@/viewport/types';
import type { DataSource } from './dataSource';
import { endpoints } from './endpoints';
import { fetchJson, HttpError } from './http';

async function orNull<T>(p: Promise<T>): Promise<T | null> {
  try {
    return await p;
  } catch (e) {
    if (e instanceof HttpError && e.status === 404) return null;
    throw e;
  }
}

export const httpDataSource: DataSource = {
  kind: 'http',
  label: 'Simulation backend',

  listUniverses: (signal) => fetchJson<Universe[]>(endpoints.universes(), { signal }),
  getUniverse: (id, signal) => orNull(fetchJson<Universe>(endpoints.universe(id), { signal })),
  getUniverseSnapshot: (id, signal) => orNull(fetchJson<WorldSnapshot>(endpoints.universeSnapshot(id), { signal })),
  getCivilization: (id, signal) => orNull(fetchJson<Civilization>(endpoints.universeCivilization(id), { signal })),

  listAgents: (params, signal) =>
    params?.universeId
      ? fetchJson<Agent[]>(endpoints.universeAgents(params.universeId), { signal })
      : fetchJson<Agent[]>(endpoints.agents(), { signal }),
  getAgent: (id, signal) => orNull(fetchJson<Agent>(endpoints.agent(id), { signal })),

  listEvents: (params, signal) =>
    params?.universeId
      ? fetchJson<WorldEvent[]>(endpoints.universeEvents(params.universeId), { signal, query: { limit: params.limit } })
      : fetchJson<WorldEvent[]>(endpoints.events(), { signal, query: { limit: params?.limit } }),

  listHypotheses: (signal) => fetchJson<Hypothesis[]>(endpoints.hypotheses(), { signal }),
  getHypothesis: (id, signal) => orNull(fetchJson<Hypothesis>(endpoints.hypothesis(id), { signal })),

  listExperiments: (signal) => fetchJson<Experiment[]>(endpoints.experiments(), { signal }),
  getExperiment: (id, signal) => orNull(fetchJson<Experiment>(endpoints.experiment(id), { signal })),

  getSettings: (signal) => fetchJson<OperatorSettings>(endpoints.settings(), { signal }),

  listAgentDecisions: (agentId, params, signal) => fetchJson<DecisionRecord[]>(endpoints.agentDecisions(agentId), { signal, query: { limit: params?.limit } }),
  getInferenceStatus: (signal) => fetchJson<InferenceStatus>(endpoints.inferenceStatus(), { signal }),
  listBenchmarks: (signal) => fetchJson<BenchmarkRecord[]>(endpoints.inferenceBenchmarks(), { signal }),
  getHealth: (signal) => fetchJson<HostStatus>(endpoints.health(), { signal }),
};
