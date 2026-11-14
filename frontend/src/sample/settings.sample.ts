// SAMPLE PRESENTATION DATA — see ./meta.ts. Not simulation output.
import type { OperatorSettings } from '@/domain';

/**
 * Default operator settings shown before a backend is connected.
 * Providers are described by an opaque adapter id — the interface does not
 * special-case any vendor.
 */
export const sampleSettings: OperatorSettings = {
  providers: [
    { id: 'p-local', label: 'Local inference', adapter: 'openai-compatible', baseUrl: 'http://127.0.0.1:11434/v1', model: 'local-default', hasCredential: false, enabled: true },
    { id: 'p-remote', label: 'Remote endpoint', adapter: 'openai-compatible', baseUrl: 'https://example.invalid/v1', model: 'unset', hasCredential: false, enabled: false },
  ],
  reasoning: { providerId: 'p-local', temperature: 0.7, maxSteps: 12, memoryWindow: 48, reflectionInterval: 400 },
  simulation: { tickRate: 24, worldWidth: 512, worldHeight: 320, initialPopulation: 64, mutationRate: 0.015, energyDecay: 0.002 },
  performance: { renderScale: 1, entityCap: 5_000, fpsCap: 60, cullOffscreen: true },
  persistence: { snapshotIntervalTicks: 2_400, retainSnapshots: 48, autosave: true, storePath: './data/snapshots' },
};
