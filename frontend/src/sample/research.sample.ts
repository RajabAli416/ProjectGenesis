// SAMPLE PRESENTATION DATA — see ./meta.ts. Not simulation output.
import type { Experiment, Hypothesis } from '@/domain';

export const sampleHypotheses: Hypothesis[] = [
  {
    id: 'h-01',
    universeId: 'u-prime',
    title: 'World boundary is a hard limit',
    statement:
      'The edge of the inhabited region cannot be crossed by any action available to agents; it is a property of the world rather than of agents.',
    state: 'testing',
    confidence: 0.64,
    proposedAtTick: 163_404,
    proposedBy: { kind: 'agent', id: 'a-0412', label: 'Ilse (A-0412)' },
    evidence: [
      { id: 'e-1', kind: 'observation', source: 'A-0412', weight: 0.4, tick: 163_404, summary: 'Movement toward x < 0 produced no displacement across 40 attempts.' },
      { id: 'e-2', kind: 'observation', source: 'A-0509', weight: 0.3, tick: 170_100, summary: 'Same result at eastern edge (x ≥ 512).' },
      { id: 'e-3', kind: 'testimony', source: 'Boundary observers', weight: 0.2, tick: 176_800, summary: 'Seven agents independently report identical behaviour.' },
      { id: 'e-4', kind: 'derivation', source: 'A-0377', weight: -0.15, tick: 178_210, summary: 'Boundary may be perceptual, not physical — no test distinguishes the two.' },
    ],
    reasoning: [
      { id: 'r-1', index: 1, tick: 163_404, actor: { kind: 'agent', id: 'a-0412', label: 'Ilse' }, statement: 'Repeated westward movement at x=0 fails. Propose: boundary exists.', confidence: 0.35 },
      { id: 'r-2', index: 2, tick: 170_100, actor: { kind: 'agent', id: 'a-0509', label: 'Kael' }, statement: 'Replicated at opposite edge. Boundary is symmetric.', confidence: 0.52 },
      { id: 'r-3', index: 3, tick: 176_800, actor: { kind: 'system', id: null, label: 'Aggregation' }, statement: 'Seven independent reports folded into collective knowledge.', confidence: 0.68 },
      { id: 'r-4', index: 4, tick: 178_210, actor: { kind: 'agent', id: 'a-0377', label: 'Brann' }, statement: 'Objection: cannot rule out a perceptual limit. Confidence revised downward.', confidence: 0.64 },
    ],
    experimentIds: ['exp-01'],
  },
  {
    id: 'h-02',
    universeId: 'u-prime',
    title: 'Instantiated sub-worlds obey the same rules as the host world',
    statement:
      'A sub-world created by an agent exhibits the same boundary, decay and regeneration behaviour as the world it was created from.',
    state: 'proposed',
    confidence: 0.41,
    proposedAtTick: 179_920,
    proposedBy: { kind: 'agent', id: 'a-0412', label: 'Ilse (A-0412)' },
    evidence: [
      { id: 'e-5', kind: 'observation', source: 'U-01 telemetry', weight: 0.25, tick: 180_000, summary: 'Resource regeneration interval in U-01 matches host within 4%.' },
    ],
    reasoning: [
      { id: 'r-5', index: 1, tick: 179_920, actor: { kind: 'agent', id: 'a-0412', label: 'Ilse' }, statement: 'If sub-world rules match host rules, host may itself be a sub-world.', confidence: 0.41 },
    ],
    experimentIds: [],
  },
  {
    id: 'h-03',
    universeId: 'u-tern',
    title: 'Hazard density above 0.4 prevents settlement formation',
    statement: 'No persistent structures appear in regions with sustained hazard above 0.4.',
    state: 'refuted',
    confidence: 0.12,
    proposedAtTick: 20_000,
    proposedBy: { kind: 'operator', id: null, label: 'Operator' },
    evidence: [
      { id: 'e-6', kind: 'measurement', source: 'U-04 telemetry', weight: -0.6, tick: 48_000, summary: 'Three persistent structures recorded in a 0.47 hazard region.' },
    ],
    reasoning: [
      { id: 'r-6', index: 1, tick: 20_000, actor: { kind: 'operator', id: null, label: 'Operator' }, statement: 'Initial conjecture from U-04 configuration.', confidence: 0.55 },
      { id: 'r-7', index: 2, tick: 48_000, actor: { kind: 'system', id: null, label: 'Telemetry' }, statement: 'Counter-example observed. Marked refuted.', confidence: 0.12 },
    ],
    experimentIds: [],
  },
];

export const sampleExperiments: Experiment[] = [
  {
    id: 'exp-01',
    name: 'Boundary permeability',
    objective: 'Determine whether the world boundary is physical or perceptual by varying edge behaviour between control and treatment universes.',
    status: 'queued',
    controlUniverseId: 'u-prime',
    variables: [
      { key: 'edge_mode', label: 'Edge mode', control: 'clamp', treatment: 'wrap' },
      { key: 'edge_signal', label: 'Edge perceptual signal', control: true, treatment: false },
      { key: 'world_width', label: 'World width', control: 512, treatment: 512, unit: 'cells' },
    ],
    replicates: 3,
    reproducibility: { seed: '7f3a9c1e', engineVersion: null, snapshotHash: null, deterministic: true },
    runs: [],
    hypothesisIds: ['h-01'],
    createdAt: '2026-10-31T08:12:00Z',
  },
  {
    id: 'exp-02',
    name: 'Scarcity gradient',
    objective: 'Measure the effect of resource density on time-to-first-settlement.',
    status: 'running',
    controlUniverseId: 'u-prime',
    variables: [
      { key: 'resource_density', label: 'Resource density', control: 0.38, treatment: 0.15 },
      { key: 'fertility', label: 'Fertility', control: 0.54, treatment: 0.22 },
      { key: 'initial_population', label: 'Initial population', control: 64, treatment: 28, unit: 'agents' },
    ],
    replicates: 2,
    reproducibility: { seed: '0a7e55d9', engineVersion: '0.0.0-dev', snapshotHash: 'sha256:3c1f…a90e', deterministic: true },
    runs: [
      { id: 'run-02-1', index: 1, startedAt: '2026-11-01T11:05:33Z', finishedAt: null, seed: '0a7e55d9', status: 'running', universeIds: ['u-hollow'] },
      { id: 'run-02-2', index: 2, startedAt: '2026-11-01T11:05:33Z', finishedAt: null, seed: '0a7e55da', status: 'queued', universeIds: [] },
    ],
    hypothesisIds: [],
    createdAt: '2026-11-01T10:40:00Z',
  },
  {
    id: 'exp-03',
    name: 'Reflection interval sweep',
    objective: 'Vary the reasoning reflection interval and observe its effect on knowledge propagation rate.',
    status: 'draft',
    controlUniverseId: null,
    variables: [{ key: 'reflection_interval', label: 'Reflection interval', control: 400, treatment: 100, unit: 'ticks' }],
    replicates: 4,
    reproducibility: { seed: '', engineVersion: null, snapshotHash: null, deterministic: false },
    runs: [],
    hypothesisIds: [],
    createdAt: '2026-11-02T00:01:00Z',
  },
];
