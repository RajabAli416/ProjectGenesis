import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import type { Experiment, ExperimentRun, ExperimentStatus, Hypothesis } from '@/domain';
import { useUniverseContext } from '@/app/universeContext';
import { useExperiments, useHypotheses, usePolling, useReloadOnSignal, useSettings } from '@/api/hooks';
import { dataSource, mutations } from '@/api';
import { useConnectionStore } from '@/store/connectionStore';
import { useChrome } from '@/store/chromeStore';
import { Page } from '@/components/shell/AppShell';
import { Table, StatusLabel, Tag, EmptyState, ResourceBoundary, Select, Tabs, DataList, Button, type Column } from '@/components/ui';
import { fmtDateTime, titleCase } from '@/lib/format';
import { experimentTone, hypothesisTone } from '@/lib/status';
import { cn } from '@/lib/cn';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { NewExperimentDialog } from './NewExperimentDialog';
import layout from '../shared/layout.module.css';
import s from './ExperimentsPage.module.css';

type StatusFilter = 'all' | ExperimentStatus;
type TabKey = 'design' | 'runs' | 'results' | 'reproducibility';

const fmtVar = (v: string | number | boolean) => (typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v));

export default function ExperimentsPage() {
  const { experimentId } = useParams();
  const navigate = useNavigate();
  const live = dataSource.kind === 'http';
  const expRes = useExperiments();
  const hypRes = useHypotheses();
  const settingsRes = useSettings();
  const [status, setStatus] = useState<StatusFilter>('all');
  const [creating, setCreating] = useState(false);

  // Experiments change state as their universes run; refresh on catalog changes and on a slow poll.
  const catalogRevision = useConnectionStore((st) => st.catalogRevision);
  useReloadOnSignal(expRes.reload, catalogRevision, 1500);
  usePolling(expRes.reload, live ? 4000 : 0);

  const all = useMemo(() => expRes.data ?? [], [expRes.data]);
  const filtered = useMemo(() => all.filter((e) => status === 'all' || e.status === status), [all, status]);
  const selected = experimentId ? (all.find((e) => e.id === experimentId) ?? null) : null;

  useChrome({ detail: selected ? selected.name : 'Configurations', statusLeft: expRes.data ? `${filtered.length} of ${all.length} experiments` : null });

  const narrow = useMediaQuery('(max-width: 900px)');
  const columns: Column<Experiment>[] = [
    { key: 'id', header: 'Id', mono: true, render: (e) => e.id.toUpperCase(), sortValue: (e) => e.id, width: 80 },
    { key: 'name', header: 'Name', render: (e) => <span style={{ color: 'var(--fg-0)' }}>{e.name}</span>, sortValue: (e) => e.name, fill: true },
    { key: 'status', header: 'Status', render: (e) => <StatusLabel tone={experimentTone[e.status]}>{titleCase(e.status)}</StatusLabel>, sortValue: (e) => e.status },
    ...(narrow
      ? []
      : ([
          { key: 'vars', header: 'Vars', num: true, render: (e) => e.variables.length, sortValue: (e) => e.variables.length },
          { key: 'runs', header: 'Runs', num: true, render: (e) => `${e.runs.length}/${e.replicates}`, sortValue: (e) => e.runs.length },
        ] satisfies Column<Experiment>[])),
  ];

  return (
    <Page flush>
      <div className={layout.masterDetail}>
        <aside className={layout.master} aria-label="Experiments">
          <div className={layout.masterToolbar}>
            <Select
              size_="sm"
              aria-label="Filter by status"
              value={status}
              onChange={(e) => setStatus(e.currentTarget.value as StatusFilter)}
              options={[{ value: 'all', label: 'Any status' }, ...(['draft', 'queued', 'running', 'complete', 'aborted'] as ExperimentStatus[]).map((st) => ({ value: st, label: titleCase(st) }))]}
            />
            <span style={{ flex: 1 }} />
            <Button size="sm" variant="outline" icon="plus" disabled={!live} title={live ? 'Design a new control/treatment experiment' : 'Creating experiments requires a connected backend'} onClick={() => setCreating(true)}>
              New
            </Button>
          </div>
          <div className={layout.masterList}>
            <ResourceBoundary
              resource={expRes}
              isEmpty={(d) => d.length === 0}
              empty={<EmptyState icon="experiments" title="No experiments" body="Experiment configurations — variables, control groups, replicates and seeds — will be listed here." />}
            >
              {() =>
                filtered.length === 0 ? (
                  <EmptyState title="No matches" body="Adjust the status filter." />
                ) : (
                  <Table compact aria-label="Experiments" columns={columns} rows={filtered} rowKey={(e) => e.id} selectedKey={selected?.id ?? null} onRowClick={(e) => navigate(`/experiments/${e.id}`)} />
                )
              }
            </ResourceBoundary>
          </div>
        </aside>

        {selected ? (
          <ExperimentDetail key={selected.id} exp={selected} hypotheses={hypRes.data ?? []} live={live} onChanged={expRes.reload} onDeleted={() => navigate('/experiments')} />
        ) : (
          <div className={layout.detail}>
            <EmptyState
              center
              icon="experiments"
              title={experimentId ? 'Experiment not found' : 'Select an experiment'}
              body={experimentId ? `No experiment ${experimentId.toUpperCase()} is known to the current data source.` : 'Choose a configuration to review its variables, control group, run history and reproducibility settings.'}
              actions={
                live && !experimentId ? (
                  <Button size="sm" variant="primary" icon="plus" onClick={() => setCreating(true)}>
                    New experiment
                  </Button>
                ) : undefined
              }
            />
          </div>
        )}
      </div>

      <NewExperimentDialog
        open={creating}
        onClose={() => setCreating(false)}
        hypotheses={hypRes.data ?? []}
        defaults={settingsRes.data}
        onCreated={(e) => {
          expRes.reload();
          navigate(`/experiments/${e.id}`);
        }}
      />
    </Page>
  );
}

function ExperimentDetail({ exp, hypotheses, live, onChanged, onDeleted }: { exp: Experiment; hypotheses: Hypothesis[]; live: boolean; onChanged: () => void; onDeleted: () => void }) {
  const [tab, setTab] = useState<TabKey>('design');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { byId } = useUniverseContext();
  const control = exp.controlUniverseId ? byId.get(exp.controlUniverseId) : null;
  const linkedHyps = hypotheses.filter((h) => exp.hypothesisIds.includes(h.id));
  const finishedRuns = exp.runs.filter((r) => r.metrics && Object.keys(r.metrics).length > 0);

  const act = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${label} failed`);
    } finally {
      setBusy(null);
    }
  };

  const universeLink = (id: string | null | undefined, label: string) =>
    id ? (
      <Link to={`/realities/${id}`} className="linkish" title={label}>
        {byId.get(id)?.code ?? id}
      </Link>
    ) : (
      <span className="faint">—</span>
    );

  const runCols: Column<ExperimentRun>[] = [
    { key: 'idx', header: '#', num: true, render: (r) => r.index, sortValue: (r) => r.index, width: 40 },
    { key: 'status', header: 'Status', render: (r) => <StatusLabel tone={experimentTone[r.status]}>{titleCase(r.status)}</StatusLabel>, sortValue: (r) => r.status },
    { key: 'seed', header: 'Seed', mono: true, render: (r) => r.seed || '—' },
    { key: 'started', header: 'Started', mono: true, render: (r) => fmtDateTime(r.startedAt), sortValue: (r) => r.startedAt },
    { key: 'finished', header: 'Finished', mono: true, render: (r) => (r.finishedAt ? fmtDateTime(r.finishedAt) : '—') },
    { key: 'control', header: 'Control', mono: true, render: (r) => universeLink(r.controlUniverseId ?? r.universeIds[0], 'Control universe') },
    { key: 'treatment', header: 'Treatment', mono: true, render: (r) => universeLink(r.treatmentUniverseId ?? r.universeIds[1], 'Treatment universe'), fill: true },
  ];

  const canStart = live && exp.status !== 'running' && exp.variables.length > 0;
  const canAbort = live && exp.status === 'running';
  const canDelete = live && exp.status !== 'running';

  return (
    <div className={layout.detail}>
      <header className={layout.detailHeader}>
        <div style={{ minWidth: 0 }}>
          <h2 className={layout.detailTitle}>
            {exp.name}
            <span className={layout.detailCode}>{exp.id.toUpperCase()}</span>
          </h2>
          <div className={layout.detailMeta}>
            <StatusLabel tone={experimentTone[exp.status]} pulse={exp.status === 'running'}>
              {titleCase(exp.status)}
            </StatusLabel>
            <span>Created {fmtDateTime(exp.createdAt)}</span>
            <span>
              {exp.replicates} replicate{exp.replicates === 1 ? '' : 's'}
            </span>
            {exp.durationTicks !== undefined && <span>{exp.durationTicks.toLocaleString()} ticks</span>}
            {exp.mode && <Tag mono>{exp.mode}</Tag>}
          </div>
        </div>
        <div className={layout.rowAside}>
          {error && (
            <span className="faint" style={{ color: 'var(--acc-crit)', fontSize: 'var(--fs-12)' }} title={error}>
              {error}
            </span>
          )}
          {canAbort ? (
            <Button size="sm" variant="outline" icon="pause" disabled={busy !== null} onClick={() => act('Abort', () => mutations.abortExperiment(exp.id))}>
              {busy === 'Abort' ? 'Aborting…' : 'Abort'}
            </Button>
          ) : (
            <Button
              size="sm"
              variant="outline"
              icon="play"
              disabled={!canStart || busy !== null}
              title={!live ? 'Starting runs requires a connected backend' : exp.variables.length === 0 ? 'Add a variable first' : `Instantiate ${exp.replicates} control/treatment pair${exp.replicates === 1 ? '' : 's'} and run to ${exp.durationTicks ?? '—'} ticks`}
              onClick={() => act('Start', () => mutations.startExperimentRun(exp.id))}
            >
              {busy === 'Start' ? 'Starting…' : exp.runs.length > 0 ? 'Run again' : 'Start run'}
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            disabled={!canDelete || busy !== null}
            title={canDelete ? 'Delete this configuration (universes it created are kept)' : 'Cannot delete while running'}
            onClick={() => {
              if (window.confirm(`Delete experiment "${exp.name}"? Universes it created are kept.`)) {
                void act('Delete', async () => {
                  await mutations.deleteExperiment(exp.id);
                  onDeleted();
                });
              }
            }}
          >
            Delete
          </Button>
        </div>
      </header>

      <div className={layout.detailBody}>
        {exp.objective && <p className={layout.prose}>{exp.objective}</p>}

        <Tabs<TabKey>
          aria-label="Experiment detail"
          value={tab}
          onChange={setTab}
          items={[
            { value: 'design', label: 'Design', count: exp.variables.length },
            { value: 'runs', label: 'Run history', count: exp.runs.length },
            { value: 'results', label: 'Results', count: finishedRuns.length },
            { value: 'reproducibility', label: 'Reproducibility' },
          ]}
        />

        {tab === 'design' && (
          <>
            <section className={layout.section}>
              <h3 className={layout.sectionTitle}>
                Control group
                {control ? (
                  <Link to={`/realities/${control.id}`} className="linkish" style={{ textTransform: 'none', letterSpacing: 0 }}>
                    {control.code} {control.name}
                  </Link>
                ) : (
                  <span style={{ textTransform: 'none', letterSpacing: 0 }}>{exp.runs.length === 0 ? 'instantiated per run from the base configuration' : 'not assigned'}</span>
                )}
              </h3>
              {exp.baseConfig && Object.keys(exp.baseConfig).length > 0 && (
                <DataList
                  dense
                  alignLeft
                  rows={Object.entries(exp.baseConfig).map(([k, v]) => ({ label: k, value: typeof v === 'object' ? JSON.stringify(v) : String(v), key: k }))}
                />
              )}
            </section>

            <section className={layout.section}>
              <h3 className={layout.sectionTitle}>Variables</h3>
              {exp.variables.length === 0 ? (
                <EmptyState title="No variables" body="This configuration does not manipulate any variable." />
              ) : (
                <div className={s.varGrid} role="table" aria-label="Variables">
                  <div className={cn(s.varHead, s.varKeyCell)} role="columnheader">
                    Variable
                  </div>
                  <div className={s.varHead} role="columnheader">
                    Control
                  </div>
                  <div className={s.varHead} role="columnheader">
                    Treatment
                  </div>
                  {exp.variables.map((v) => {
                    const differs = v.control !== v.treatment;
                    return (
                      <div key={v.key} className={s.varRow} role="row">
                        <div className={cn(s.varCell, s.varKeyCell)} role="cell">
                          <span className={s.varKey}>{v.label}</span>
                          <span className={s.varKeyCode}>{v.key}</span>
                        </div>
                        <div className={cn(s.varCell, s.varValue)} role="cell">
                          {fmtVar(v.control)}
                          {v.unit && <span className={s.varUnit}>{v.unit}</span>}
                        </div>
                        <div className={cn(s.varCell, s.varValue, differs && s.varDiff)} role="cell">
                          {fmtVar(v.treatment)}
                          {v.unit && <span className={s.varUnit}>{v.unit}</span>}
                          {!differs && <Tag>unchanged</Tag>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <section className={layout.section}>
              <h3 className={layout.sectionTitle}>Hypotheses under test</h3>
              {linkedHyps.length === 0 ? (
                <div className="faint" style={{ fontSize: 'var(--fs-12)' }}>
                  No hypothesis is linked to this experiment.
                </div>
              ) : (
                <div className={layout.rowList}>
                  {linkedHyps.map((h) => (
                    <div key={h.id} className={layout.rowItem}>
                      <div>
                        <Link to={`/observatory/${h.id}`} className={cn(layout.rowPrimary, 'linkish')}>
                          {h.title}
                        </Link>
                        <div className={layout.rowSecondary}>{h.id.toUpperCase()}</div>
                      </div>
                      <div className={layout.rowAside}>
                        <StatusLabel tone={hypothesisTone[h.state]}>{titleCase(h.state)}</StatusLabel>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        )}

        {tab === 'runs' &&
          (exp.runs.length === 0 ? (
            <EmptyState
              icon="experiments"
              title="No runs recorded"
              body={exp.status === 'draft' ? (live ? 'This configuration is a draft. Start a run to instantiate its control and treatment universes.' : 'This configuration is a draft. Runs can be started once the design is complete and a backend is connected.') : 'The experiment is configured but no run has been executed yet.'}
            />
          ) : (
            <Table aria-label="Run history" rows={exp.runs} rowKey={(r) => r.id} columns={runCols} initialSort={{ key: 'idx', dir: 'asc' }} />
          ))}

        {tab === 'results' &&
          (finishedRuns.length === 0 ? (
            <EmptyState icon="experiments" title="No results yet" body="Metrics are computed from the mechanics of each arm when a run reaches its duration. Nothing here is estimated or inferred by a model." />
          ) : (
            finishedRuns.map((r) => <RunMetrics key={r.id} run={r} />)
          ))}

        {tab === 'reproducibility' && (
          <>
            <div className={s.reproGrid}>
              <ReproItem label="Seed" value={exp.reproducibility.seed || null} />
              <ReproItem label="Deterministic" value={exp.runs.length === 0 ? null : exp.reproducibility.deterministic ? 'yes' : 'no'} />
              <ReproItem label="Engine version" value={exp.reproducibility.engineVersion} />
              <ReproItem label="State hash" value={exp.reproducibility.snapshotHash} />
            </div>
            <DataList
              alignLeft
              rows={[
                { label: 'Replicates', value: exp.replicates },
                { label: 'Seed policy', value: 'replicate seeds derived from the experiment seed; identical across re-runs', mono: false },
                {
                  label: 'Determinism claim',
                  value:
                    exp.runs.length === 0
                      ? 'decided at first run: lockstep mode with no model in the loop (or a replay/scripted provider) is reproducible bit-for-bit; anything else is not claimed'
                      : exp.reproducibility.deterministic
                        ? 'mechanics-only or replayable provider in lockstep — same seed reproduces the same state hash'
                        : 'a live model participates or the clock does not wait for decisions — outcomes vary between runs with the same seed',
                  mono: false,
                },
                { label: 'Pinned engine', value: exp.reproducibility.engineVersion ? 'yes' : 'no — recorded at first run', mono: false },
                { label: 'State hash', value: exp.reproducibility.snapshotHash ? 'identity-neutral hash of the first control arm at completion' : 'recorded when the first run completes', mono: false },
              ]}
            />
          </>
        )}
      </div>
    </div>
  );
}

const fmtMetric = (v: unknown): string => {
  if (typeof v === 'number') return Number.isInteger(v) ? v.toLocaleString() : v.toFixed(3);
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (v === null || v === undefined) return '—';
  return String(v);
};

function RunMetrics({ run }: { run: ExperimentRun }) {
  const control = run.metrics?.control ?? {};
  const treatment = run.metrics?.treatment ?? {};
  const keys = Array.from(new Set([...Object.keys(control), ...Object.keys(treatment)]));
  return (
    <section className={layout.section}>
      <h3 className={layout.sectionTitle}>
        Run {run.index}
        <span className="mono" style={{ textTransform: 'none', letterSpacing: 0 }}>
          seed {run.seed}
        </span>
      </h3>
      <div className={s.metricsGrid} role="table" aria-label={`Run ${run.index} metrics`}>
        <div className={s.varHead} role="columnheader">
          Metric
        </div>
        <div className={s.varHead} role="columnheader">
          Control
        </div>
        <div className={s.varHead} role="columnheader">
          Treatment
        </div>
        <div className={s.varHead} role="columnheader">
          Δ
        </div>
        {keys.map((k) => {
          const c = control[k];
          const t = treatment[k];
          const numeric = typeof c === 'number' && typeof t === 'number';
          const delta = numeric ? (t as number) - (c as number) : null;
          return (
            <div key={k} className={s.varRow} role="row">
              <div className={cn(s.varCell, s.varKeyCell)} role="cell">
                <span className={s.varKey}>{k.replace(/_/g, ' ')}</span>
              </div>
              <div className={cn(s.varCell, s.varValue)} role="cell">
                {fmtMetric(c)}
              </div>
              <div className={cn(s.varCell, s.varValue, delta !== 0 && s.varDiff)} role="cell">
                {fmtMetric(t)}
              </div>
              <div className={cn(s.varCell, s.varValue, delta ? s.metricDelta : undefined)} role="cell">
                {delta === null ? '—' : `${delta > 0 ? '+' : ''}${fmtMetric(delta)}`}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ReproItem({ label, value }: { label: string; value: string | null }) {
  return (
    <div className={s.reproItem}>
      <span className={s.reproLabel}>{label}</span>
      <span className={cn(s.reproValue, !value && s.reproUnset)} title={value ?? undefined}>
        {value ?? 'unset'}
      </span>
    </div>
  );
}
