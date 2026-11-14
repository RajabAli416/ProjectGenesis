import type { EntityMarker, TerrainClass } from './types';

/** Numeric colours for the Pixi stage. Mirrors design/tokens.css. */
export const palette = {
  background: 0x0a0b0d,
  worldFloor: 0x0d0e11,
  boundary: 0x42464e,
  gridFine: 0xffffff,
  gridCoarse: 0xffffff,
  fg0: 0xf2f3f5,
  fg1: 0xe1e3e7,
  fg2: 0x9a9ea6,
  fg3: 0x666b74,
  fg4: 0x42464e,
  live: 0x7f9f86,
  attn: 0xc2a25f,
  crit: 0xb4705f,
  sel: 0x6f98a3,
  depth: 0x8a85a3,
} as const;

/** Terrain base colours; `v` (0..1) nudges brightness within the class. */
export const terrainColor: Record<TerrainClass, { base: number; range: number }> = {
  void: { base: 0x0a0b0d, range: 0.0 },
  barren: { base: 0x15171a, range: 0.35 },
  fertile: { base: 0x182019, range: 0.45 },
  water: { base: 0x12171d, range: 0.3 },
  built: { base: 0x23252a, range: 0.2 },
};

export function shade(color: number, amount: number): number {
  const r = (color >> 16) & 0xff;
  const g = (color >> 8) & 0xff;
  const b = color & 0xff;
  const f = 1 + amount;
  const cl = (v: number) => Math.max(0, Math.min(255, Math.round(v * f)));
  return (cl(r) << 16) | (cl(g) << 8) | cl(b);
}

/** World-unit radius of a marker: scales with zoom but never below a readable screen size. */
export function entityRadius(e: EntityMarker, zoom: number): number {
  const base = e.kind === 'agent' ? 2.2 : e.kind === 'structure' ? 3.2 : e.kind === 'portal' ? 4 : 1.6;
  const minScreenPx = e.kind === 'agent' ? 3 : e.kind === 'structure' ? 3.5 : e.kind === 'portal' ? 5 : 2.2;
  return Math.max(base, minScreenPx / zoom);
}
