import { useState } from 'react';
import { Link } from 'react-router';
import type { Agent, Universe } from '@/domain';
import type { EntityMarker, WorldSnapshot } from '@/viewport/types';
import { Inspector, InspectorSection } from '@/components/shell/Inspector';
import { DataList, Meter, Tabs, Tag, StatusLabel, Button } from '@/components/ui';
import { fmtCoord, fmtDateTime, fmtFixed, fmtInt, fmtPct, fmtTick, titleCase } from '@/lib/format';
import { agentTone, universeTone } from '@/lib/status';
import s from './UniversePage.module.css';

type TabKey = 'world' | 'population' | 'selection';

export interface UniverseInspectorProps {
  open: boolean;
  onClose: () => void;
  universe: Universe | null;
  snapshot: WorldSnapshot | null;
  selected: EntityMarker | null;
  selectedAgent: Agent | null;
  onCenterSelected: () => void;
  onClearSelection: () => void;
}

export function UniverseInspector({ open, onClose, universe, snapshot, selected, selectedAgent, onCenterSelected, onClearSelection }: UniverseInspectorProps) {
  const [tab, setTab] = useState<TabKey>('world');
  // Jump to the selection tab when something is selected.
  const [lastSelected, setLastSelected] = useState<string | null>(null);
  if (selected && selected.id !== lastSelected) {
    setLastSelected(selected.id);
    setTab('selection');
  } else if (!selected && lastSelected) {
    setLastSelected(null);
  }

  return (
    <Inspector title={universe ? `${universe.code} ${universe.name}` : 'Inspector'} open={open} onClose={onClose}>
      <Tabs<TabKey>
        aria-label="Inspector tabs"
        value={tab}
        onChange={setTab}
        items={[
          { value: 'world', label: 'World' },
          { value: 'population', label: 'Population' },
          { value: 'selection', label: 'Selection', count: selected ? 1 : undefined },
        ]}
      />

      {!universe && <div className={s.selectionEmpty}>Select a universe to inspect its conditions.</div>}

      {universe && tab === 'world' && (
        <>
          <InspectorSection title="Status">
            <DataList
              dense
              rows={[
                { label: 'State', value: <StatusLabel tone={universeTone[universe.status]}>{titleCase(universe.status)}</StatusLabel>, mono: false },
                { label: 'Tick', value: fmtTick(universe.clock.tick) },
                { label: 'Rate', value: universe.clock.rate > 0 ? `${universe.clock.rate} t/s` : 'halted' },
                { label: 'Observed', value: fmtDateTime(universe.clock.observedAt) },
              ]}
            />
          </InspectorSection>
          <InspectorSection title="Geometry">
            <DataList
              dense
              rows={[
                { label: 'Extent', value: `${universe.world.width} × ${universe.world.height}` },
                { label: 'Cell size', value: snapshot ? `${snapshot.cellSize} u` : '—' },
                { label: 'Seed', value: universe.world.seed },
                { label: 'Depth', value: universe.lineage.depth },
              ]}
            />
          </InspectorSection>
          <InspectorSection title="Conditions" meta="normalised">
            <div className={s.fieldRows}>
              {universe.world.fields.map((f) => (
                <div key={f.key} className={s.fieldRow}>
                  <span>{f.label}</span>
                  <Meter value={f.value} format={(v) => fmtFixed(v, 2)} />
                </div>
              ))}
            </div>
          </InspectorSection>
          <InspectorSection title="Lineage">
            <DataList
              dense
              alignLeft
              rows={[
                { label: 'Parent', value: universe.lineage.parentId ? <Link to={`/realities/${universe.lineage.parentId}`} className="linkish">{universe.lineage.parentId}</Link> : 'root', mono: true },
                { label: 'Created by', value: universe.lineage.createdBy.label, mono: false },
                { label: 'At tick', value: fmtTick(universe.lineage.createdAtTick) },
                { label: 'Children', value: universe.childIds.length },
              ]}
            />
          </InspectorSection>
        </>
      )}

      {universe && tab === 'population' && (
        <>
          <InspectorSection title="Counts">
            <DataList
              dense
              rows={[
                { label: 'Alive', value: fmtInt(universe.population.alive) },
                { label: 'Total recorded', value: fmtInt(universe.population.total) },
                { label: 'Born', value: fmtInt(universe.population.born) },
                { label: 'Died', value: fmtInt(universe.population.died) },
                { label: 'Generations', value: universe.population.generations },
              ]}
            />
          </InspectorSection>
          <InspectorSection title="Means">
            <div className={s.fieldRows}>
              <div className={s.fieldRow}>
                <span>Energy</span>
                <Meter value={universe.population.meanEnergy} format={(v) => fmtFixed(v, 2)} tone="live" />
              </div>
              <div className={s.fieldRow}>
                <span>Age</span>
                <span className="mono" style={{ textAlign: 'right', color: 'var(--fg-1)' }}>
                  {fmtInt(universe.population.meanAge)} t
                </span>
              </div>
            </div>
          </InspectorSection>
          <InspectorSection title="In snapshot" meta={snapshot ? `tick ${fmtTick(snapshot.tick)}` : undefined}>
            {snapshot ? (
              <DataList
                dense
                rows={(['agent', 'structure', 'resource', 'portal'] as const).map((k) => ({
                  label: titleCase(k) + 's',
                  value: snapshot.entities.filter((e) => e.kind === k).length,
                }))}
              />
            ) : (
              <div className="faint" style={{ fontSize: 'var(--fs-12)' }}>
                No snapshot available.
              </div>
            )}
          </InspectorSection>
        </>
      )}

      {universe && tab === 'selection' && (
        <>
          {!selected && (
            <div className={s.selectionEmpty}>
              Nothing selected. Use the select tool and click a marker in the viewport. Agents appear as circles, structures as squares, resources as diamonds and portals to child universes as nested squares.
            </div>
          )}
          {selected && (
            <>
              <InspectorSection
                title={<span className={s.kindLabel}>{selected.kind}</span>}
                meta={
                  <span style={{ display: 'inline-flex', gap: 4 }}>
                    <Button size="sm" variant="ghost" icon="fit" onClick={onCenterSelected}>
                      Centre
                    </Button>
                    <Button size="sm" variant="ghost" icon="close" onClick={onClearSelection}>
                      Clear
                    </Button>
                  </span>
                }
              >
                <DataList
                  dense
                  rows={[
                    { label: 'Id', value: selected.id.toUpperCase() },
                    { label: 'Position', value: fmtCoord(selected.x, selected.y) },
                    { label: selected.kind === 'agent' ? 'Energy' : selected.kind === 'resource' ? 'Remaining' : 'Condition', value: fmtPct(selected.level) },
                  ]}
                />
              </InspectorSection>

              {selected.kind === 'agent' && selectedAgent && (
                <>
                  <InspectorSection title="Agent" meta={<Link to={`/agents/${selectedAgent.id}`} className="linkish">Open in explorer</Link>}>
                    <DataList
                      dense
                      rows={[
                        { label: 'Name', value: selectedAgent.name, mono: false },
                        { label: 'Status', value: <StatusLabel tone={agentTone[selectedAgent.status]}>{titleCase(selectedAgent.status)}</StatusLabel>, mono: false },
                        { label: 'Generation', value: selectedAgent.generation },
                        { label: 'Age', value: `${fmtInt(selectedAgent.age)} t` },
                        { label: 'Relationships', value: selectedAgent.relationships.length },
                        { label: 'Knowledge', value: selectedAgent.knowledge.length },
                      ]}
                    />
                  </InspectorSection>
                  <InspectorSection title="Traits">
                    <div className={s.fieldRows}>
                      {selectedAgent.traits.map((t) => (
                        <div key={t.key} className={s.fieldRow}>
                          <span>{t.label}</span>
                          <Meter value={t.value} format={(v) => fmtFixed(v, 2)} />
                        </div>
                      ))}
                    </div>
                  </InspectorSection>
                </>
              )}

              {selected.kind === 'portal' && (
                <InspectorSection title="Portal">
                  <div className="faint" style={{ fontSize: 'var(--fs-12)', lineHeight: 1.5 }}>
                    Entry point to a child universe. <Link to={`/realities/${selected.label ?? ''}`} className="linkish">View in Recursive Realities</Link>.
                  </div>
                </InspectorSection>
              )}

              {(selected.kind === 'structure' || selected.kind === 'resource') && (
                <InspectorSection title="Detail">
                  <div className="faint" style={{ fontSize: 'var(--fs-12)' }}>
                    <Tag>{selected.kind}</Tag> markers carry only position and level in the current snapshot schema.
                  </div>
                </InspectorSection>
              )}
            </>
          )}
        </>
      )}
    </Inspector>
  );
}
