import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import type { Evidence, Experiment, Hypothesis, HypothesisState } from '@/domain';
import { useUniverseContext } from '@/app/universeContext';
import { useExperiments, useHypotheses } from '@/api/hooks';
import { useChrome } from '@/store/chromeStore';
import { Page } from '@/components/shell/AppShell';
import { Select, StatusLabel, Tag, Meter, Table, EmptyState, ResourceBoundary, Tabs, Panel, DataList, type Column } from '@/components/ui';
import { fmtPct, fmtSigned, fmtTick, titleCase } from '@/lib/format';
import { hypothesisTone, experimentTone } from '@/lib/status';
import { cn } from '@/lib/cn';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { ProvenanceNote, ProvenanceTag } from './ProvenanceTag';
import layout from '../shared/layout.module.css';
import s from './ObservatoryPage.module.css';

type StateFilter = 'all' | HypothesisState;
type TabKey = 'evidence' | 'reasoning' | 'experiments';

export default function ObservatoryPage() {
  const { hypothesisId } = useParams();
  const navigate = useNavigate();
  const { universes, byId: universesById } = useUniverseContext();
  const hypRes = useHypotheses();
  const expRes = useExperiments();

  const [stateFilter, setStateFilter] = useState<StateFilter>('all');
  const [universeFilter, setUniverseFilter] = useState('all');

  const all = useMemo(() => hypRes.data ?? [], [hypRes.data]);
  const filtered = useMemo(
    () => all.filter((h) => (stateFilter === 'all' || h.state === stateFilter) && (universeFilter === 'all' || h.universeId === universeFilter)),
    [all, stateFilter, universeFilter],
  );
  const selected = hypothesisId ? (all.find((h) => h.id === hypothesisId) ?? null) : null;

  useChrome({
    detail: selected ? selected.title : 'Hypotheses',
    statusLeft: hypRes.data ? `${filtered.length} of ${all.length} hypotheses` : null,
  });

  return (
    <Page flush>
      <div className={layout.masterDetail}>
        <aside className={layout.master} aria-label="Hypotheses">
          <div className={layout.masterToolbar}>
            <Select
              size_="sm"
              aria-label="Filter by state"
              value={stateFilter}
              onChange={(e) => setStateFilter(e.currentTarget.value as StateFilter)}
              options={[
                { value: 'all', label: 'Any state' },
                ...(['proposed', 'testing', 'supported', 'refuted', 'withdrawn'] as HypothesisState[]).map((st) => ({ value: st, label: titleCase(st) })),
              ]}
            />
            <Select
              size_="sm"
              aria-label="Filter by universe"
              value={universeFilter}
              onChange={(e) => setUniverseFilter(e.currentTarget.value)}
              options={[{ value: 'all', label: 'All universes' }, ...universes.map((u) => ({ value: u.id, label: `${u.code} ${u.name}` }))]}
            />
          </div>
          <div className={layout.masterList}>
            <ResourceBoundary
              resource={hypRes}
              isEmpty={(d) => d.length === 0}
              empty={<EmptyState icon="observatory" title="No hypotheses" body="Hypotheses proposed by agents or operators will be listed here together with their evidence and reasoning history." />}
            >
              {() =>
                filtered.length === 0 ? (
                  <EmptyState title="No matches" body="Adjust the filters." />
                ) : (
                  filtered.map((h) => (
                    <button key={h.id} type="button" className={cn(s.hypItem, selected?.id === h.id && s.hypSelected)} onClick={() => navigate(`/observatory/${h.id}`)} aria-pressed={selected?.id === h.id}>
                      <div className={s.hypTitleRow}>
                        <span className={s.hypTitle}>{h.title}</span>
                        <span className={s.hypTags}>
                          {h.existential && <Tag tone="attn" title="Claim about the nature of the world itself">existential</Tag>}
                          <ProvenanceTag provenance={h.provenance} />
                          <StatusLabel tone={hypothesisTone[h.state]}>{titleCase(h.state)}</StatusLabel>
                        </span>
                      </div>
                      <Meter value={h.confidence} tone={hypothesisTone[h.state] === 'neutral' ? undefined : hypothesisTone[h.state]} />
                      <div className={s.hypMeta}>
                        <span>{h.id.toUpperCase()}</span>
                        <span>{universesById.get(h.universeId)?.code ?? h.universeId}</span>
                        <span>{h.evidence.length} evidence</span>
                        <span>{h.reasoning.length} steps</span>
                      </div>
                    </button>
                  ))
                )
              }
            </ResourceBoundary>
          </div>
        </aside>

        {selected ? (
          <HypothesisDetail key={selected.id} hyp={selected} experiments={expRes.data ?? []} />
        ) : (
          <div className={layout.detail}>
            <EmptyState
              center
              icon="observatory"
              title={hypothesisId ? 'Hypothesis not found' : 'Select a hypothesis'}
              body={hypothesisId ? `No hypothesis ${hypothesisId.toUpperCase()} is known to the current data source.` : 'Choose a hypothesis to review its statement, evidence, linked experiments and reasoning history.'}
            />
          </div>
        )}
      </div>
    </Page>
  );
}

function HypothesisDetail({ hyp, experiments }: { hyp: Hypothesis; experiments: Experiment[] }) {
  const [tab, setTab] = useState<TabKey>('evidence');
  const { byId } = useUniverseContext();
  const universe = byId.get(hyp.universeId);
  const linked = experiments.filter((e) => hyp.experimentIds.includes(e.id));

  const netWeight = hyp.evidence.reduce((n, e) => n + e.weight, 0);

  // Below ~1100px the detail pane is too narrow for five columns; fold kind/source under the summary.
  const compact = useMediaQuery('(max-width: 1100px)');
  const evidenceCols: Column<Evidence>[] = compact
    ? [
        { key: 'tick', header: 'Tick', num: true, render: (e) => fmtTick(e.tick), sortValue: (e) => e.tick, width: 80 },
        {
          key: 'summary',
          header: 'Evidence',
          fill: true,
          render: (e) => (
            <div style={{ whiteSpace: 'normal', minWidth: 160 }}>
              <div style={{ color: 'var(--fg-1)' }}>{e.summary}</div>
              <div className="faint" style={{ marginTop: 2, fontSize: 'var(--fs-11)' }}>
                {e.kind} · <span className="mono">{e.source}</span>
                {e.verifiedByMechanics && (
                  <>
                    {' '}
                    · <Tag tone="live" title="Value produced by the mechanics, not asserted by a model">verified</Tag>
                  </>
                )}
              </div>
            </div>
          ),
        },
        { key: 'weight', header: 'Weight', render: (e) => <Meter value={e.weight} bipolar tone={e.weight < 0 ? 'crit' : 'live'} style={{ width: 84 }} />, sortValue: (e) => e.weight },
      ]
    : [
        { key: 'tick', header: 'Tick', num: true, render: (e) => fmtTick(e.tick), sortValue: (e) => e.tick, width: 90 },
        { key: 'kind', header: 'Kind', render: (e) => <Tag>{e.kind}</Tag>, sortValue: (e) => e.kind },
        { key: 'source', header: 'Source', mono: true, render: (e) => e.source, sortValue: (e) => e.source },
        {
          key: 'verified',
          header: 'Verified',
          render: (e) =>
            e.verifiedByMechanics ? (
              <Tag tone="live" title="Value produced by the mechanics, not asserted by a model">
                mechanics
              </Tag>
            ) : (
              <span className="faint">—</span>
            ),
          sortValue: (e) => (e.verifiedByMechanics ? 1 : 0),
        },
        { key: 'summary', header: 'Summary', render: (e) => <span style={{ whiteSpace: 'normal', color: 'var(--fg-1)' }}>{e.summary}</span>, fill: true },
        { key: 'weight', header: 'Weight', render: (e) => <Meter value={e.weight} bipolar tone={e.weight < 0 ? 'crit' : 'live'} style={{ width: 120 }} />, sortValue: (e) => e.weight },
      ];

  return (
    <div className={layout.detail}>
      <header className={layout.detailHeader}>
        <div style={{ minWidth: 0 }}>
          <h2 className={layout.detailTitle}>
            {hyp.title}
            <span className={layout.detailCode}>{hyp.id.toUpperCase()}</span>
          </h2>
          <div className={layout.detailMeta}>
            <StatusLabel tone={hypothesisTone[hyp.state]}>{titleCase(hyp.state)}</StatusLabel>
            <span>
              Proposed tick {fmtTick(hyp.proposedAtTick)} by{' '}
              {hyp.proposedBy.kind === 'agent' && hyp.proposedBy.id ? (
                <Link to={`/agents/${hyp.proposedBy.id}`} className="linkish">
                  {hyp.proposedBy.label}
                </Link>
              ) : (
                hyp.proposedBy.label
              )}
            </span>
            {universe && (
              <Link to={`/realities/${universe.id}`} className="linkish">
                {universe.code} {universe.name}
              </Link>
            )}
          </div>
        </div>
        <div className={s.confidenceBlock}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-end' }}>
            <span className="caps">Confidence</span>
            <span className={s.confidenceValue}>{fmtPct(hyp.confidence)}</span>
          </div>
        </div>
      </header>

      <div className={layout.detailBody}>
        <p className={s.statement}>{hyp.statement}</p>
        <ProvenanceNote provenance={hyp.provenance} existential={hyp.existential} />

        <Tabs<TabKey>
          aria-label="Hypothesis detail"
          value={tab}
          onChange={setTab}
          items={[
            { value: 'evidence', label: 'Evidence', count: hyp.evidence.length },
            { value: 'reasoning', label: 'Reasoning history', count: hyp.reasoning.length },
            { value: 'experiments', label: 'Linked experiments', count: linked.length },
          ]}
        />

        {tab === 'evidence' &&
          (hyp.evidence.length === 0 ? (
            <EmptyState title="No evidence" body="Nothing has been recorded for or against this hypothesis." />
          ) : (
            <>
              <DataList
                dense
                rows={[
                  { label: 'Items', value: hyp.evidence.length },
                  { label: 'Supporting', value: hyp.evidence.filter((e) => e.weight > 0).length },
                  { label: 'Against', value: hyp.evidence.filter((e) => e.weight < 0).length },
                  { label: 'Net weight', value: <span className={cn(netWeight > 0 ? s.deltaUp : netWeight < 0 ? s.deltaDown : undefined)}>{fmtSigned(netWeight)}</span> },
                ]}
                alignLeft
                className={undefined}
              />
              <Table aria-label="Evidence" rows={hyp.evidence} rowKey={(e) => e.id} columns={evidenceCols} initialSort={{ key: 'tick', dir: 'asc' }} />
            </>
          ))}

        {tab === 'reasoning' &&
          (hyp.reasoning.length === 0 ? (
            <EmptyState title="No reasoning steps" body="The reasoning trace is empty." />
          ) : (
            <div className={s.reasoning}>
              {hyp.reasoning.map((step, i) => {
                const prev = i > 0 ? hyp.reasoning[i - 1].confidence : null;
                const delta = prev !== null ? step.confidence - prev : null;
                return (
                  <div key={step.id} className={s.step}>
                    <span className={s.stepIndex}>{String(step.index).padStart(2, '0')}</span>
                    <span className={s.stepTick}>{fmtTick(step.tick)}</span>
                    <div>
                      <div className={s.stepStatement}>{step.statement}</div>
                      <div className={s.stepActor}>
                        {step.actor.kind === 'agent' && step.actor.id ? (
                          <Link to={`/agents/${step.actor.id}`} className="linkish">
                            {step.actor.label}
                          </Link>
                        ) : (
                          step.actor.label
                        )}{' '}
                        · {step.actor.kind}
                      </div>
                    </div>
                    <div className={s.stepConf}>
                      <span>{fmtPct(step.confidence)}</span>
                      {delta !== null && <span className={cn(s.delta, delta > 0 && s.deltaUp, delta < 0 && s.deltaDown)}>{fmtSigned(delta * 100, 0)} pt</span>}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}

        {tab === 'experiments' &&
          (linked.length === 0 ? (
            <EmptyState title="No linked experiments" body="No experiment has been configured to test this hypothesis. Experiments can be linked from the Experiments section." />
          ) : (
            <div className={layout.grid2}>
              {linked.map((e) => (
                <Panel key={e.id} title={e.name} subtitle={e.id.toUpperCase()} actions={<StatusLabel tone={experimentTone[e.status]}>{titleCase(e.status)}</StatusLabel>}>
                  <p className={layout.prose} style={{ fontSize: 'var(--fs-12)', color: 'var(--fg-2)' }}>
                    {e.objective}
                  </p>
                  <div style={{ marginTop: 'var(--sp-3)' }}>
                    <Link to={`/experiments/${e.id}`} className="linkish" style={{ fontSize: 'var(--fs-12)' }}>
                      Open experiment
                    </Link>
                  </div>
                </Panel>
              ))}
            </div>
          ))}
      </div>
    </div>
  );
}
