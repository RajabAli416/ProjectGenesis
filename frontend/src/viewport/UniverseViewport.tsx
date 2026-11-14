import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { EmptyState, LoadingState } from '@/components/ui/EmptyState';
import { fmtCoord } from '@/lib/format';
import { PixiStage } from './PixiStage';
import type { CameraState, EntityMarker, ViewportPointer, ViewportStats, ViewportTool, WorldSnapshot } from './types';
import s from './UniverseViewport.module.css';

export interface UniverseViewportHandle {
  fit: () => void;
  zoomBy: (factor: number) => void;
  centerOn: (x: number, y: number, zoom?: number) => void;
  getCamera: () => CameraState | null;
}

export interface UniverseViewportProps {
  snapshot: WorldSnapshot | null;
  /** Whether a snapshot is still being fetched (controls the loading overlay). */
  loading?: boolean;
  tool: ViewportTool;
  selectedId: string | null;
  initialCamera?: CameraState;
  onSelect: (id: string | null) => void;
  onCamera?: (camera: CameraState) => void;
  onStats?: (stats: ViewportStats) => void;
  emptyTitle?: string;
  emptyBody?: string;
}

/**
 * React host for PixiStage. Owns nothing about the world — it forwards props
 * to the stage and reflects pointer/hover/stats back as lightweight overlays.
 */
export const UniverseViewport = forwardRef<UniverseViewportHandle, UniverseViewportProps>(function UniverseViewport(
  { snapshot, loading, tool, selectedId, initialCamera, onSelect, onCamera, onStats, emptyTitle, emptyBody },
  ref,
) {
  const hostRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<PixiStage | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [pointer, setPointer] = useState<ViewportPointer>({ world: null });
  const [pointerPx, setPointerPx] = useState<{ x: number; y: number } | null>(null);
  const [hover, setHover] = useState<EntityMarker | null>(null);
  const [camera, setCamera] = useState<CameraState | null>(initialCamera ?? null);
  const [stats, setStats] = useState<ViewportStats | null>(null);

  // Latest callbacks without re-creating the stage.
  const cbs = useRef({ onSelect, onCamera, onStats });
  cbs.current = { onSelect, onCamera, onStats };
  const snapshotRef = useRef(snapshot);
  snapshotRef.current = snapshot;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let cancelled = false;
    const stage = new PixiStage(host, {
      onSelect: (id) => cbs.current.onSelect(id),
      onHover: (id) => setHover(id ? (snapshotRef.current?.entities.find((e) => e.id === id) ?? null) : null),
      onCamera: (c) => {
        setCamera(c);
        cbs.current.onCamera?.(c);
      },
      onPointer: setPointer,
      onStats: (st) => {
        setStats(st);
        cbs.current.onStats?.(st);
      },
      onReady: () => {
        if (!cancelled) setReady(true);
      },
      onError: (e) => {
        if (!cancelled) setError(e);
      },
    });
    stageRef.current = stage;
    void stage.init();
    return () => {
      cancelled = true;
      stage.destroy();
      stageRef.current = null;
      setReady(false);
    };
  }, []);

  // Push props into the stage once ready.
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || !ready) return;
    stage.setSnapshot(snapshot);
    if (snapshot && initialCamera) {
      stage.setCamera(initialCamera);
      setCamera(initialCamera);
    } else {
      setCamera(stage.getCamera());
    }
    // initialCamera is intentionally read only when the snapshot changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [snapshot, ready]);

  useEffect(() => {
    stageRef.current?.setTool(tool);
  }, [tool, ready]);

  useEffect(() => {
    stageRef.current?.setSelection(selectedId);
  }, [selectedId, ready]);

  useImperativeHandle(
    ref,
    () => ({
      fit: () => stageRef.current?.fit(),
      zoomBy: (f) => stageRef.current?.zoomBy(f),
      centerOn: (x, y, z) => stageRef.current?.centerOn(x, y, z),
      getCamera: () => stageRef.current?.getCamera() ?? null,
    }),
    [],
  );

  // Track raw pointer position for the hover label.
  const onMove = (e: React.PointerEvent) => {
    const r = e.currentTarget.getBoundingClientRect();
    setPointerPx({ x: e.clientX - r.left, y: e.clientY - r.top });
  };

  const scale = camera ? scaleBarFor(camera.zoom) : null;

  return (
    <div className={s.root} onPointerMove={onMove} onPointerLeave={() => setPointerPx(null)}>
      <div ref={hostRef} className={s.host} />
      <div className={s.frame} />

      {error && (
        <div className={s.centerMessage}>
          <div className={s.messageBox}>
            <EmptyState icon="warn" title="Renderer unavailable" body={`PixiJS could not initialise a WebGL context: ${error.message}`} center />
          </div>
        </div>
      )}

      {!error && ready && loading && (
        <div className={s.centerMessage}>
          <div className={s.messageBox} style={{ width: 240 }}>
            <LoadingState lines={2} label="Loading snapshot" />
          </div>
        </div>
      )}

      {!error && ready && !loading && !snapshot && (
        <div className={s.centerMessage}>
          <div className={s.messageBox}>
            <EmptyState icon="universe" title={emptyTitle ?? 'No world snapshot'} body={emptyBody ?? 'The engine has not published a snapshot for this universe yet.'} center />
          </div>
        </div>
      )}

      <div className={s.overlay} aria-hidden="true">
        <div className={s.overlayRow}>
          <span className={s.chip}>
            <span className={s.chipLabel}>Cursor</span>
            {pointer.world ? fmtCoord(pointer.world.x, pointer.world.y) : '—'}
          </span>
          {stats && (
            <span className={s.chip}>
              <span className={s.chipLabel}>{stats.renderer}</span>
              {stats.fps} fps
              <span className={s.chipLabel}>ent</span>
              {stats.entities}
            </span>
          )}
        </div>
        <div className={s.overlayRow}>
          {scale && (
            <div className={s.scaleBar}>
              <span>{scale.units} u</span>
              <div className={s.scaleLine} style={{ width: scale.px }} />
            </div>
          )}
          {camera && (
            <span className={s.chip}>
              <span className={s.chipLabel}>Zoom</span>
              {camera.zoom.toFixed(2)}×
            </span>
          )}
        </div>
      </div>

      {hover && pointerPx && (
        <div className={s.hoverLabel} style={{ left: pointerPx.x, top: pointerPx.y }}>
          {hover.kind} · {hover.label ?? hover.id}
        </div>
      )}
    </div>
  );
});

/** Pick a round world-unit length that renders between 60 and 140 px. */
function scaleBarFor(zoom: number): { units: number; px: number } {
  const candidates = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];
  for (const u of candidates) {
    const px = u * zoom;
    if (px >= 60 && px <= 140) return { units: u, px };
  }
  const u = candidates[candidates.length - 1];
  return { units: u, px: Math.min(140, u * zoom) };
}
