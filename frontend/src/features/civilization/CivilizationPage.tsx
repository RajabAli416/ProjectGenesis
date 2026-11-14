import { useEffect, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router';
import type { Civilization, CivilizationStage, Technology } from '@/domain';
import { useUniverseContext } from '@/app/universeContext';
import { useCivilization } from '@/api/hooks';
import { useChrome } from '@/store/chromeStore';
import { Page } from '@/components/shell/AppShell';
import { Panel, Readouts, Select, Tag, Meter, Disclosure, Table, EmptyState, ResourceBoundary, StatusDot, type Column } from '@/components/ui';
import { fmtAgentCode, fmtInt, fmtPct, fmtTick, titleCase } from '@/lib/format';
import { cn } from '@/lib/cn';
import { civilizationStageLabel, civilizationStages } from '@/lib/status';
import { SampleNotice } from '../shared/SampleNotice';
import layout from '../shared/layout.module.css';
import s from './CivilizationPage.module.css';

const STAGES = civilizationStages;
const stageLabel = civilizationStageLabel;

export default function CivilizationPage() {
  const { universes, active, byId } = useUniverseContext();
  const [params, setParams] = useSearchParams();
  const paramId = params.get('u');
  const universeId = paramId && byId.has(paramId) ? paramId : (active?.id ?? null);
  const universe = universeId ? (byId.get(universeId) ?? null) : null;

  useEffect(() => {
    if (!paramId && active) setParams({ u: active.id }, { replace: true });
  }, [paramId, active, setParams]);

  const civRes = useCivilization(universeId);

  useChrome({ detail: universe ? `${universe.code} ${universe.name}` : 'No universe' });

  const selector = (
    <Select
      aria-label="Universe"
      mono
      value={universeId ?? ''}
      onChange={(e) => setParams({ u: e.currentTarget.value })}
      options={universes.map((u) => ({ value: u.id, label: `${u.code}  ${u.name}` }))}
    />
  );

  return (
    <Page title="Civilization" lede="Collective development of the population in a single universe." actions={selector}>
      <SampleNotice compact />

      {!universe && <EmptyState icon="civilization" title="No universe selected" body="Choose a universe to view its civilization record." />}

      {universe && (
        <ResourceBoundary
          resource={civRes}
          isEmpty={(d) => d === null || d.stage === 'none'}
          empty={
            <>
              <StageTrack stage={universe.civilizationStage ?? 'none'} />
              <EmptyState
                icon="civilization"
                title={universe.status === 'initialising' ? 'Universe is initialising' : 'No civilization yet'}
                body={
                  universe.status === 'initialising'
                    ? 'This universe has no population. Civilization records begin once agents form persistent groups.'
                    : `${universe.code} ${universe.name} has ${fmtInt(universe.population.alive)} living agents but the engine has not detected persistent social structures. Technology, institutions and infrastructure appear here when they emerge.`
                }
              />
            </>
          }
        >
          {(civ) => <CivilizationView civ={civ!} />}
        </ResourceBoundary>
      )}
    </Page>
  );
}

function StageTrack({ stage }: { stage: CivilizationStage }) {
  const idx = STAGES.indexOf(stage);
  return (
    <div className={s.stages} role="list" aria-label="Civilization stages">
      {STAGES.map((st, i) => (
        <div key={st} role="listitem" className={cn(s.stage, i <= idx && s.stageReached, i === idx && s.stageCurrent)} aria-current={i === idx ? 'step' : undefined}>
          <span className={s.stageIndex}>{String(i).padStart(2, '0')}</span>
          <span className={s.stageName}>{stageLabel[st]}</span>
        </div>
      ))}
    </div>
  );
}

function CivilizationView({ civ }: { civ: Civilization }) {
  const established = civ.technologies.filter((t) => t.state === 'established').length;
  const emerging = civ.technologies.filter((t) => t.state === 'emerging').length;
  const tiers = useMemo(() => {
    const map = new Map<number, Technology[]>();
    for (const t of civ.technologies) map.set(t.tier, [...(map.get(t.tier) ?? []), t]);
    return [...map.entries()].sort((a, b) => a[0] - b[0]);
  }, [civ.technologies]);
  const techName = (id: string) => civ.technologies.find((t) => t.id === id)?.name ?? id;

  const knowledgeCols: Column<Civilization['collectiveKnowledge'][number]>[] = [
    { key: 'topic', header: 'Topic', render: (k) => k.topic, fill: true, sortValue: (k) => k.topic },
    { key: 'holders', header: 'Holders', num: true, render: (k) => fmtInt(k.holders), sortValue: (k) => k.holders },
    { key: 'conf', header: 'Mean confidence', render: (k) => <Meter value={k.confidence} style={{ width: 120 }} />, sortValue: (k) => k.confidence },
  ];

  return (
    <>
      <StageTrack stage={civ.stage} />

      <Readouts
        items={[
          { label: 'Stage', value: stageLabel[civ.stage] },
          { label: 'Technologies', value: established, note: `${emerging} emerging · ${civ.technologies.length - established - emerging} unknown` },
          { label: 'Institutions', value: civ.institutions.length, note: `${fmtInt(civ.institutions.reduce((n, i) => n + i.members, 0))} members` },
          { label: 'Infrastructure', value: fmtInt(civ.infrastructure.reduce((n, i) => n + i.count, 0)), note: `${civ.infrastructure.length} types` },
          { label: 'Shared knowledge', value: civ.collectiveKnowledge.length, note: 'topics held collectively' },
        ]}
      />

      <div className={layout.grid2}>
        <Panel title="Population development" subtitle="eras by tick range">
          {civ.eras.length === 0 ? (
            <EmptyState title="No eras recorded" />
          ) : (
            <div className={s.eras}>
              {civ.eras.map((e) => (
                <div key={e.id} className={s.era}>
                  <div>
                    <div className={s.eraLabel}>{e.label}</div>
                    <div className={s.eraRange}>
                      {fmtTick(e.fromTick)} – {e.toTick !== null ? fmtTick(e.toTick) : 'present'}
                    </div>
                  </div>
                  <div className={s.eraNote}>{e.note ?? ''}</div>
                  <div className={s.eraPeak} title="Peak population">
                    {fmtInt(e.peakPopulation)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Technology progression" subtitle="grouped by tier">
          {tiers.length === 0 ? (
            <EmptyState title="No technologies" body="Nothing has been discovered." />
          ) : (
            tiers.map(([tier, techs]) => (
              <Disclosure key={tier} title={`Tier ${tier}`} meta={`${techs.filter((t) => t.state === 'established').length}/${techs.length}`} defaultOpen={tier <= 2 || techs.some((t) => t.state === 'emerging')}>
                {techs.map((t) => (
                  <div key={t.id} className={cn(s.techRow, t.state === 'unknown' && s.techUnknown)}>
                    <div>
                      <div className={s.techName}>
                        <StatusDot tone={t.state === 'established' ? 'live' : t.state === 'emerging' ? 'attn' : 'neutral'} />
                        {t.name}
                      </div>
                      {t.requires.length > 0 && <div className={s.techReq}>requires {t.requires.map(techName).join(', ')}</div>}
                    </div>
                    <div className={s.techMeta}>
                      {t.discoveredAtTick !== null ? <span>t {fmtTick(t.discoveredAtTick)}</span> : <span>—</span>}
                      {t.discoveredBy ? (
                        <Link to={`/agents/${t.discoveredBy}`} className="linkish">
                          {fmtAgentCode(t.discoveredBy)}
                        </Link>
                      ) : (
                        <Tag>{t.state}</Tag>
                      )}
                    </div>
                  </div>
                ))}
              </Disclosure>
            ))
          )}
        </Panel>

        <Panel title="Social structures" subtitle="institutions">
          {civ.institutions.length === 0 ? (
            <EmptyState title="No institutions" body="No persistent groups beyond kinship have formed." />
          ) : (
            <Table
              aria-label="Institutions"
              rows={civ.institutions}
              rowKey={(i) => i.id}
              columns={[
                { key: 'name', header: 'Name', render: (i) => i.name, fill: true, sortValue: (i) => i.name },
                { key: 'kind', header: 'Kind', render: (i) => <Tag>{titleCase(i.kind)}</Tag>, sortValue: (i) => i.kind },
                { key: 'members', header: 'Members', num: true, render: (i) => fmtInt(i.members), sortValue: (i) => i.members },
                { key: 'founded', header: 'Founded', num: true, render: (i) => fmtTick(i.foundedAtTick), sortValue: (i) => i.foundedAtTick },
              ]}
            />
          )}
        </Panel>

        <Panel title="Infrastructure" subtitle="inventory and condition">
          {civ.infrastructure.length === 0 ? (
            <EmptyState title="No infrastructure" body="No persistent structures have been built." />
          ) : (
            <div>
              {civ.infrastructure.map((i) => (
                <div key={i.id} className={s.infraRow}>
                  <span style={{ color: 'var(--fg-1)' }}>{i.name}</span>
                  <span className="mono" style={{ textAlign: 'right', color: 'var(--fg-2)' }}>
                    {fmtInt(i.count)}
                  </span>
                  <Meter value={i.condition} tone={i.condition < 0.5 ? 'attn' : undefined} format={(v) => `${fmtPct(v)} cond`} />
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Collective knowledge" subtitle="topics held by multiple agents" flushBody>
        {civ.collectiveKnowledge.length === 0 ? (
          <EmptyState title="No shared knowledge" body="Knowledge has not yet propagated between agents." />
        ) : (
          <Table aria-label="Collective knowledge" rows={civ.collectiveKnowledge} rowKey={(k) => k.id} columns={knowledgeCols} initialSort={{ key: 'holders', dir: 'desc' }} />
        )}
      </Panel>
    </>
  );
}
