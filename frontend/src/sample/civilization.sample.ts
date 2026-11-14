// SAMPLE PRESENTATION DATA — see ./meta.ts. Not simulation output.
import type { Civilization } from '@/domain';

/** Only U-00 has a populated civilization record; other universes exercise empty states. */
export const sampleCivilizations: Record<string, Civilization> = {
  'u-prime': {
    universeId: 'u-prime',
    stage: 'polities',
    eras: [
      { id: 'era-1', label: 'Dispersal', fromTick: 0, toTick: 18_400, peakPopulation: 212, note: 'Unstructured foraging; no persistent groups.' },
      { id: 'era-2', label: 'Bands', fromTick: 18_400, toTick: 61_900, peakPopulation: 488 },
      { id: 'era-3', label: 'Settlements', fromTick: 61_900, toTick: 128_300, peakPopulation: 1_012, note: 'First fixed structures near the northern basin.' },
      { id: 'era-4', label: 'Polities', fromTick: 128_300, toTick: null, peakPopulation: 1_311 },
    ],
    technologies: [
      { id: 't-fire', name: 'Controlled fire', tier: 1, state: 'established', requires: [], discoveredAtTick: 9_120, discoveredBy: 'a-0031' },
      { id: 't-tools', name: 'Shaped tools', tier: 1, state: 'established', requires: [], discoveredAtTick: 12_700, discoveredBy: 'a-0044' },
      { id: 't-storage', name: 'Grain storage', tier: 2, state: 'established', requires: ['t-tools'], discoveredAtTick: 64_010, discoveredBy: 'a-0157' },
      { id: 't-clay', name: 'Clay firing', tier: 2, state: 'established', requires: ['t-fire'], discoveredAtTick: 71_300, discoveredBy: 'a-0163' },
      { id: 't-irrigation', name: 'Irrigation', tier: 3, state: 'established', requires: ['t-storage', 't-tools'], discoveredAtTick: 129_900, discoveredBy: 'a-0240' },
      { id: 't-record', name: 'Record keeping', tier: 3, state: 'emerging', requires: ['t-clay'], discoveredAtTick: 171_040, discoveredBy: 'a-0377' },
      { id: 't-subworld', name: 'Sub-world instantiation', tier: 4, state: 'emerging', requires: ['t-record'], discoveredAtTick: 142_414, discoveredBy: 'a-0412' },
      { id: 't-metal', name: 'Metallurgy', tier: 4, state: 'unknown', requires: ['t-clay', 't-fire'], discoveredAtTick: null, discoveredBy: null },
    ],
    institutions: [
      { id: 'i-1', name: 'Basin kin-group', kind: 'kinship', members: 184, foundedAtTick: 40_200 },
      { id: 'i-2', name: 'Northern council', kind: 'council', members: 11, foundedAtTick: 130_500 },
      { id: 'i-3', name: 'Potters', kind: 'guild', members: 36, foundedAtTick: 98_040 },
      { id: 'i-4', name: 'Boundary observers', kind: 'academy', members: 7, foundedAtTick: 163_900 },
    ],
    infrastructure: [
      { id: 'inf-1', name: 'Shelters', count: 312, condition: 0.77 },
      { id: 'inf-2', name: 'Granaries', count: 24, condition: 0.69 },
      { id: 'inf-3', name: 'Irrigation channels', count: 9, condition: 0.58 },
      { id: 'inf-4', name: 'Kilns', count: 14, condition: 0.81 },
      { id: 'inf-5', name: 'Record stones', count: 3, condition: 0.92 },
    ],
    collectiveKnowledge: [
      { id: 'ck-1', topic: 'Seasonal hazard cycle', holders: 402, confidence: 0.71 },
      { id: 'ck-2', topic: 'World boundary is impassable', holders: 118, confidence: 0.64 },
      { id: 'ck-3', topic: 'Fertile basin location', holders: 1_009, confidence: 0.93 },
      { id: 'ck-4', topic: 'Sub-worlds can be instantiated', holders: 9, confidence: 0.52 },
      { id: 'ck-5', topic: 'Resource nodes regenerate', holders: 611, confidence: 0.58 },
    ],
  },
  'u-meridian': {
    universeId: 'u-meridian',
    stage: 'bands',
    eras: [
      { id: 'era-m1', label: 'Dispersal', fromTick: 0, toTick: 14_200, peakPopulation: 96 },
      { id: 'era-m2', label: 'Bands', fromTick: 14_200, toTick: null, peakPopulation: 318 },
    ],
    technologies: [
      { id: 'tm-fire', name: 'Controlled fire', tier: 1, state: 'established', requires: [], discoveredAtTick: 6_300, discoveredBy: 'a-1002' },
      { id: 'tm-tools', name: 'Shaped tools', tier: 1, state: 'emerging', requires: [], discoveredAtTick: 38_900, discoveredBy: 'a-1077' },
    ],
    institutions: [{ id: 'im-1', name: 'River kin-group', kind: 'kinship', members: 61, foundedAtTick: 20_010 }],
    infrastructure: [],
    collectiveKnowledge: [{ id: 'ckm-1', topic: 'River course', holders: 240, confidence: 0.88 }],
  },
};
