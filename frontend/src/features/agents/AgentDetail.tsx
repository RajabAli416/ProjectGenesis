import { useState } from 'react';
import { Link, useNavigate } from 'react-router';
import type { Agent, DecisionRecord } from '@/domain';
import { useUniverseContext } from '@/app/universeContext';
import { useAgentDecisions, usePolling } from '@/api/hooks';
import { dataSource } from '@/api';
import { useSelectionStore } from '@/store/selectionStore';
import { DataList, Meter, Tabs, Tag, StatusLabel, Table, EmptyState, Button, ResourceBoundary, type Column } from '@/components/ui';
import { fmtAgentCode, fmtCoord, fmtFixed, fmtInt, fmtPct, fmtTick, titleCase } from '@/lib/format';
import { agentTone } from '@/lib/status';
import { cn } from '@/lib/cn';
import layout from '../shared/layout.module.css';
import s from './AgentsPage.module.css';

type TabKey = 'identity' | 'lineage' | 'relationships' | 'knowledge' | 'memory' | 'decisions';

const fmtParams = (p: Record<string, unknown> | undefined): string => {
  if (!p) return '';
  const entries = Object.entries(p);
  if (entries.length === 0) return '';
  return entries.map(([k, v]) => `${k}=${typeof v === 'number' ? (Number.isInteger(v) ? v : v.toFixed(2)) : JSON.stringify(v)}`).join(' ');
};

export function AgentDetail({ agent, byId }: { agent: Agent; byId: Map<string, Agent> }) {
  const [tab, setTab] = useState<TabKey>('identity');
  const { byId: universes } = useUniverseContext();
  const universe = universes.get(agent.universeId);
  const navigate = useNavigate();
  const selectEntity = useSelectionStore((st) => st.selectEntity);
  const live = dataSource.kind === 'http';
  const decisions = useAgentDecisions(tab === 'decisions' ? agent.id : null, 100);
  usePolling(decisions.reload, tab === 'decisions' && live && agent.status !== 'deceased' ? 4000 : 0);

  const nameOf = (id: string) => byId.get(id)?.name ?? fmtAgentCode(id);

  return (
    <div className={layout.detail}>
      <header className={layout.detailHeader}>
        <div>
          <h2 className={layout.detailTitle}>
            {agent.name}
            <span className={layout.detailCode}>{fmtAgentCode(agent.id)}</span>
          </h2>
          <div className={layout.detailMeta}>
            <StatusLabel tone={agentTone[agent.status]}>{titleCase(agent.status)}</StatusLabel>
            <span>Generation {agent.generation}</span>
            {universe && (
              <Link to={`/universe/${universe.id}`} className="linkish">
                {universe.code} {universe.name}
              </Link>
            )}
          </div>
        </div>
        <div className={layout.rowAside}>
          <Button
            size="sm"
            variant="outline"
            icon="universe"
            title="Select this agent in the universe viewport"
            onClick={() => {
              selectEntity(agent.id);
              navigate(`/universe/${agent.universeId}`);
            }}
          >
            Locate
          </Button>
        </div>
      </header>

      <Tabs<TabKey>
        aria-label="Agent detail"
        value={tab}
        onChange={setTab}
        items={[
          { value: 'identity', label: 'Identity' },
          { value: 'lineage', label: 'Lineage', count: agent.lineage.parentIds.length + agent.lineage.offspringIds.length },
          { value: 'relationships', label: 'Relationships', count: agent.relationships.length },
          { value: 'knowledge', label: 'Knowledge', count: agent.knowledge.length },
          { value: 'memory', label: 'Memory', count: agent.memory.length },
          ...(live ? [{ value: 'decisions' as const, label: 'Decisions', count: decisions.data?.length ?? agent.decisionsModel }] : []),
        ]}
      />

      <div className={layout.detailBody}>
        {tab === 'identity' && (
          <div className={s.identityGrid}>
            <section className={layout.section}>
              <h3 className={layout.sectionTitle}>Vitals</h3>
              <DataList
                rows={[
                  { label: 'Energy', value: <Meter value={agent.energy} tone={agent.energy < 0.25 ? 'crit' : 'live'} format={(v) => fmtFixed(v, 2)} style={{ width: 140 }} />, mono: false },
                  { label: 'Age', value: `${fmtInt(agent.age)} t` },
                  { label: 'Born', value: `tick ${fmtTick(agent.bornAtTick)}` },
                  { label: 'Died', value: agent.diedAtTick !== null ? `tick ${fmtTick(agent.diedAtTick)}` : '—' },
                  { label: 'Position', value: fmtCoord(agent.position.x, agent.position.y) },
                  ...(agent.inventory && Object.keys(agent.inventory).length > 0
                    ? [{ label: 'Inventory', value: Object.entries(agent.inventory).map(([k, v]) => `${k} ${fmtFixed(v, 2)}`).join(' · ') }]
                    : []),
                ]}
              />
            </section>
            {(agent.policy || agent.intent || agent.decisionsTotal !== undefined) && (
              <section className={layout.section}>
                <h3 className={layout.sectionTitle}>Cognition</h3>
                <DataList
                  rows={[
                    ...(agent.policy ? [{ label: 'Last policy', value: <Tag tone={agent.policy === 'model' ? 'sel' : undefined}>{agent.policy}</Tag>, mono: false }] : []),
                    ...(agent.modelRef !== undefined ? [{ label: 'Model', value: agent.modelRef ?? 'none (reflex only)' }] : []),
                    ...(agent.decisionsTotal !== undefined
                      ? [{ label: 'Decisions', value: `${fmtInt(agent.decisionsTotal)} total · ${fmtInt(agent.decisionsModel ?? 0)} by model` }]
                      : []),
                    {
                      label: 'Current intent',
                      value: agent.intent ? (
                        <span>
                          <span className="mono">{agent.intent.type}</span>
                          {fmtParams(agent.intent.params) && <span className="mono faint"> {fmtParams(agent.intent.params)}</span>}
                          <span className="faint"> · since {fmtTick(agent.intent.startedTick)}</span>
                        </span>
                      ) : (
                        <span className="faint">idle</span>
                      ),
                      mono: false,
                    },
                  ]}
                />
              </section>
            )}
            <section className={layout.section}>
              <h3 className={layout.sectionTitle}>Traits</h3>
              <div className={s.traitList}>
                {agent.traits.map((t) => (
                  <div key={t.key} className={s.traitRow}>
                    <span>{t.label}</span>
                    <Meter value={t.value} format={(v) => fmtFixed(v, 2)} />
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}

        {tab === 'lineage' && (
          <div className={s.lineage}>
            <div className={s.lineageCol}>
              <h3 className={layout.sectionTitle}>Parents</h3>
              {agent.lineage.parentIds.length === 0 && <div className={s.lineageEmpty}>No recorded parents — founding generation.</div>}
              {agent.lineage.parentIds.map((id) => (
                <LineageNode key={id} id={id} agent={byId.get(id)} />
              ))}
            </div>
            <div className={s.lineageSelf}>
              <span className="caps">Subject</span>
              <strong style={{ fontWeight: 500, marginTop: 4 }}>{agent.name}</strong>
              <span className="mono faint" style={{ fontSize: 'var(--fs-11)' }}>
                gen {agent.generation}
              </span>
            </div>
            <div className={s.lineageCol}>
              <h3 className={layout.sectionTitle}>Offspring</h3>
              {agent.lineage.offspringIds.length === 0 && <div className={s.lineageEmpty}>No offspring recorded.</div>}
              {agent.lineage.offspringIds.map((id) => (
                <LineageNode key={id} id={id} agent={byId.get(id)} />
              ))}
            </div>
          </div>
        )}

        {tab === 'relationships' &&
          (agent.relationships.length === 0 ? (
            <EmptyState title="No relationships" body="The engine has not reported any social ties for this agent." />
          ) : (
            <Table<Agent['relationships'][number]>
              aria-label="Relationships"
              rows={agent.relationships}
              rowKey={(r) => `${r.agentId}-${r.kind}`}
              columns={
                [
                  { key: 'agent', header: 'Agent', render: (r) => <Link to={`/agents/${r.agentId}`} className="linkish">{nameOf(r.agentId)}</Link>, fill: true },
                  { key: 'id', header: 'Id', mono: true, render: (r) => fmtAgentCode(r.agentId) },
                  { key: 'kind', header: 'Kind', render: (r) => <Tag>{r.kind}</Tag>, sortValue: (r) => r.kind },
                  { key: 'affinity', header: 'Affinity', render: (r) => <Meter value={r.affinity} bipolar tone={r.affinity < 0 ? 'crit' : 'live'} style={{ width: 140 }} />, sortValue: (r) => r.affinity },
                  { key: 'since', header: 'Since', num: true, render: (r) => fmtTick(r.sinceTick), sortValue: (r) => r.sinceTick },
                ] satisfies Column<Agent['relationships'][number]>[]
              }
            />
          ))}

        {tab === 'knowledge' &&
          (agent.knowledge.length === 0 ? (
            <EmptyState title="No knowledge items" body="Nothing has been acquired, taught or inherited yet." />
          ) : (
            <Table<Agent['knowledge'][number]>
              aria-label="Knowledge"
              rows={agent.knowledge}
              rowKey={(k) => k.id}
              initialSort={{ key: 'confidence', dir: 'desc' }}
              columns={[
                { key: 'topic', header: 'Topic', render: (k) => k.topic, fill: true, sortValue: (k) => k.topic },
                { key: 'source', header: 'Source', render: (k) => <Tag>{k.source}</Tag>, sortValue: (k) => k.source },
                { key: 'confidence', header: 'Confidence', render: (k) => <Meter value={k.confidence} style={{ width: 120 }} />, sortValue: (k) => k.confidence },
                { key: 'acq', header: 'Acquired', num: true, render: (k) => fmtTick(k.acquiredAtTick), sortValue: (k) => k.acquiredAtTick },
              ]}
            />
          ))}

        {tab === 'memory' &&
          (agent.memory.length === 0 ? (
            <EmptyState title="No memory records" body="The engine has not published memory traces for this agent." />
          ) : (
            <div className={s.memory}>
              {[...agent.memory]
                .sort((a, b) => b.tick - a.tick)
                .map((m) => (
                  <div key={m.id} className={s.memoryItem}>
                    <span className={s.memoryTick}>{fmtTick(m.tick)}</span>
                    <Tag>{m.kind}</Tag>
                    <span className={cn(s.memorySummary)}>
                      {m.summary}
                      {m.source && m.source !== 'observation' && (
                        <Tag tone={m.source === 'inference' ? 'sel' : undefined} title={m.source === 'inference' ? 'Written by the model, not observed' : m.source === 'taught' ? 'Received from another agent' : 'Inherited at birth'} className={s.memorySource}>
                          {m.source}
                        </Tag>
                      )}
                    </span>
                    <Meter value={m.salience} format={(v) => `sal ${fmtPct(v)}`} />
                  </div>
                ))}
            </div>
          ))}

        {tab === 'decisions' && (
          <ResourceBoundary resource={decisions} isEmpty={(d) => d.length === 0} empty={
              <EmptyState
                title="No model decisions logged"
                body={`The log holds every deliberation sent to a model — accepted, rejected or failed. Routine reflex behaviour is counted (${fmtInt(agent.decisionsTotal ?? 0)} so far) but not logged.${agent.decisionsModel === 0 ? ' Model reasoning is disabled for this universe or the provider has not answered yet.' : ''}`}
              />
            }
          >
            {(rows) => (
              <Table<DecisionRecord>
                compact
                aria-label="Decisions"
                rows={rows}
                rowKey={(d) => String(d.id)}
                initialSort={{ key: 'tick', dir: 'desc' }}
                columns={[
                  { key: 'tick', header: 'Tick', num: true, render: (d) => fmtTick(d.tickRequested), sortValue: (d) => d.tickRequested, width: 72 },
                  { key: 'purpose', header: 'Purpose', render: (d) => d.purpose, sortValue: (d) => d.purpose },
                  { key: 'policy', header: 'Policy', render: (d) => <Tag tone={d.policy === 'model' ? 'sel' : undefined}>{d.policy}</Tag>, sortValue: (d) => d.policy },
                  {
                    key: 'action',
                    header: 'Action',
                    fill: true,
                    render: (d) => (
                      <span>
                        {d.action ? (
                          <>
                            <span className="mono">{d.action.type}</span>
                            {fmtParams(d.action.params) && <span className="mono faint"> {fmtParams(d.action.params)}</span>}
                          </>
                        ) : (
                          <span className="faint">—</span>
                        )}
                        {d.rationale && (
                          <span className="faint" style={{ display: 'block', fontSize: 'var(--fs-11)' }} title={d.rationale}>
                            {d.rationale}
                          </span>
                        )}
                      </span>
                    ),
                  },
                  {
                    key: 'outcome',
                    header: 'Outcome',
                    render: (d) =>
                      d.accepted ? (
                        <StatusLabel tone="live">applied{d.tickApplied !== null ? ` @${fmtTick(d.tickApplied)}` : ''}</StatusLabel>
                      ) : (
                        <StatusLabel tone="crit">{d.rejectionReason ?? (d.valid === false ? 'invalid output' : 'rejected')}</StatusLabel>
                      ),
                    sortValue: (d) => (d.accepted ? 1 : 0),
                  },
                  { key: 'latency', header: 'Latency', num: true, render: (d) => (d.latencyMs !== null ? `${fmtInt(d.latencyMs)} ms` : '—'), sortValue: (d) => d.latencyMs ?? -1 },
                  { key: 'tokens', header: 'Tokens', num: true, render: (d) => (d.promptTokens !== null ? `${fmtInt(d.promptTokens)}+${fmtInt(d.completionTokens ?? 0)}` : '—') },
                  { key: 'model', header: 'Model', mono: true, render: (d) => d.modelRef ?? '—' },
                ]}
              />
            )}
          </ResourceBoundary>
        )}
      </div>
    </div>
  );
}

function LineageNode({ id, agent }: { id: string; agent: Agent | undefined }) {
  return (
    <Link to={`/agents/${id}`} className={s.lineageNode}>
      <span>
        {agent?.name ?? 'Unknown'} <span className="mono faint">{fmtAgentCode(id)}</span>
      </span>
      {agent ? <StatusLabel tone={agentTone[agent.status]}>gen {agent.generation}</StatusLabel> : <span className="faint">not loaded</span>}
    </Link>
  );
}
