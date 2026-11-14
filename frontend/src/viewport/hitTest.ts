import type { CameraState, EntityMarker } from './types';
import { entityRadius } from './palette';

/**
 * Nearest entity whose marker contains (or is within `slopPx` of) the given
 * world point. Linear scan: entity counts in a single viewport are small
 * enough that a spatial index is not yet warranted.
 */
export function hitTestEntities(entities: EntityMarker[], wx: number, wy: number, cam: CameraState, slopPx = 6): EntityMarker | null {
  let best: EntityMarker | null = null;
  let bestD = Infinity;
  const slop = slopPx / cam.zoom;
  for (const e of entities) {
    const r = entityRadius(e, cam.zoom) + slop;
    const dx = e.x - wx;
    const dy = e.y - wy;
    const d2 = dx * dx + dy * dy;
    if (d2 <= r * r && d2 < bestD) {
      best = e;
      bestD = d2;
    }
  }
  return best;
}
