import type { CameraState } from './types';

export const MIN_ZOOM = 0.25;
export const MAX_ZOOM = 24;

export const clampZoom = (z: number): number => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z));

export function screenToWorld(cam: CameraState, sx: number, sy: number, vw: number, vh: number): { x: number; y: number } {
  return { x: cam.cx + (sx - vw / 2) / cam.zoom, y: cam.cy + (sy - vh / 2) / cam.zoom };
}

export function worldToScreen(cam: CameraState, wx: number, wy: number, vw: number, vh: number): { x: number; y: number } {
  return { x: (wx - cam.cx) * cam.zoom + vw / 2, y: (wy - cam.cy) * cam.zoom + vh / 2 };
}

/** Zoom by a factor while keeping the world point under (sx, sy) fixed. */
export function zoomAround(cam: CameraState, factor: number, sx: number, sy: number, vw: number, vh: number): CameraState {
  const before = screenToWorld(cam, sx, sy, vw, vh);
  const zoom = clampZoom(cam.zoom * factor);
  const next = { ...cam, zoom };
  const after = screenToWorld(next, sx, sy, vw, vh);
  return { cx: cam.cx + (before.x - after.x), cy: cam.cy + (before.y - after.y), zoom };
}

/** Camera that frames a world of the given size with some margin. */
export function fitCamera(worldW: number, worldH: number, vw: number, vh: number, margin = 24): CameraState {
  const zoom = clampZoom(Math.min((vw - margin * 2) / worldW, (vh - margin * 2) / worldH));
  return { cx: worldW / 2, cy: worldH / 2, zoom };
}

/** Visible world rectangle for the current camera. */
export function visibleRect(cam: CameraState, vw: number, vh: number): { x0: number; y0: number; x1: number; y1: number } {
  const tl = screenToWorld(cam, 0, 0, vw, vh);
  const br = screenToWorld(cam, vw, vh, vw, vh);
  return { x0: tl.x, y0: tl.y, x1: br.x, y1: br.y };
}
