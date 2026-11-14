/**
 * REST route table. Mirrors the resource layout the FastAPI backend exposes
 * (backend/app/api/routers). Keeping it in one place means the http data
 * source, the mutation layer and the backend contract test agree on paths.
 */
export const endpoints = {
  health: () => '/health',
  version: () => '/version',

  universes: () => '/universes',
  universe: (id: string) => `/universes/${encodeURIComponent(id)}`,
  universeSnapshot: (id: string) => `/universes/${encodeURIComponent(id)}/snapshot`,
  universeAgents: (id: string) => `/universes/${encodeURIComponent(id)}/agents`,
  universeCivilization: (id: string) => `/universes/${encodeURIComponent(id)}/civilization`,
  universeEvents: (id: string) => `/universes/${encodeURIComponent(id)}/events`,
  universeCommand: (id: string) => `/universes/${encodeURIComponent(id)}/command`,
  universeArchive: (id: string) => `/universes/${encodeURIComponent(id)}/archive`,
  universeConfig: (id: string) => `/universes/${encodeURIComponent(id)}/config`,

  agents: () => '/agents',
  agent: (id: string) => `/agents/${encodeURIComponent(id)}`,
  agentMemory: (id: string) => `/agents/${encodeURIComponent(id)}/memory`,
  agentDecisions: (id: string) => `/agents/${encodeURIComponent(id)}/decisions`,

  events: () => '/events',

  hypotheses: () => '/research/hypotheses',
  hypothesis: (id: string) => `/research/hypotheses/${encodeURIComponent(id)}`,
  hypothesisWithdraw: (id: string) => `/research/hypotheses/${encodeURIComponent(id)}/withdraw`,

  experiments: () => '/experiments',
  experiment: (id: string) => `/experiments/${encodeURIComponent(id)}`,
  experimentRuns: (id: string) => `/experiments/${encodeURIComponent(id)}/runs`,
  experimentAbort: (id: string) => `/experiments/${encodeURIComponent(id)}/abort`,

  settings: () => '/settings',
  providerCredential: (providerId: string) => `/settings/providers/${encodeURIComponent(providerId)}/credential`,

  inferenceStatus: () => '/inference/status',
  inferenceModels: () => '/inference/models',
  inferenceAvailable: () => '/inference/available',
  inferenceRequests: () => '/inference/requests',
  inferenceDecisions: () => '/inference/decisions',
  inferenceBenchmarks: () => '/inference/benchmarks',
} as const;
