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

/**
 * The read-side boundary between the interface and the simulation backend.
 *
 * Two implementations exist:
 *  - staticDataSource: serves bundled, clearly-labelled presentation fixtures.
 *  - httpDataSource:   calls the FastAPI service via REST.
 *
 * Nothing above this interface knows which one is active.
 */
export interface DataSource {
  readonly kind: 'static' | 'http';
  readonly label: string;

  listUniverses(signal?: AbortSignal): Promise<Universe[]>;
  getUniverse(id: string, signal?: AbortSignal): Promise<Universe | null>;
  getUniverseSnapshot(id: string, signal?: AbortSignal): Promise<WorldSnapshot | null>;
  getCivilization(universeId: string, signal?: AbortSignal): Promise<Civilization | null>;

  listAgents(params?: { universeId?: string }, signal?: AbortSignal): Promise<Agent[]>;
  getAgent(id: string, signal?: AbortSignal): Promise<Agent | null>;

  listEvents(params?: { universeId?: string; limit?: number }, signal?: AbortSignal): Promise<WorldEvent[]>;

  listHypotheses(signal?: AbortSignal): Promise<Hypothesis[]>;
  getHypothesis(id: string, signal?: AbortSignal): Promise<Hypothesis | null>;

  listExperiments(signal?: AbortSignal): Promise<Experiment[]>;
  getExperiment(id: string, signal?: AbortSignal): Promise<Experiment | null>;

  getSettings(signal?: AbortSignal): Promise<OperatorSettings>;

  /* Backend-only observability. The static source returns empty results — it has no engine to report on. */
  listAgentDecisions(agentId: string, params?: { limit?: number }, signal?: AbortSignal): Promise<DecisionRecord[]>;
  getInferenceStatus(signal?: AbortSignal): Promise<InferenceStatus | null>;
  listBenchmarks(signal?: AbortSignal): Promise<BenchmarkRecord[]>;
  getHealth(signal?: AbortSignal): Promise<HostStatus | null>;
}
