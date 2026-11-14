import { Application, Container, Graphics } from 'pixi.js';
import type { CameraState, EntityMarker, StageEvents, ViewportTool, WorldSnapshot } from './types';
import { clampZoom, fitCamera, screenToWorld, visibleRect, zoomAround } from './camera';
import { entityRadius, palette, shade, terrainColor } from './palette';
import { hitTestEntities } from './hitTest';

/**
 * PixiStage renders a WorldSnapshot and handles camera interaction.
 *
 * It is deliberately framework-agnostic: React mounts it, feeds it snapshots
 * and camera/tool/selection changes, and listens to StageEvents. The stage
 * owns no simulation state and never mutates a snapshot. All draw routines
 * are idempotent functions of (snapshot, camera, selection, hover).
 */
export class PixiStage {
  private app: Application | null = null;
  private destroyed = false;
  private ready = false;

  private readonly world = new Container();
  private readonly terrainLayer = new Graphics();
  private readonly gridLayer = new Graphics();
  private readonly boundaryLayer = new Graphics();
  private readonly entityLayer = new Graphics();
  private readonly selectionLayer = new Graphics();

  private snapshot: WorldSnapshot | null = null;
  private camera: CameraState = { cx: 0, cy: 0, zoom: 1 };
  private tool: ViewportTool = 'select';
  private selectedId: string | null = null;
  private hoverId: string | null = null;

  private vw = 1;
  private vh = 1;
  private lastEntityZoom = -1;

  private resizeObs: ResizeObserver | null = null;
  private drag: { startX: number; startY: number; camX: number; camY: number; moved: boolean; pointerId: number } | null = null;

  private frameCount = 0;
  private frameAccum = 0;

  constructor(
    private readonly host: HTMLElement,
    private readonly events: StageEvents,
  ) {}

  /* ---------------------------------------------------------------- lifecycle */

  async init(): Promise<void> {
    const app = new Application();
    try {
      await app.init({
        background: palette.background,
        antialias: true,
        autoDensity: true,
        resolution: Math.min(window.devicePixelRatio || 1, 2),
        preference: 'webgl',
        width: Math.max(1, this.host.clientWidth),
        height: Math.max(1, this.host.clientHeight),
      });
    } catch (err) {
      this.events.onError(err instanceof Error ? err : new Error(String(err)));
      return;
    }

    // React StrictMode or fast navigation may destroy us during the await.
    if (this.destroyed) {
      app.destroy(true, { children: true });
      return;
    }

    this.app = app;
    this.world.addChild(this.terrainLayer, this.gridLayer, this.boundaryLayer, this.entityLayer, this.selectionLayer);
    app.stage.addChild(this.world);
    app.stage.eventMode = 'none';

    const canvas = app.canvas;
    canvas.style.display = 'block';
    canvas.style.touchAction = 'none';
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', 'Universe viewport');
    this.host.appendChild(canvas);

    this.vw = Math.max(1, this.host.clientWidth);
    this.vh = Math.max(1, this.host.clientHeight);

    this.resizeObs = new ResizeObserver(() => this.handleResize());
    this.resizeObs.observe(this.host);

    canvas.addEventListener('pointerdown', this.onPointerDown);
    canvas.addEventListener('pointermove', this.onPointerMove);
    canvas.addEventListener('pointerup', this.onPointerUp);
    canvas.addEventListener('pointercancel', this.onPointerUp);
    canvas.addEventListener('pointerleave', this.onPointerLeave);
    canvas.addEventListener('wheel', this.onWheel, { passive: false });
    canvas.addEventListener('contextmenu', this.onContextMenu);

    app.ticker.add(this.onTick);

    this.ready = true;
    this.applyCamera();
    this.redrawAll();
    this.events.onReady();
  }

  destroy(): void {
    this.destroyed = true;
    this.ready = false;
    this.resizeObs?.disconnect();
    this.resizeObs = null;
    const app = this.app;
    if (app) {
      const canvas = app.canvas;
      canvas.removeEventListener('pointerdown', this.onPointerDown);
      canvas.removeEventListener('pointermove', this.onPointerMove);
      canvas.removeEventListener('pointerup', this.onPointerUp);
      canvas.removeEventListener('pointercancel', this.onPointerUp);
      canvas.removeEventListener('pointerleave', this.onPointerLeave);
      canvas.removeEventListener('wheel', this.onWheel);
      canvas.removeEventListener('contextmenu', this.onContextMenu);
      app.ticker.remove(this.onTick);
      app.destroy(true, { children: true });
      this.app = null;
    }
  }

  get isReady(): boolean {
    return this.ready;
  }

  /* --------------------------------------------------------------- public api */

  setSnapshot(snapshot: WorldSnapshot | null, opts: { fit?: boolean } = {}): void {
    const changedUniverse = snapshot?.universeId !== this.snapshot?.universeId;
    this.snapshot = snapshot;
    this.lastEntityZoom = -1;
    if (!this.ready) return;
    if (snapshot && (opts.fit || changedUniverse)) this.fit(false);
    this.redrawAll();
    this.emitStats(true);
  }

  setCamera(camera: CameraState): void {
    this.camera = { ...camera, zoom: clampZoom(camera.zoom) };
    if (!this.ready) return;
    this.applyCamera();
    this.redrawGrid();
    this.redrawEntitiesIfZoomChanged();
  }

  getCamera(): CameraState {
    return { ...this.camera };
  }

  setTool(tool: ViewportTool): void {
    this.tool = tool;
    this.updateCursor();
  }

  setSelection(id: string | null): void {
    if (this.selectedId === id) return;
    this.selectedId = id;
    if (this.ready) this.redrawSelection();
  }

  fit(emit = true): void {
    if (!this.snapshot) return;
    this.camera = fitCamera(this.snapshot.width, this.snapshot.height, this.vw, this.vh);
    if (!this.ready) return;
    this.applyCamera();
    this.redrawGrid();
    this.redrawEntitiesIfZoomChanged();
    if (emit) this.events.onCamera(this.getCamera());
  }

  zoomBy(factor: number): void {
    this.camera = zoomAround(this.camera, factor, this.vw / 2, this.vh / 2, this.vw, this.vh);
    if (!this.ready) return;
    this.applyCamera();
    this.redrawGrid();
    this.redrawEntitiesIfZoomChanged();
    this.events.onCamera(this.getCamera());
  }

  centerOn(wx: number, wy: number, zoom?: number): void {
    this.camera = { cx: wx, cy: wy, zoom: zoom !== undefined ? clampZoom(zoom) : this.camera.zoom };
    if (!this.ready) return;
    this.applyCamera();
    this.redrawGrid();
    this.redrawEntitiesIfZoomChanged();
    this.events.onCamera(this.getCamera());
  }

  /* ------------------------------------------------------------------ camera */

  private applyCamera(): void {
    const { cx, cy, zoom } = this.camera;
    this.world.scale.set(zoom);
    this.world.position.set(this.vw / 2 - cx * zoom, this.vh / 2 - cy * zoom);
  }

  private handleResize(): void {
    if (!this.app) return;
    const w = Math.max(1, this.host.clientWidth);
    const h = Math.max(1, this.host.clientHeight);
    if (w === this.vw && h === this.vh) return;
    this.vw = w;
    this.vh = h;
    this.app.renderer.resize(w, h);
    this.applyCamera();
    this.redrawGrid();
  }

  /* ----------------------------------------------------------------- drawing */

  private redrawAll(): void {
    this.redrawTerrain();
    this.redrawBoundary();
    this.redrawGrid();
    this.redrawEntities();
    this.redrawSelection();
  }

  private redrawTerrain(): void {
    const g = this.terrainLayer;
    g.clear();
    const s = this.snapshot;
    if (!s) return;
    g.rect(0, 0, s.width, s.height).fill({ color: palette.worldFloor });
    const cs = s.cellSize;
    for (const c of s.terrain) {
      if (c.cls === 'void') continue;
      const spec = terrainColor[c.cls];
      const color = shade(spec.base, (c.v - 0.5) * spec.range);
      g.rect(c.x * cs, c.y * cs, cs, cs).fill({ color });
    }
  }

  private redrawBoundary(): void {
    const g = this.boundaryLayer;
    g.clear();
    const s = this.snapshot;
    if (!s) return;
    g.rect(0, 0, s.width, s.height).stroke({ color: palette.boundary, width: 1, pixelLine: true, alpha: 0.9 });
  }

  private redrawGrid(): void {
    const g = this.gridLayer;
    g.clear();
    const s = this.snapshot;
    if (!s) return;
    const zoom = this.camera.zoom;
    const vis = visibleRect(this.camera, this.vw, this.vh);
    const x0 = Math.max(0, vis.x0);
    const y0 = Math.max(0, vis.y0);
    const x1 = Math.min(s.width, vis.x1);
    const y1 = Math.min(s.height, vis.y1);
    if (x1 <= x0 || y1 <= y0) return;

    const fine = s.cellSize;
    const coarse = s.cellSize * 8;

    // Fine grid appears as cells become legible; coarse grid is always present but faint.
    const fineAlpha = Math.max(0, Math.min(0.07, (zoom - 1.2) * 0.05));
    const coarseAlpha = Math.max(0.05, Math.min(0.14, zoom * 0.05));

    if (fineAlpha > 0.005) {
      for (let x = Math.ceil(x0 / fine) * fine; x <= x1; x += fine) {
        if (x % coarse === 0) continue;
        g.moveTo(x, y0).lineTo(x, y1);
      }
      for (let y = Math.ceil(y0 / fine) * fine; y <= y1; y += fine) {
        if (y % coarse === 0) continue;
        g.moveTo(x0, y).lineTo(x1, y);
      }
      g.stroke({ color: palette.gridFine, alpha: fineAlpha, width: 1, pixelLine: true });
    }

    for (let x = Math.ceil(x0 / coarse) * coarse; x <= x1; x += coarse) g.moveTo(x, y0).lineTo(x, y1);
    for (let y = Math.ceil(y0 / coarse) * coarse; y <= y1; y += coarse) g.moveTo(x0, y).lineTo(x1, y);
    g.stroke({ color: palette.gridCoarse, alpha: coarseAlpha, width: 1, pixelLine: true });
  }

  private redrawEntitiesIfZoomChanged(): void {
    // Marker sizes have a screen-space floor, so they must be recomputed when zoom moves.
    if (Math.abs(this.camera.zoom - this.lastEntityZoom) / Math.max(this.lastEntityZoom, 0.001) > 0.04) {
      this.redrawEntities();
      this.redrawSelection();
    }
  }

  private redrawEntities(): void {
    const g = this.entityLayer;
    g.clear();
    const s = this.snapshot;
    if (!s) return;
    const zoom = this.camera.zoom;
    this.lastEntityZoom = zoom;

    // Draw in a stable order so overlapping markers layer consistently.
    const order: Record<EntityMarker['kind'], number> = { resource: 0, structure: 1, portal: 2, agent: 3 };
    const sorted = [...s.entities].sort((a, b) => order[a.kind] - order[b.kind]);

    for (const e of sorted) {
      const r = entityRadius(e, zoom);
      switch (e.kind) {
        case 'agent': {
          const alpha = e.faded ? 0.32 : 0.95;
          // Brightness tracks energy; the marker stays neutral grey.
          const color = shade(palette.fg2, (e.level - 0.5) * 0.6);
          g.circle(e.x, e.y, r).fill({ color, alpha });
          if (!e.faded) g.circle(e.x, e.y, r).stroke({ color: palette.fg4, width: 1, pixelLine: true, alpha: 0.8 });
          break;
        }
        case 'structure': {
          g.rect(e.x - r, e.y - r, r * 2, r * 2).fill({ color: palette.fg4, alpha: 0.55 });
          g.rect(e.x - r, e.y - r, r * 2, r * 2).stroke({ color: palette.fg3, width: 1, pixelLine: true, alpha: 0.9 });
          break;
        }
        case 'resource': {
          g.moveTo(e.x, e.y - r).lineTo(e.x + r, e.y).lineTo(e.x, e.y + r).lineTo(e.x - r, e.y).closePath();
          g.fill({ color: palette.attn, alpha: 0.25 + e.level * 0.45 });
          break;
        }
        case 'portal': {
          g.rect(e.x - r, e.y - r, r * 2, r * 2).stroke({ color: palette.depth, width: 1, pixelLine: true, alpha: 0.9 });
          const r2 = r * 0.5;
          g.rect(e.x - r2, e.y - r2, r2 * 2, r2 * 2).stroke({ color: palette.depth, width: 1, pixelLine: true, alpha: 0.7 });
          break;
        }
      }
    }
  }

  private redrawSelection(): void {
    const g = this.selectionLayer;
    g.clear();
    const s = this.snapshot;
    if (!s) return;
    const zoom = this.camera.zoom;

    const drawRing = (e: EntityMarker, color: number, alpha: number, ticks: boolean) => {
      const r = entityRadius(e, zoom) + 4 / zoom;
      g.circle(e.x, e.y, r).stroke({ color, width: 1, pixelLine: true, alpha });
      if (ticks) {
        const t = 3 / zoom;
        const o = r + 2 / zoom;
        g.moveTo(e.x - o - t, e.y).lineTo(e.x - o, e.y);
        g.moveTo(e.x + o, e.y).lineTo(e.x + o + t, e.y);
        g.moveTo(e.x, e.y - o - t).lineTo(e.x, e.y - o);
        g.moveTo(e.x, e.y + o).lineTo(e.x, e.y + o + t);
        g.stroke({ color, width: 1, pixelLine: true, alpha });
      }
    };

    if (this.hoverId && this.hoverId !== this.selectedId) {
      const e = s.entities.find((x) => x.id === this.hoverId);
      if (e) drawRing(e, palette.fg3, 0.9, false);
    }
    if (this.selectedId) {
      const e = s.entities.find((x) => x.id === this.selectedId);
      if (e) drawRing(e, palette.sel, 1, true);
    }
  }

  /* ------------------------------------------------------------------- input */

  private canvasPoint(ev: PointerEvent | WheelEvent): { x: number; y: number } {
    const rect = (ev.currentTarget as HTMLCanvasElement).getBoundingClientRect();
    return { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
  }

  private onPointerDown = (ev: PointerEvent): void => {
    if (!this.app) return;
    const p = this.canvasPoint(ev);
    try {
      (ev.currentTarget as HTMLCanvasElement).setPointerCapture(ev.pointerId);
    } catch {
      /* synthetic or already-released pointer; dragging still works within the canvas */
    }
    this.drag = { startX: p.x, startY: p.y, camX: this.camera.cx, camY: this.camera.cy, moved: false, pointerId: ev.pointerId };
    this.updateCursor(true);
  };

  private onPointerMove = (ev: PointerEvent): void => {
    if (!this.app) return;
    const p = this.canvasPoint(ev);
    const w = screenToWorld(this.camera, p.x, p.y, this.vw, this.vh);
    this.events.onPointer({ world: w });

    if (this.drag && this.drag.pointerId === ev.pointerId) {
      const dx = p.x - this.drag.startX;
      const dy = p.y - this.drag.startY;
      if (!this.drag.moved && Math.hypot(dx, dy) > 3) this.drag.moved = true;
      if (this.drag.moved) {
        this.camera = { ...this.camera, cx: this.drag.camX - dx / this.camera.zoom, cy: this.drag.camY - dy / this.camera.zoom };
        this.applyCamera();
        this.redrawGrid();
      }
      return;
    }

    if (this.tool === 'select' && this.snapshot) {
      const hit = hitTestEntities(this.snapshot.entities, w.x, w.y, this.camera);
      const id = hit?.id ?? null;
      if (id !== this.hoverId) {
        this.hoverId = id;
        this.redrawSelection();
        this.events.onHover(id);
        this.updateCursor();
      }
    }
  };

  private onPointerUp = (ev: PointerEvent): void => {
    if (!this.app) return;
    const drag = this.drag;
    this.drag = null;
    this.updateCursor();
    if (!drag || drag.pointerId !== ev.pointerId) return;

    if (drag.moved) {
      this.events.onCamera(this.getCamera());
      return;
    }

    // A click (no drag) selects under the select tool; primary button only.
    if (this.tool === 'select' && ev.button === 0 && this.snapshot) {
      const p = this.canvasPoint(ev);
      const w = screenToWorld(this.camera, p.x, p.y, this.vw, this.vh);
      const hit = hitTestEntities(this.snapshot.entities, w.x, w.y, this.camera);
      const id = hit?.id ?? null;
      this.selectedId = id;
      this.redrawSelection();
      this.events.onSelect(id);
    }
  };

  private onPointerLeave = (): void => {
    this.events.onPointer({ world: null });
    if (this.hoverId) {
      this.hoverId = null;
      this.redrawSelection();
      this.events.onHover(null);
    }
  };

  private onWheel = (ev: WheelEvent): void => {
    if (!this.app) return;
    ev.preventDefault();
    const p = this.canvasPoint(ev);
    const factor = Math.exp(-ev.deltaY * (ev.deltaMode === 1 ? 0.05 : 0.0015));
    this.camera = zoomAround(this.camera, factor, p.x, p.y, this.vw, this.vh);
    this.applyCamera();
    this.redrawGrid();
    this.redrawEntitiesIfZoomChanged();
    this.events.onCamera(this.getCamera());
  };

  private onContextMenu = (ev: Event): void => ev.preventDefault();

  private updateCursor(dragging = false): void {
    const canvas = this.app?.canvas;
    if (!canvas) return;
    if (dragging && this.drag?.moved) canvas.style.cursor = 'grabbing';
    else if (this.tool === 'pan') canvas.style.cursor = 'grab';
    else canvas.style.cursor = this.hoverId ? 'pointer' : 'crosshair';
  }

  /* ------------------------------------------------------------------- stats */

  private onTick = (): void => {
    if (!this.app) return;
    this.frameCount += 1;
    this.frameAccum += this.app.ticker.deltaMS;
    if (this.frameAccum >= 1000) {
      this.emitStats();
      this.frameCount = 0;
      this.frameAccum = 0;
    }
  };

  private emitStats(immediate = false): void {
    if (!this.app) return;
    const fps = immediate ? Math.round(this.app.ticker.FPS) : Math.round((this.frameCount * 1000) / Math.max(1, this.frameAccum));
    const rendererName = this.app.renderer.name;
    this.events.onStats({ fps, entities: this.snapshot?.entities.length ?? 0, drawCalls: null, renderer: rendererName });
  }
}
