import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import type { Agent, AgentStatus } from '@/domain';
import { useUniverseContext } from '@/app/universeContext';
import { useAgents } from '@/api/hooks';
import { useChrome } from '@/store/chromeStore';
import { Page } from '@/components/shell/AppShell';
import { Table, SearchInput, Select, StatusDot, Meter, EmptyState, ResourceBoundary, type Column } from '@/components/ui';
import { fmtAgentCode, fmtInt } from '@/lib/format';
import { agentTone } from '@/lib/status';
import { useMediaQuery } from '@/lib/useMediaQuery';
import { AgentDetail } from './AgentDetail';
import layout from '../shared/layout.module.css';
import s from './AgentsPage.module.css';

type StatusFilter = 'all' | AgentStatus;

export default function AgentsPage() {
  const { agentId } = useParams();
  const navigate = useNavigate();
  const { universes, active } = useUniverseContext();

  // null = not chosen by the operator; follow the active universe unless a deep link to an agent is open.
  const [universeChoice, setUniverseChoice] = useState<string | null>(null);
  const [status, setStatus] = useState<StatusFilter>('all');
  const [query, setQuery] = useState('');
  const universeFilter = universeChoice ?? (agentId ? 'all' : (active?.id ?? 'all'));

  const agentsRes = useAgents(null);
  const all = useMemo(() => agentsRes.data ?? [], [agentsRes.data]);
  const byId = useMemo(() => new Map(all.map((a) => [a.id, a])), [all]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return all.filter(
      (a) =>
        (universeFilter === 'all' || a.universeId === universeFilter) &&
        (status === 'all' || a.status === status) &&
        (!q || a.name.toLowerCase().includes(q) || a.id.toLowerCase().includes(q)),
    );
  }, [all, universeFilter, status, query]);

  const selected = agentId ? (byId.get(agentId) ?? null) : null;

  useChrome({
    detail: selected ? `${selected.name} · ${fmtAgentCode(selected.id)}` : 'Explorer',
    statusLeft: agentsRes.data ? `${filtered.length} of ${all.length} agents` : null,
  });

  const narrow = useMediaQuery('(max-width: 900px)');
  const columns: Column<Agent>[] = [
    { key: 'status', header: '', width: 20, render: (a) => <StatusDot tone={agentTone[a.status]} /> },
    { key: 'id', header: 'Id', mono: true, render: (a) => fmtAgentCode(a.id), sortValue: (a) => a.id, width: 84 },
    { key: 'name', header: 'Name', render: (a) => <span style={{ color: 'var(--fg-0)' }}>{a.name}</span>, sortValue: (a) => a.name, fill: true },
    { key: 'gen', header: 'Gen', num: true, render: (a) => a.generation, sortValue: (a) => a.generation },
    ...(narrow ? [] : [{ key: 'age', header: 'Age', num: true, render: (a) => fmtInt(a.age), sortValue: (a) => a.age } satisfies Column<Agent>]),
    { key: 'energy', header: 'Energy', render: (a) => <Meter value={a.energy} tone={a.energy < 0.25 ? 'crit' : undefined} style={{ width: narrow ? 68 : 80 }} />, sortValue: (a) => a.energy },
  ];

  return (
    <Page flush>
      <div className={layout.masterDetail}>
        <aside className={layout.master} aria-label="Agent list">
          <div className={layout.masterToolbar}>
            <div className={s.filters}>
              <SearchInput className={s.search} placeholder="Search name or id" value={query} onChange={(e) => setQuery(e.currentTarget.value)} aria-label="Search agents" />
            </div>
            <Select
              size_="sm"
              aria-label="Filter by universe"
              value={universeFilter}
              onChange={(e) => setUniverseChoice(e.currentTarget.value)}
              options={[{ value: 'all', label: 'All universes' }, ...universes.map((u) => ({ value: u.id, label: `${u.code} ${u.name}` }))]}
            />
            <Select
              size_="sm"
              aria-label="Filter by status"
              value={status}
              onChange={(e) => setStatus(e.currentTarget.value as StatusFilter)}
              options={[
                { value: 'all', label: 'Any status' },
                { value: 'active', label: 'Active' },
                { value: 'dormant', label: 'Dormant' },
                { value: 'deceased', label: 'Deceased' },
              ]}
            />
            <span className={s.count}>{filtered.length}</span>
          </div>
          <div className={layout.masterList}>
            <ResourceBoundary
              resource={agentsRes}
              isEmpty={(d) => d.length === 0}
              empty={<EmptyState icon="agents" title="No agents" body="No agents have been registered by the engine. Agents appear here as soon as a universe is populated." />}
            >
              {() =>
                filtered.length === 0 ? (
                  <EmptyState title="No matches" body="Adjust the filters or search term." />
                ) : (
                  <Table
                    compact
                    aria-label="Agents"
                    columns={columns}
                    rows={filtered}
                    rowKey={(a) => a.id}
                    selectedKey={selected?.id ?? null}
                    onRowClick={(a) => navigate(`/agents/${a.id}`)}
                    rowClassName={(a) => (a.status === 'deceased' ? 'faint' : undefined)}
                    initialSort={{ key: 'id', dir: 'asc' }}
                  />
                )
              }
            </ResourceBoundary>
          </div>
        </aside>

        {selected ? (
          <AgentDetail key={selected.id} agent={selected} byId={byId} />
        ) : (
          <div className={layout.detail}>
            <EmptyState
              center
              icon="agents"
              title={agentId ? 'Agent not found' : 'Select an agent'}
              body={agentId ? `No agent with id ${fmtAgentCode(agentId)} is known to the current data source.` : 'Choose an agent from the list to inspect identity, lineage, relationships, knowledge and memory.'}
            />
          </div>
        )}
      </div>
    </Page>
  );
}
