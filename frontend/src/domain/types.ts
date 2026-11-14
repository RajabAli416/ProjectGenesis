/**
 * Domain model for RECURSION.
 *
 * These types describe the shape of state the simulation backend exposes.
 * They are intentionally free of any frontend or rendering concerns, and are
 * expected to mirror the Pydantic models of the FastAPI service once it exists.
 *
 * Time is measured in ticks. The frontend never advances ticks itself; every
 * clock value here is a snapshot received from the backend.
 */

export type Id = string;

export type UniverseStatus = 'running' | 'paused' | 'initialising' | 'terminated' | 'archived';

export interface SimulationClock {
  tick: number;
  /** Ticks per real-time second the engine is currently targeting. 0 when paused. */
  rate: number;
  /** Multiplier requested by the operator, relative to the engine's base rate. */
  speed: number;
  /** ISO timestamp of the snapshot this clock was read from. */
  observedAt: string;
}

export interface UniverseLineage {
  parentId: Id | null;
  /** 0 for a root universe. */
  depth: number;
  /** Agent or experiment that caused this universe to be created, if known. */
  createdBy: { kind: 'operator' | 'agent' | 'experiment'; id: Id | null; label: string };
  createdAtTick: number;
  /** ISO timestamp in operator wall-clock time. */
  createdAt: string;
}

export interface WorldConditions {
  width: number;
  height: number;
  seed: string;
  /** Normalised 0..1 scalar fields the engine reports; names are backend-defined. */
  fields: Array<{ key: string; label: string; value: number; unit?: string }>;
}

export interface PopulationStats {
  total: number;
  alive: number;
  born: number;
  died: number;
  /** Mean per capita, in engine energy units. */
  meanEnergy: number;
  meanAge: number;
  generations: number;
}

/**
 * realtime: the clock runs at tick rate and model decisions are applied when they arrive.
 * lockstep: the clock waits for every pending decision — slower, but reproducible.
 */
export type ExecutionMode = 'realtime' | 'lockstep';

export interface Universe {
  id: Id;
  name: string;
  /** Short mono code shown in dense tables, e.g. "U-00". */
  code: string;
  status: UniverseStatus;
  clock: SimulationClock;
  lineage: UniverseLineage;
  population: PopulationStats;
  world: WorldConditions;
  civilizationStage: CivilizationStage | null;
  childIds: Id[];
  // Additive fields reported by the backend.
  mode?: ExecutionMode;
  cellSize?: number;
  /** Provider:model@digest of the model that has driven decisions here, if any. */
  modelRef?: string | null;
  /** Share of the host tick budget (1.0 for a root universe). */
  computeShare?: number;
  engineVersion?: string;
}

export interface CreateUniverseRequest {
  name?: string;
  seed?: string | null;
  /** Dot-path overrides on the backend UniverseConfig, e.g. {"rules.hazard_amplitude": 0.4}. */
  config?: Record<string, unknown>;
  initialPopulation?: number | null;
  mode?: ExecutionMode;
  start?: boolean;
}

export type AgentStatus = 'active' | 'dormant' | 'deceased';

export interface AgentRelationship {
  agentId: Id;
  kind: 'parent' | 'offspring' | 'partner' | 'ally' | 'rival' | 'mentor' | 'student';
  /** -1..1 affinity reported by the engine. */
  affinity: number;
  sinceTick: number;
}

export interface KnowledgeItem {
  id: Id;
  topic: string;
  /** 0..1 */
  confidence: number;
  acquiredAtTick: number;
  source: 'observation' | 'inference' | 'taught' | 'inherited';
}

export interface MemoryRecord {
  id: Id;
  tick: number;
  kind: 'perception' | 'action' | 'social' | 'reflection';
  summary: string;
  /** 0..1 */
  salience: number;
  /** Where the record came from: mechanics ('observation'), the model ('inference'), another agent ('taught') or birth ('inherited'). */
  source?: 'observation' | 'inference' | 'taught' | 'inherited';
}

/** Which policy produced an agent's most recent decision. */
export type DecisionPolicy = 'reflex' | 'model';

export interface AgentIntent {
  type: string;
  params: Record<string, unknown>;
  startedTick: number;
  policy: DecisionPolicy;
  progress?: number;
  decisionId?: number | null;
}

export interface Agent {
  id: Id;
  universeId: Id;
  name: string;
  status: AgentStatus;
  generation: number;
  bornAtTick: number;
  diedAtTick: number | null;
  age: number;
  /** 0..1 normalised energy */
  energy: number;
  position: { x: number; y: number };
  lineage: { parentIds: Id[]; offspringIds: Id[] };
  relationships: AgentRelationship[];
  knowledge: KnowledgeItem[];
  memory: MemoryRecord[];
  traits: Array<{ key: string; label: string; value: number }>;
  // Additive fields reported by the backend.
  inventory?: Record<string, number>;
  intent?: AgentIntent | null;
  policy?: DecisionPolicy;
  modelRef?: string | null;
  decisionsTotal?: number;
  decisionsModel?: number;
}

/** One entry of an agent's decision log: what was asked, what came back, whether mechanics accepted it. */
export interface DecisionRecord {
  id: number;
  agentId: Id;
  universeId: Id;
  tickRequested: number;
  tickApplied: number | null;
  policy: DecisionPolicy;
  purpose: 'decision' | 'reflection';
  action: { type: string; params?: Record<string, unknown> } | null;
  accepted: boolean;
  rejectionReason: string | null;
  rationale: string | null;
  requestId: number | null;
  modelRef: string | null;
  latencyMs: number | null;
  valid: boolean | null;
  promptTokens: number | null;
  completionTokens: number | null;
  createdAt: string;
}

export type CivilizationStage = 'none' | 'bands' | 'settlements' | 'polities' | 'industrial' | 'reflective';

export interface PopulationEra {
  id: Id;
  label: string;
  fromTick: number;
  toTick: number | null;
  peakPopulation: number;
  note?: string;
}

export interface Technology {
  id: Id;
  name: string;
  tier: number;
  state: 'unknown' | 'emerging' | 'established';
  requires: Id[];
  discoveredAtTick: number | null;
  discoveredBy: Id | null;
}

export interface Institution {
  id: Id;
  name: string;
  kind: 'kinship' | 'council' | 'guild' | 'market' | 'cult' | 'academy' | 'state';
  members: number;
  foundedAtTick: number;
}

export interface Infrastructure {
  id: Id;
  name: string;
  count: number;
  condition: number; // 0..1
}

export interface Civilization {
  universeId: Id;
  stage: CivilizationStage;
  eras: PopulationEra[];
  technologies: Technology[];
  institutions: Institution[];
  infrastructure: Infrastructure[];
  collectiveKnowledge: Array<{ id: Id; topic: string; holders: number; confidence: number }>;
}

export type HypothesisState = 'proposed' | 'testing' | 'supported' | 'refuted' | 'withdrawn';

export interface Evidence {
  id: Id;
  kind: 'observation' | 'measurement' | 'experiment' | 'testimony' | 'derivation';
  source: string;
  /** -1..1: negative weights count against the hypothesis. */
  weight: number;
  tick: number;
  summary: string;
  /** True when the value was produced by the mechanics (a probe or measurement), not asserted by a model. */
  verifiedByMechanics?: boolean;
}

/**
 * Where a hypothesis most plausibly came from. The backend tracks every term an
 * agent has been exposed to through prompts and messages; a claim that reuses
 * exposed vocabulary is never presented as an independent discovery.
 */
export type ProvenanceClass = 'prompt-exposed' | 'evidence-linked' | 'model-originated' | 'operator';

export interface Provenance {
  classification: ProvenanceClass;
  /** Terms of the claim the proposing agent had already seen in prompts or messages. */
  promptExposedTerms: string[];
  /** Share of linked evidence that is mechanics-verified. */
  verifiedEvidenceRatio: number;
  /** Plain-language caveat, always present for model-originated claims. */
  note: string;
}

export interface ReasoningStep {
  id: Id;
  index: number;
  tick: number;
  actor: { kind: 'agent' | 'operator' | 'system'; id: Id | null; label: string };
  statement: string;
  /** Confidence after this step, 0..1 */
  confidence: number;
}

export interface Hypothesis {
  id: Id;
  universeId: Id;
  title: string;
  statement: string;
  state: HypothesisState;
  /** 0..1 */
  confidence: number;
  proposedAtTick: number;
  proposedBy: { kind: 'agent' | 'operator'; id: Id | null; label: string };
  evidence: Evidence[];
  reasoning: ReasoningStep[];
  experimentIds: Id[];
  // Additive fields reported by the backend.
  provenance?: Provenance;
  /** The claim concerns the nature of the world itself (simulation, creator, boundary). */
  existential?: boolean;
}

export interface CreateHypothesisRequest {
  universeId: Id;
  title: string;
  statement: string;
  confidence?: number;
  experimentIds?: Id[];
}

export type ExperimentStatus = 'draft' | 'queued' | 'running' | 'complete' | 'aborted';

export interface ExperimentVariable {
  key: string;
  label: string;
  control: string | number | boolean;
  treatment: string | number | boolean;
  unit?: string;
}

export interface ExperimentRun {
  id: Id;
  index: number;
  startedAt: string;
  finishedAt: string | null;
  seed: string;
  status: ExperimentStatus;
  universeIds: Id[];
  // Additive fields reported by the backend.
  controlUniverseId?: Id | null;
  treatmentUniverseId?: Id | null;
  /** Per-arm metrics computed from mechanics at completion: { control: {...}, treatment: {...} }. */
  metrics?: Record<string, Record<string, unknown>> | null;
}

export interface Experiment {
  id: Id;
  name: string;
  objective: string;
  status: ExperimentStatus;
  controlUniverseId: Id | null;
  variables: ExperimentVariable[];
  replicates: number;
  reproducibility: {
    seed: string;
    engineVersion: string | null;
    snapshotHash: string | null;
    deterministic: boolean;
  };
  runs: ExperimentRun[];
  hypothesisIds: Id[];
  createdAt: string;
  // Additive fields reported by the backend.
  durationTicks?: number;
  mode?: ExecutionMode;
  baseConfig?: Record<string, unknown>;
}

export interface CreateExperimentRequest {
  name: string;
  objective?: string;
  variables?: ExperimentVariable[];
  replicates?: number;
  seed?: string | null;
  durationTicks?: number;
  mode?: ExecutionMode;
  hypothesisIds?: Id[];
  baseConfig?: Record<string, unknown>;
  controlUniverseId?: Id | null;
}

export type PatchExperimentRequest = Partial<Omit<CreateExperimentRequest, 'baseConfig' | 'controlUniverseId'>> & { status?: ExperimentStatus };

export type EventSeverity = 'info' | 'notice' | 'warning' | 'critical';

export interface WorldEvent {
  id: Id;
  universeId: Id;
  tick: number;
  severity: EventSeverity;
  category: 'population' | 'civilization' | 'universe' | 'agent' | 'research' | 'system';
  summary: string;
  refs?: Array<{ kind: 'agent' | 'universe' | 'hypothesis' | 'experiment'; id: Id }>;
}

/* ---- Settings (operator-side, persisted by the backend once connected) ---- */

export interface ProviderConfig {
  id: Id;
  label: string;
  /** Opaque adapter identifier the backend understands; the UI never special-cases it. */
  adapter: string;
  baseUrl: string;
  model: string;
  /** Whether a credential is stored server-side. The UI never receives the key itself. */
  hasCredential: boolean;
  enabled: boolean;
}

export interface ReasoningConfig {
  providerId: Id | null;
  temperature: number;
  maxSteps: number;
  memoryWindow: number;
  reflectionInterval: number;
  // Additive fields reported by the backend.
  /** Ticks between scheduled decisions (needs and messages can trigger earlier). */
  decisionInterval?: number;
  /** Context window requested from the provider. */
  numCtx?: number;
  thinkDecisions?: boolean;
  thinkReflection?: boolean;
  promptProfile?: string;
  concurrency?: number;
  timeoutS?: number;
}

export interface SimulationParams {
  tickRate: number;
  /** World units; the terrain grid is width / cellSize cells wide. */
  worldWidth: number;
  worldHeight: number;
  initialPopulation: number;
  mutationRate: number;
  energyDecay: number;
  cellSize?: number;
}

export interface PerformanceConfig {
  renderScale: number;
  entityCap: number;
  fpsCap: number;
  cullOffscreen: boolean;
}

export interface PersistenceConfig {
  snapshotIntervalTicks: number;
  retainSnapshots: number;
  autosave: boolean;
  storePath: string;
}

export interface OperatorSettings {
  providers: ProviderConfig[];
  reasoning: ReasoningConfig;
  simulation: SimulationParams;
  performance: PerformanceConfig;
  persistence: PersistenceConfig;
}

/* ---- Inference observability (backend-only; no sample fixtures exist for these) ---- */

export interface ModelRef {
  id: string;
  providerId: string;
  adapter: string;
  model: string;
  digest: string | null;
  family: string | null;
  parameterSize: string | null;
  quantization: string | null;
  firstSeen: string;
}

export interface InferenceStatus {
  providerId: string | null;
  adapter: string | null;
  reachable: boolean;
  providerVersion: string | null;
  model: string | null;
  modelRef: ModelRef | null;
  /** Whether the provider reports the configured model as resident (Ollama: loaded in memory). */
  modelLoaded: boolean;
  queueDepth: number;
  inFlight: number;
  concurrency: number;
  completed: number;
  failed: number;
  invalid: number;
  latencyP50Ms: number | null;
  latencyP95Ms: number | null;
  lastError: string | null;
}

export interface BenchmarkRecord {
  id: number;
  createdAt: string;
  providerId: string;
  model: string;
  modelRef: string | null;
  numCtx: number;
  think: boolean;
  requests: number;
  jsonValidRate: number;
  schemaValidRate: number;
  latencyP50Ms: number;
  latencyP95Ms: number;
  promptTokensMean: number;
  completionTokensMean: number;
  promptEvalRateTps: number | null;
  evalRateTps: number | null;
  loadDurationMs: number | null;
  notes: string | null;
}

export interface BenchmarkRequest {
  providerId?: string | null;
  model?: string | null;
  numCtx?: number | null;
  think?: boolean;
  requests?: number;
}

export interface HostStatus {
  engineVersion: string;
  mechanicsVersion: number;
  promptVersion: number;
  uptimeS: number;
  universes: number;
  running: number;
  totalRate: number;
  hostTickBudget: number;
  wsClients: number;
  dbPath: string;
  inference: InferenceStatus;
}
