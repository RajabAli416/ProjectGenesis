import type {
  BenchmarkRecord,
  BenchmarkRequest,
  CreateExperimentRequest,
  CreateHypothesisRequest,
  CreateUniverseRequest,
  Experiment,
  Hypothesis,
  OperatorSettings,
  PatchExperimentRequest,
  Universe,
} from '@/domain';
import { endpoints } from './endpoints';
import { fetchJson } from './http';

/**
 * Write-side boundary for everything that is not a transport command:
 * creating universes and experiments, applying settings, running benchmarks.
 * Each call returns the backend's view of the resource; the interface never
 * fabricates the result of a mutation.
 */
export interface Mutations {
  createUniverse(req: CreateUniverseRequest): Promise<Universe>;
  archiveUniverse(id: string): Promise<Universe>;

  createExperiment(req: CreateExperimentRequest): Promise<Experiment>;
  patchExperiment(id: string, req: PatchExperimentRequest): Promise<Experiment>;
  deleteExperiment(id: string): Promise<void>;
  startExperimentRun(id: string): Promise<Experiment>;
  abortExperiment(id: string): Promise<Experiment>;

  createHypothesis(req: CreateHypothesisRequest): Promise<Hypothesis>;
  withdrawHypothesis(id: string): Promise<Hypothesis>;

  putSettings(settings: OperatorSettings): Promise<OperatorSettings>;
  setCredential(providerId: string, credential: string | null): Promise<OperatorSettings>;

  runBenchmark(req: BenchmarkRequest): Promise<BenchmarkRecord>;
}

export const httpMutations: Mutations = {
  createUniverse: (req) => fetchJson(endpoints.universes(), { method: 'POST', body: req }),
  archiveUniverse: (id) => fetchJson(endpoints.universeArchive(id), { method: 'POST' }),

  createExperiment: (req) => fetchJson(endpoints.experiments(), { method: 'POST', body: req }),
  patchExperiment: (id, req) => fetchJson(endpoints.experiment(id), { method: 'PATCH', body: req }),
  deleteExperiment: (id) => fetchJson(endpoints.experiment(id), { method: 'DELETE' }),
  startExperimentRun: (id) => fetchJson(endpoints.experimentRuns(id), { method: 'POST' }),
  abortExperiment: (id) => fetchJson(endpoints.experimentAbort(id), { method: 'POST' }),

  createHypothesis: (req) => fetchJson(endpoints.hypotheses(), { method: 'POST', body: req }),
  withdrawHypothesis: (id) => fetchJson(endpoints.hypothesisWithdraw(id), { method: 'POST' }),

  putSettings: (settings) => fetchJson(endpoints.settings(), { method: 'PUT', body: settings }),
  setCredential: (providerId, credential) => fetchJson(endpoints.providerCredential(providerId), { method: 'PUT', body: { credential } }),

  runBenchmark: (req) => fetchJson(endpoints.inferenceBenchmarks(), { method: 'POST', body: req }),
};

export class NoEngineError extends Error {
  constructor() {
    super('No simulation engine connected.');
    this.name = 'NoEngineError';
  }
}

/** With the static source every mutation is refused explicitly rather than faked. */
export const noEngineMutations: Mutations = new Proxy({} as Mutations, {
  get: () => () => Promise.reject(new NoEngineError()),
});
