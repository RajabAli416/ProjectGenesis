import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import type { Universe } from '@/domain';
import { useUniverseContext } from '@/app/universeContext';
import { useEvents, useSettings } from '@/api/hooks';
import { dataSource, mutations } from '@/api';
import { useChrome } from '@/store/chromeStore';
import { Page } from '@/components/shell/AppShell';
import { Panel, Readouts, DataList, StatusLabel, Tag, Button, EmptyState, ResourceBoundary } from '@/components/ui';
import { fmtDateTime, fmtInt, fmtTick, titleCase } from '@/lib/format';
import { civilizationStageLabel, universeTone } from '@/lib/status';
import { cn } from '@/lib/cn';
import { SampleNotice } from '../shared/SampleNotice';
import { NewUniverseDialog } from './NewUniverseDialog';
import layout from '../shared/layout.module.css';
import s from './RealitiesPage.module.css';

interface TreeRow {
  universe: Universe;
  depth: number;
  /** For each ancestor level: whether that ancestor's branch continues below. */
  guides: boolean[];
  isLast: boolean;
}

function buildTree(universes: Universe[]): TreeRow[] {
  const byParent = new Map<string | null, Universe[]>();
  for (const u of universes) {
    const key = u.lineage.parentId && universes.some((x) => x.id === u.lineage.parentId) ? u.lineage.parentId : null;
    byParent.set(key, [...(byParent.get(key) ?? []), u]);
  }
  for (const list of byParent.values()) list.sort((a, b) => a.lineage.createdAtTick - b.lineage.createdAtTick || a.code.localeCompare(b.code));

  const rows: TreeRow[] = [];
  const walk = (parentId: string | null, depth: number, guides: boolean[]) => {
    const children = byParent.get(parentId) ?? [];
    children.forEach((u, i) => {
      const isLast = i === children.length - 1;
      rows.push({ universe: u, depth, guides, isLast });
      walk(u.id, depth + 1, [...guides, !isLast]);
    });
  };
  walk(null, 0, []);
  return rows;
}

export default function RealitiesPage() {
  const { universeId } = useParams();
  const navigate = useNavigate();
  const { resource, universes, byId, setActive } = useUniverseContext();

  const rows = useMemo(() => buildTree(universes), [universes]);
  const selected = universeId ? (byId.get(universeId) ?? null) : null;
  const events = useEvents({ universeId: selected?.id ?? null, limit: 50 });
  const settings = useSettings();
  const [creating, setCreating] = useState(false);
  const [archiving, setArchiving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const live = dataSource.kind === 'http';

  const archive = async () => {
    if (!selected || !window.confirm(`Archive ${selected.code} ${selected.name}? It stops permanently and is removed from the hierarchy.`)) return;
    setArchiving(true);
    setActionError(null);
    try {
      await mutations.archiveUniverse(selected.id);
      resource.reload();
      navigate('/realities');
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Archive failed');
    } finally {
      setArchiving(false);
    }
  };

  const stats = useMemo(() => {
    const roots = universes.filter((u) => !u.lineage.parentId).length;
    const deepest = universes.reduce((d, u) => Math.max(d, u.lineage.depth), 0);
    const byAgent = universes.filter((u) => u.lineage.createdBy.kind === 'agent').length;
    const byExp = universes.filter((u) => u.lineage.createdBy.kind === 'experiment').length;
    return { roots, deepest, byAgent, byExp };
  }, [universes]);

  useChrome({ detail: selected ? `${selected.code} ${selected.name}` : 'Hierarchy', statusLeft: `${universes.length} universes · depth ${stats.deepest}` });

  const ancestors = useMemo(() => {
    const out: Universe[] = [];
    let cur = selected;
    while (cur?.lineage.parentId) {
      const p = byId.get(cur.lineage.parentId);
      if (!p) break;
      out.unshift(p);
      cur = p;
    }
    return out;
  }, [selected, byId]);

  return (
    <Page
      title="Recursive Realities"
      lede="Universes instantiated inside other universes, with their creation history."
      actions={
        <Button size="sm" variant="primary" icon="plus" disabled={!live} title={live ? 'Create a root universe' : 'Creating universes requires a connected backend'} onClick={() => setCreating(true)}>
          New universe
        </Button>
      }
    >
      <SampleNotice compact />
      <NewUniverseDialog
        open={creating}
        onClose={() => setCreating(false)}
        defaults={settings.data ?? null}
        onCreated={(u) => {
          resource.reload();
          setActive(u.id);
          navigate(`/realities/${u.id}`);
        }}
      />

      <ResourceBoundary
        resource={resource}
        isEmpty={(d) => d.length === 0}
        empty={
          <EmptyState
            icon="realities"
            title="No universes"
            body={live ? 'The engine is running but owns no universe yet. Create a root universe to begin.' : 'The hierarchy appears once at least one root universe is registered.'}
            actions={live ? <Button size="sm" variant="primary" icon="plus" onClick={() => setCreating(true)}>New universe</Button> : undefined}
          />
        }
      >
        {() => (
          <>
            <Readouts
              items={[
                { label: 'Root universes', value: stats.roots },
                { label: 'Nested universes', value: universes.length - stats.roots, note: `${stats.byAgent} by agents · ${stats.byExp} by experiments` },
                { label: 'Maximum depth', value: stats.deepest },
                { label: 'Running', value: universes.filter((u) => u.status === 'running').length, note: `${universes.filter((u) => u.status === 'terminated').length} terminated` },
              ]}
            />

            <div className={layout.gridMainAside}>
              <Panel title="Hierarchy" subtitle="ordered by creation tick" flushBody>
                <div className={s.header} aria-hidden="true">
                  <span>Universe</span>
                  <span>Status</span>
                  <span className={s.num}>Alive</span>
                  <span className={s.num}>Gen</span>
                  <span className={s.num}>Tick</span>
                </div>
                <div className={s.tree} role="tree" aria-label="Universe hierarchy">
                  {rows.map((r) => (
                    <button
                      key={r.universe.id}
                      type="button"
                      role="treeitem"
                      aria-level={r.depth + 1}
                      aria-selected={selected?.id === r.universe.id}
                      className={cn(s.node, selected?.id === r.universe.id && s.nodeSelected, (r.universe.status === 'terminated' || r.universe.status === 'archived') && s.nodeTerminated, r.depth === 0 && s.depth0)}
                      onClick={() => navigate(`/realities/${r.universe.id}`)}
                    >
                      <span className={s.nodeHead}>
                        <span className={s.indent} aria-hidden="true">
                          {r.guides.map((continues, i) => (
                            <span key={i} className={cn(s.indentCell, !continues && s.blank)} />
                          ))}
                          {r.depth > 0 && <span className={cn(s.indentCell, s.branch, r.isLast && s.last)} />}
                        </span>
                        <span className={s.depthMark} title={`Depth ${r.depth}`}>
                          {r.depth}
                        </span>
                        <span className={s.code}>{r.universe.code}</span>
                        <span className={s.name}>{r.universe.name}</span>
                      </span>
                      <StatusLabel tone={universeTone[r.universe.status]}>{titleCase(r.universe.status)}</StatusLabel>
                      <span className={s.num}>{fmtInt(r.universe.population.alive)}</span>
                      <span className={s.num}>{r.universe.population.generations}</span>
                      <span className={s.num}>{fmtTick(r.universe.clock.tick)}</span>
                    </button>
                  ))}
                </div>
              </Panel>

              {selected ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)', minWidth: 0 }}>
                  <Panel
                    title={`${selected.code} ${selected.name}`}
                    subtitle={`depth ${selected.lineage.depth}`}
                    actions={
                      <>
                        {live && selected.status !== 'archived' && (
                          <Button size="sm" variant="ghost" onClick={archive} disabled={archiving} title="Stop this universe permanently and hide it from the hierarchy">
                            {archiving ? 'Archiving…' : 'Archive'}
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          icon="universe"
                          onClick={() => {
                            setActive(selected.id);
                            navigate(`/universe/${selected.id}`);
                          }}
                        >
                          Open in Universe
                        </Button>
                      </>
                    }
                  >
                    {actionError && (
                      <div className="faint" style={{ color: 'var(--acc-attn)', fontSize: 'var(--fs-12)', marginBottom: 'var(--sp-2)' }}>
                        {actionError}
                      </div>
                    )}
                    <div className={s.pathRow} style={{ marginBottom: 'var(--sp-3)' }}>
                      {ancestors.map((a) => (
                        <span key={a.id} style={{ display: 'contents' }}>
                          <Link to={`/realities/${a.id}`} className="linkish">
                            {a.code}
                          </Link>
                          <span className={s.pathSep}>›</span>
                        </span>
                      ))}
                      <span style={{ color: 'var(--fg-0)' }}>{selected.code}</span>
                    </div>
                    <DataList
                      dense
                      rows={[
                        { label: 'Status', value: <StatusLabel tone={universeTone[selected.status]}>{titleCase(selected.status)}</StatusLabel>, mono: false },
                        { label: 'Generation', value: selected.population.generations },
                        { label: 'Population', value: `${fmtInt(selected.population.alive)} alive · ${fmtInt(selected.population.total)} total` },
                        { label: 'Tick', value: fmtTick(selected.clock.tick) },
                        { label: 'Extent', value: `${selected.world.width} × ${selected.world.height}` },
                        { label: 'Seed', value: selected.world.seed },
                        ...(selected.mode ? [{ label: 'Mode', value: selected.mode }] : []),
                        ...(selected.modelRef ? [{ label: 'Model', value: selected.modelRef }] : []),
                        ...(selected.computeShare !== undefined && selected.computeShare < 1 ? [{ label: 'Compute share', value: `${Math.round(selected.computeShare * 100)}%` }] : []),
                        { label: 'Children', value: selected.childIds.length },
                        { label: 'Civilization', value: selected.civilizationStage ? <Tag>{civilizationStageLabel[selected.civilizationStage]}</Tag> : '—', mono: false },
                      ]}
                    />
                  </Panel>

                  <Panel title="Creation history" subtitle="how this reality came to exist">
                    <div className={s.history}>
                      <div className={s.historyItem}>
                        <span className={s.historyDot} />
                        <div>
                          <div className={s.historyBody}>
                            Instantiated by <strong style={{ fontWeight: 500 }}>{selected.lineage.createdBy.label}</strong>
                            {selected.lineage.parentId && byId.get(selected.lineage.parentId) && (
                              <>
                                {' '}
                                inside{' '}
                                <Link to={`/realities/${selected.lineage.parentId}`} className="linkish">
                                  {byId.get(selected.lineage.parentId)!.code} {byId.get(selected.lineage.parentId)!.name}
                                </Link>
                              </>
                            )}
                            .
                          </div>
                          <div className={s.historyMeta}>
                            {selected.lineage.parentId ? `parent tick ${fmtTick(selected.lineage.createdAtTick)}` : 'root'} · {fmtDateTime(selected.lineage.createdAt)}
                          </div>
                        </div>
                      </div>
                      {selected.lineage.createdBy.kind === 'agent' && selected.lineage.createdBy.id && (
                        <div className={s.historyItem}>
                          <span className={s.historyDot} />
                          <div>
                            <div className={s.historyBody}>
                              Creator is an agent of the parent universe —{' '}
                              <Link to={`/agents/${selected.lineage.createdBy.id}`} className="linkish">
                                inspect {selected.lineage.createdBy.id.toUpperCase()}
                              </Link>
                              .
                            </div>
                          </div>
                        </div>
                      )}
                      {selected.lineage.createdBy.kind === 'experiment' && selected.lineage.createdBy.id && (
                        <div className={s.historyItem}>
                          <span className={s.historyDot} />
                          <div>
                            <div className={s.historyBody}>
                              Created as a run of{' '}
                              <Link to={`/experiments/${selected.lineage.createdBy.id}`} className="linkish">
                                {selected.lineage.createdBy.label}
                              </Link>
                              .
                            </div>
                          </div>
                        </div>
                      )}
                      <ResourceBoundary resource={events} isEmpty={(d) => d.length === 0} empty={null} loadingLines={1}>
                        {(data) =>
                          data
                            .filter((e) => e.category === 'universe' || e.category === 'system')
                            .slice(0, 6)
                            .map((e) => (
                              <div key={e.id} className={s.historyItem}>
                                <span className={s.historyDot} />
                                <div>
                                  <div className={s.historyBody}>{e.summary}</div>
                                  <div className={s.historyMeta}>tick {fmtTick(e.tick)}</div>
                                </div>
                              </div>
                            ))
                        }
                      </ResourceBoundary>
                    </div>
                  </Panel>
                </div>
              ) : (
                <Panel title="Detail">
                  <EmptyState title="Select a universe" body="Choose a node in the hierarchy to see its identity, population, status and creation history." />
                </Panel>
              )}
            </div>
          </>
        )}
      </ResourceBoundary>
    </Page>
  );
}
