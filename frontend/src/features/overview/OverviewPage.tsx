import { useMemo } from 'react';
import { Link, useNavigate } from 'react-router';
import type { Universe } from '@/domain';
import { useUniverseContext } from '@/app/universeContext';
import { useEvents } from '@/api/hooks';
import { useChrome } from '@/store/chromeStore';
import { Page } from '@/components/shell/AppShell';
import { Readouts, Panel, Table, StatusLabel, Tag, Meter, EmptyState, ResourceBoundary, Button, type Column } from '@/components/ui';
import { fmtCompact, fmtInt, fmtTick, titleCase } from '@/lib/format';
import { civilizationStageLabel, civilizationStages, universeTone } from '@/lib/status';
import { SampleNotice } from '../shared/SampleNotice';
import { EventList } from '../shared/EventList';
import layout from '../shared/layout.module.css';
import s from './OverviewPage.module.css';

const stageOrder = civilizationStages;
const stageIndex = (stage: Universe['civilizationStage']) => (stage ? stageOrder.indexOf(stage) : -1);
const stageName = (stage: Universe['civilizationStage']) => (stage ? civilizationStageLabel[stage] : null);

export default function OverviewPage() {
  useChrome({ detail: 'Command centre' });
  const { resource, universes, setActive } = useUniverseContext();
  const events = useEvents({ limit: 12 });
  const navigate = useNavigate();

  const summary = useMemo(() => {
    const running = universes.filter((u) => u.status === 'running');
    const alive = universes.reduce((n, u) => n + u.population.alive, 0);
    const total = universes.reduce((n, u) => n + u.population.total, 0);
    const deepest = universes.reduce((d, u) => Math.max(d, u.lineage.depth), 0);
    const mostAdvanced = universes.reduce<Universe | null>((best, u) => (stageIndex(u.civilizationStage) > stageIndex(best?.civilizationStage ?? null) ? u : best), null);
    return { running, alive, total, deepest, mostAdvanced };
  }, [universes]);

  const columns: Column<Universe>[] = [
    { key: 'code', header: 'Code', mono: true, render: (u) => u.code, sortValue: (u) => u.code, width: 64 },
    { key: 'name', header: 'Universe', render: (u) => <span style={{ color: 'var(--fg-0)' }}>{u.name}</span>, sortValue: (u) => u.name, fill: true },
    { key: 'status', header: 'Status', render: (u) => <StatusLabel tone={universeTone[u.status]}>{titleCase(u.status)}</StatusLabel>, sortValue: (u) => u.status },
    { key: 'depth', header: 'Depth', num: true, render: (u) => u.lineage.depth, sortValue: (u) => u.lineage.depth },
    { key: 'tick', header: 'Tick', num: true, render: (u) => fmtTick(u.clock.tick), sortValue: (u) => u.clock.tick },
    { key: 'alive', header: 'Alive', num: true, render: (u) => fmtInt(u.population.alive), sortValue: (u) => u.population.alive },
    { key: 'gen', header: 'Gen', num: true, render: (u) => u.population.generations, sortValue: (u) => u.population.generations },
    { key: 'stage', header: 'Civilization', render: (u) => (u.civilizationStage ? <Tag>{stageName(u.civilizationStage)}</Tag> : <span className="faint">—</span>), sortValue: (u) => stageIndex(u.civilizationStage) },
  ];

  return (
    <Page title="Overview" lede="Status of all universes under observation, as last reported by the engine.">
      <SampleNotice />

      <ResourceBoundary
        resource={resource}
        isEmpty={(d) => d.length === 0}
        empty={
          <EmptyState
            icon="universe"
            title="No universes"
            body="The engine has not registered any universes. Once a simulation is started, its status, population and events will appear here."
            actions={
              <Button size="sm" onClick={() => navigate('/experiments')}>
                Open experiments
              </Button>
            }
          />
        }
      >
        {() => (
          <>
            <Readouts
              items={[
                { label: 'Universes', value: universes.length, note: `${summary.running.length} running` },
                { label: 'Population alive', value: fmtCompact(summary.alive), note: `${fmtCompact(summary.total)} total recorded` },
                { label: 'Active agents', value: fmtCompact(summary.running.reduce((n, u) => n + u.population.alive, 0)), note: 'in running universes' },
                {
                  label: 'Simulation time',
                  value: summary.running[0] ? fmtTick(summary.running[0].clock.tick) : '—',
                  unit: 'ticks',
                  note: summary.running[0] ? `${summary.running[0].code} ${summary.running[0].name}` : 'no running universe',
                },
                { label: 'Recursion depth', value: summary.deepest, note: 'deepest nested universe' },
                {
                  label: 'Civilization',
                  value: stageName(summary.mostAdvanced?.civilizationStage ?? null) ?? '—',
                  note: summary.mostAdvanced ? `${summary.mostAdvanced.code} most advanced` : undefined,
                },
              ]}
            />

            <div className={layout.gridMainAside}>
              <div className={s.stack}>
                <Panel title="Universes" subtitle={`${universes.length} registered`} flushBody>
                  <Table
                    columns={columns}
                    rows={universes}
                    rowKey={(u) => u.id}
                    onRowClick={(u) => {
                      setActive(u.id);
                      navigate(`/universe/${u.id}`);
                    }}
                    rowClassName={(u) => (u.status === 'terminated' || u.status === 'archived' ? 'faint' : undefined)}
                    aria-label="Universes"
                  />
                </Panel>

                <Panel title="Civilization progress" subtitle="stage per universe">
                  <div className={s.progressList}>
                    {universes
                      .filter((u) => u.status !== 'terminated' && u.status !== 'archived')
                      .map((u) => {
                        const idx = stageIndex(u.civilizationStage);
                        return (
                          <div key={u.id} className={s.progressRow}>
                            <Link to={`/civilization?u=${u.id}`} className={s.progressName}>
                              <span className="mono faint">{u.code}</span> {u.name}
                            </Link>
                            <Meter value={Math.max(0, idx) / (stageOrder.length - 1)} format={() => stageName(u.civilizationStage) ?? 'initialising'} tone={idx > 0 ? 'depth' : undefined} />
                          </div>
                        );
                      })}
                  </div>
                </Panel>
              </div>

              <Panel title="Recent events" subtitle="across all universes" flushBody actions={<Button size="sm" variant="ghost" iconRight="arrowUpRight" onClick={() => navigate('/universe')}>Universe</Button>}>
                <ResourceBoundary resource={events} isEmpty={(d) => d.length === 0} empty={<EmptyState title="No events" body="Engine events will stream here once a universe is running." />}>
                  {(data) => <EventList events={data} />}
                </ResourceBoundary>
              </Panel>
            </div>
          </>
        )}
      </ResourceBoundary>
    </Page>
  );
}
