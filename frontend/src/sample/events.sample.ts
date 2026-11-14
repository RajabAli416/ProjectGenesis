// SAMPLE PRESENTATION DATA — see ./meta.ts. Not simulation output.
import type { WorldEvent } from '@/domain';

export const sampleEvents: WorldEvent[] = [
  { id: 'ev-01', universeId: 'u-meridian', tick: 41_880, severity: 'notice', category: 'universe', summary: 'Sub-world instantiated by A-1077; designated U-03.', refs: [{ kind: 'agent', id: 'a-1077' }, { kind: 'universe', id: 'u-meridian-b' }] },
  { id: 'ev-02', universeId: 'u-prime', tick: 184_301, severity: 'info', category: 'agent', summary: 'Resource node (218, 139) depleted.', refs: [{ kind: 'agent', id: 'a-0412' }] },
  { id: 'ev-03', universeId: 'u-prime', tick: 183_990, severity: 'notice', category: 'research', summary: 'A-0412 revised expectation of hazard cycle.', refs: [{ kind: 'agent', id: 'a-0412' }, { kind: 'hypothesis', id: 'h-01' }] },
  { id: 'ev-04', universeId: 'u-prime', tick: 181_000, severity: 'info', category: 'agent', summary: 'A-0377 entered dormancy (energy 0.19).', refs: [{ kind: 'agent', id: 'a-0377' }] },
  { id: 'ev-05', universeId: 'u-prime', tick: 179_920, severity: 'notice', category: 'research', summary: 'Hypothesis H-02 proposed by A-0412.', refs: [{ kind: 'hypothesis', id: 'h-02' }] },
  { id: 'ev-06', universeId: 'u-hollow', tick: 9_014, severity: 'warning', category: 'system', summary: 'Universe paused by operator.', refs: [{ kind: 'universe', id: 'u-hollow' }] },
  { id: 'ev-07', universeId: 'u-prime', tick: 176_800, severity: 'info', category: 'civilization', summary: 'Boundary observers membership reached 7.' },
  { id: 'ev-08', universeId: 'u-prime', tick: 175_306, severity: 'notice', category: 'universe', summary: 'Sub-world instantiated by EXP-02; designated U-02.', refs: [{ kind: 'experiment', id: 'exp-02' }, { kind: 'universe', id: 'u-hollow' }] },
  { id: 'ev-09', universeId: 'u-prime', tick: 172_310, severity: 'info', category: 'agent', summary: 'A-0288 deceased at age 54,310.', refs: [{ kind: 'agent', id: 'a-0288' }] },
  { id: 'ev-10', universeId: 'u-prime', tick: 171_040, severity: 'notice', category: 'civilization', summary: 'Record keeping reached emerging state.' },
  { id: 'ev-11', universeId: 'u-tern', tick: 66_201, severity: 'critical', category: 'population', summary: 'Population reached zero. Universe terminated.', refs: [{ kind: 'universe', id: 'u-tern' }] },
  { id: 'ev-12', universeId: 'u-prime', tick: 142_414, severity: 'notice', category: 'universe', summary: 'Sub-world instantiated by A-0412; designated U-01.', refs: [{ kind: 'agent', id: 'a-0412' }, { kind: 'universe', id: 'u-meridian' }] },
];
