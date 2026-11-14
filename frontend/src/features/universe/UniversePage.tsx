import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useParams } from 'react-router';
import { useUniverseContext } from '@/app/universeContext';
import { useAgents, useReloadOnSignal, useUniverseSnapshot } from '@/api/hooks';
import { useChrome } from '@/store/chromeStore';
import { useConnectionStore } from '@/store/connectionStore';
import { useUiStore } from '@/store/uiStore';
import { useSelectionStore } from '@/store/selectionStore';
import { UniverseViewport, type UniverseViewportHandle } from '@/viewport';
import { Page } from '@/components/shell/AppShell';
import { StatusDot } from '@/components/ui';
import { fmtTick } from '@/lib/format';
import { TransportBar } from './TransportBar';
import { UniverseInspector } from './UniverseInspector';
import s from './UniversePage.module.css';

function isEditable(el: EventTarget | null): boolean {
  return el instanceof HTMLElement && (el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA' || el.isContentEditable);
}

export default function UniversePage() {
  const { universeId } = useParams();
  const { active, byId, setActive } = useUniverseContext();

  // A route param overrides the operator's active universe.
  useEffect(() => {
    if (universeId && byId.has(universeId) && active?.id !== universeId) setActive(universeId);
  }, [universeId, byId, active?.id, setActive]);

  const universe = universeId && byId.has(universeId) ? byId.get(universeId)! : active;

  const snapshotRes = useUniverseSnapshot(universe?.id ?? null);
  const agentsRes = useAgents(universe?.id ?? null);

  // Live channel: stream snapshots for the universe on screen only, and refresh the agent list
  // when the backend signals a change (birth, death, pause...) or periodically while it runs.
  const subscribe = useConnectionStore((st) => st.subscribe);
  const connection = useConnectionStore((st) => st.state);
  const liveSnapshot = useConnectionStore((st) => (universe ? st.snapshots[universe.id] : undefined));
  const revision = useConnectionStore((st) => (universe ? st.universeRevisions[universe.id] : undefined));
  useEffect(() => {
    if (connection !== 'open') return;
    subscribe(universe ? [universe.id] : []);
    return () => subscribe([]);
  }, [connection, subscribe, universe]);
  useReloadOnSignal(agentsRes.reload, `${revision ?? 0}:${Math.floor((liveSnapshot?.tick ?? 0) / 200)}`, 2000);

  const inspectorOpen = useUiStore((st) => st.inspectorOpen);
  const setInspectorOpen = useUiStore((st) => st.setInspectorOpen);

  const tool = useSelectionStore((st) => st.tool);
  const setTool = useSelectionStore((st) => st.setTool);
  const selectedEntityId = useSelectionStore((st) => st.selectedEntityId);
  const selectEntity = useSelectionStore((st) => st.selectEntity);
  const cameras = useSelectionStore((st) => st.cameras);
  const rememberCamera = useSelectionStore((st) => st.rememberCamera);

  const viewportRef = useRef<UniverseViewportHandle>(null);
  // Only a snapshot that belongs to the current universe is rendered; stale data from a previous
  // universe is not. The streamed snapshot wins over the REST one whenever it is at least as recent.
  const restSnapshot = snapshotRes.status === 'ready' ? (snapshotRes.data ?? null) : null;
  const snapshot = useMemo(() => {
    if (!universe) return null;
    const live = liveSnapshot && liveSnapshot.universeId === universe.id ? liveSnapshot : null;
    if (live && (!restSnapshot || live.tick >= restSnapshot.tick)) return live;
    return restSnapshot && restSnapshot.universeId === universe.id ? restSnapshot : null;
  }, [universe, liveSnapshot, restSnapshot]);

  const selected = useMemo(() => snapshot?.entities.find((e) => e.id === selectedEntityId) ?? null, [snapshot, selectedEntityId]);
  const selectedAgent = useMemo(() => (selected?.kind === 'agent' ? (agentsRes.data?.find((a) => a.id === selected.id) ?? null) : null), [selected, agentsRes.data]);

  useChrome({
    detail: universe ? `${universe.code} ${universe.name}` : 'No universe',
    inspectorAvailable: true,
    statusLeft: snapshot ? `snapshot tick ${fmtTick(snapshot.tick)} · ${snapshot.entities.length} entities` : null,
    statusRight: selected ? `selected ${selected.kind} ${selected.id.toUpperCase()}` : null,
  });

  // Clear a selection that no longer exists in the current snapshot.
  useEffect(() => {
    if (selectedEntityId && snapshot && !snapshot.entities.some((e) => e.id === selectedEntityId)) selectEntity(null);
  }, [snapshot, selectedEntityId, selectEntity]);

  const zoomIn = useCallback(() => viewportRef.current?.zoomBy(1.25), []);
  const zoomOut = useCallback(() => viewportRef.current?.zoomBy(1 / 1.25), []);
  const fit = useCallback(() => viewportRef.current?.fit(), []);
  const centerSelected = useCallback(() => {
    if (selected) viewportRef.current?.centerOn(selected.x, selected.y, Math.max(viewportRef.current?.getCamera()?.zoom ?? 1, 4));
  }, [selected]);

  // Viewport keyboard shortcuts.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isEditable(e.target)) return;
      switch (e.key) {
        case 'v':
          setTool('select');
          break;
        case 'h':
          setTool('pan');
          break;
        case '+':
        case '=':
          zoomIn();
          break;
        case '-':
          zoomOut();
          break;
        case 'f':
          fit();
          break;
        case 'Escape':
          selectEntity(null);
          break;
        case 'i':
          setInspectorOpen(!inspectorOpen);
          break;
        default:
          return;
      }
      e.preventDefault();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setTool, zoomIn, zoomOut, fit, selectEntity, setInspectorOpen, inspectorOpen]);

  return (
    <Page flush>
      <div className={s.root}>
        <div className={s.stage}>
          {universe && universe.status === 'initialising' && (
            <div className={s.banner}>
              <StatusDot tone="sel" /> Universe is initialising — no snapshot has been published yet.
            </div>
          )}
          <UniverseViewport
            ref={viewportRef}
            snapshot={snapshot}
            loading={snapshotRes.status === 'loading'}
            tool={tool}
            selectedId={selectedEntityId}
            initialCamera={universe ? cameras[universe.id] : undefined}
            onSelect={selectEntity}
            onCamera={(c) => universe && rememberCamera(universe.id, c)}
            emptyTitle={universe ? 'No world snapshot' : 'No universe selected'}
            emptyBody={universe ? 'The engine has not published a snapshot for this universe.' : 'Choose a universe from the header to begin observing.'}
          />
          <TransportBar universe={universe} tool={tool} onTool={setTool} onZoomIn={zoomIn} onZoomOut={zoomOut} onFit={fit} />
        </div>

        <UniverseInspector
          open={inspectorOpen}
          onClose={() => setInspectorOpen(false)}
          universe={universe}
          snapshot={snapshot}
          selected={selected}
          selectedAgent={selectedAgent}
          onCenterSelected={centerSelected}
          onClearSelection={() => selectEntity(null)}
        />
      </div>
    </Page>
  );
}
