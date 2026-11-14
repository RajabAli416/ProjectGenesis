// SAMPLE PRESENTATION DATA — see ./meta.ts. Not simulation output.
//
// The viewport needs geometry to demonstrate rendering. This module builds a
// static terrain field and entity list from a universe's seed using a tiny
// deterministic hash. The output never changes between frames or loads; it is
// scenery for the renderer, not a world model.

import type { Universe } from '@/domain';
import type { EntityMarker, TerrainCell, TerrainClass, WorldSnapshot } from '@/viewport/types';
import { sampleAgents } from './agents.sample';

function hashSeed(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Deterministic 2D value noise in [0,1). */
function noise2(ix: number, iy: number, seed: number): number {
  let n = ix * 374761393 + iy * 668265263 + seed * 1442695041;
  n = (n ^ (n >>> 13)) * 1274126177;
  n = n ^ (n >>> 16);
  return (n >>> 0) / 4294967296;
}

function smooth(x: number, y: number, seed: number, scale: number): number {
  const fx = x / scale;
  const fy = y / scale;
  const x0 = Math.floor(fx);
  const y0 = Math.floor(fy);
  const tx = fx - x0;
  const ty = fy - y0;
  const sx = tx * tx * (3 - 2 * tx);
  const sy = ty * ty * (3 - 2 * ty);
  const a = noise2(x0, y0, seed);
  const b = noise2(x0 + 1, y0, seed);
  const c = noise2(x0, y0 + 1, seed);
  const d = noise2(x0 + 1, y0 + 1, seed);
  return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy;
}

const CELL = 8;

export function buildSampleSnapshot(universe: Universe): WorldSnapshot | null {
  if (universe.status === 'initialising') return null;

  const seed = hashSeed(universe.world.seed);
  const cols = Math.floor(universe.world.width / CELL);
  const rows = Math.floor(universe.world.height / CELL);
  const fertility = universe.world.fields.find((f) => f.key === 'fertility')?.value ?? 0.5;

  const terrain: TerrainCell[] = [];
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      const e = smooth(x, y, seed, 9) * 0.65 + smooth(x, y, seed + 7, 3.5) * 0.35;
      const moisture = smooth(x, y, seed + 31, 12);
      let cls: TerrainClass;
      if (e < 0.26) cls = 'water';
      else if (e > 0.78) cls = 'void';
      else if (moisture * fertility > 0.26) cls = 'fertile';
      else cls = 'barren';
      terrain.push({ x, y, cls, v: e });
    }
  }

  const entities: EntityMarker[] = [];

  for (const a of sampleAgents.filter((a) => a.universeId === universe.id)) {
    entities.push({
      id: a.id,
      kind: 'agent',
      x: a.position.x,
      y: a.position.y,
      level: a.energy,
      faded: a.status !== 'active',
      label: a.name,
    });
  }

  // Structures and resources are placed deterministically on fertile cells.
  const fertileCells = terrain.filter((c) => c.cls === 'fertile');
  const structureCount = universe.civilizationStage === 'polities' ? 22 : universe.civilizationStage === 'settlements' ? 10 : universe.civilizationStage === 'bands' ? 3 : 0;
  const resourceCount = Math.max(4, Math.round(fertileCells.length * 0.06));

  for (let i = 0; i < structureCount && fertileCells.length; i++) {
    const c = fertileCells[Math.floor(noise2(i, 101, seed) * fertileCells.length)];
    entities.push({ id: `s-${i}`, kind: 'structure', x: c.x * CELL + CELL / 2, y: c.y * CELL + CELL / 2, level: 0.6 + noise2(i, 202, seed) * 0.4 });
    // Mark the cell as built for shading.
    c.cls = 'built';
  }
  for (let i = 0; i < resourceCount && fertileCells.length; i++) {
    const c = fertileCells[Math.floor(noise2(i, 303, seed) * fertileCells.length)];
    entities.push({ id: `r-${i}`, kind: 'resource', x: c.x * CELL + noise2(i, 404, seed) * CELL, y: c.y * CELL + noise2(i, 505, seed) * CELL, level: 0.2 + noise2(i, 606, seed) * 0.8 });
  }

  // Portals: one per child universe, placed near the parent's created-by agent if present.
  universe.childIds.forEach((childId, i) => {
    const creator = sampleAgents.find((a) => a.memory.some((m) => m.summary.includes(childId === 'u-meridian' ? 'U-01' : childId === 'u-hollow' ? 'U-02' : 'U-03')));
    const x = creator ? creator.position.x + 6 : universe.world.width * (0.3 + i * 0.3);
    const y = creator ? creator.position.y - 4 : universe.world.height * 0.5;
    entities.push({ id: `portal-${childId}`, kind: 'portal', x, y, level: 1, label: childId });
  });

  return {
    universeId: universe.id,
    tick: universe.clock.tick,
    width: universe.world.width,
    height: universe.world.height,
    cellSize: CELL,
    terrain,
    entities,
  };
}
