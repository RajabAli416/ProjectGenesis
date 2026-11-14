import type { AgentStatus, CivilizationStage, EventSeverity, ExperimentStatus, HypothesisState, UniverseStatus } from '@/domain';

export type Tone = 'live' | 'attn' | 'crit' | 'sel' | 'depth' | 'neutral';

/** Ordered from least to most developed; index doubles as a progress value. */
export const civilizationStages: readonly CivilizationStage[] = ['none', 'bands', 'settlements', 'polities', 'industrial', 'reflective'];

export const civilizationStageLabel: Record<CivilizationStage, string> = {
  none: 'Pre-social',
  bands: 'Bands',
  settlements: 'Settlements',
  polities: 'Polities',
  industrial: 'Industrial',
  reflective: 'Reflective',
};

export const universeTone: Record<UniverseStatus, Tone> = {
  running: 'live',
  paused: 'attn',
  initialising: 'sel',
  terminated: 'crit',
  archived: 'neutral',
};

export const agentTone: Record<AgentStatus, Tone> = {
  active: 'live',
  dormant: 'attn',
  deceased: 'neutral',
};

export const hypothesisTone: Record<HypothesisState, Tone> = {
  proposed: 'neutral',
  testing: 'sel',
  supported: 'live',
  refuted: 'crit',
  withdrawn: 'neutral',
};

export const experimentTone: Record<ExperimentStatus, Tone> = {
  draft: 'neutral',
  queued: 'attn',
  running: 'live',
  complete: 'sel',
  aborted: 'crit',
};

export const severityTone: Record<EventSeverity, Tone> = {
  info: 'neutral',
  notice: 'sel',
  warning: 'attn',
  critical: 'crit',
};
