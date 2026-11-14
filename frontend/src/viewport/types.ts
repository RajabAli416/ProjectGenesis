/**
 * Render-facing types for the universe viewport.
 *
 * A WorldSnapshot is a flattened, render-ready view of a universe at a single
 * tick. It is produced from backend state (REST or WebSocket) and handed to
 * the PixiStage. The stage never mutates it and never derives new state from it.
 */

export type TerrainClass = 'void' | 'barren' | 'fertile' | 'water' | 'built';

export interface TerrainCell {
  x: number;
  y: number;
  cls: TerrainClass;
  /** 0..1 intensity used only for shading within the class. */
  v: number;
}

export type EntityKind = 'agent' | 'structure' | 'resource' | 'portal';

export interface EntityMarker {
  id: string;
  kind: EntityKind;
  x: number;
  y: number;
  /** 0..1 — agents: energy; structures: condition; resources: remaining. */
  level: number;
  /** Render hint: dormant/deceased agents are drawn faded. */
  faded?: boolean;
  label?: string;
}

export interface WorldSnapshot {
  universeId: string;
  tick: number;
  width: number;
  height: number;
  /** World units per terrain cell. */
  cellSize: number;
  terrain: TerrainCell[];
  entities: EntityMarker[];
}

export interface CameraState {
  /** World coordinate at the viewport centre. */
  cx: number;
  cy: number;
  /** Screen pixels per world unit. */
  zoom: number;
}

export type ViewportTool = 'select' | 'pan';

export interface ViewportSelection {
  entityId: string | null;
}

export interface ViewportPointer {
  /** World coordinates under the cursor, or null when outside the canvas. */
  world: { x: number; y: number } | null;
}

export interface ViewportStats {
  fps: number;
  entities: number;
  drawCalls: number | null;
  renderer: string;
}

export interface StageEvents {
  onSelect: (entityId: string | null) => void;
  onHover: (entityId: string | null) => void;
  onCamera: (camera: CameraState) => void;
  onPointer: (pointer: ViewportPointer) => void;
  onStats: (stats: ViewportStats) => void;
  onReady: () => void;
  onError: (error: Error) => void;
}
