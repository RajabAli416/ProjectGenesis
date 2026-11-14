import { useEffect, useState } from 'react';
import { useSettings } from '@/api/hooks';
import { dataSource, mutations } from '@/api';
import { useSettingsStore } from '@/store/settingsStore';
import { useChrome } from '@/store/chromeStore';
import { Page } from '@/components/shell/AppShell';
import { Panel, Field, Input, NumberField, Select, Toggle, Slider, Button, Tag, Notice, StatusDot, IconButton, ResourceBoundary, EmptyState } from '@/components/ui';
import { fmtInt } from '@/lib/format';
import { InferencePanel } from './InferencePanel';
import s from './SettingsPage.module.css';

const GROUPS = [
  { id: 'providers', label: 'Model providers' },
  { id: 'inference', label: 'Inference' },
  { id: 'reasoning', label: 'Reasoning' },
  { id: 'simulation', label: 'Simulation parameters' },
  { id: 'performance', label: 'Performance' },
  { id: 'persistence', label: 'Persistence' },
] as const;

const ADAPTERS = [
  { value: 'ollama', label: 'ollama' },
  { value: 'openai-compatible', label: 'openai-compatible' },
  { value: 'scripted', label: 'scripted (deterministic, no model)' },
  { value: 'replay', label: 'replay (recorded responses)' },
];

export default function SettingsPage() {
  const res = useSettings();
  const live = dataSource.kind === 'http';
  const draft = useSettingsStore((st) => st.draft);
  const dirty = useSettingsStore((st) => st.dirty);
  const hydrate = useSettingsStore((st) => st.hydrate);
  const adopt = useSettingsStore((st) => st.adopt);
  const reset = useSettingsStore((st) => st.reset);
  const updateProvider = useSettingsStore((st) => st.updateProvider);
  const addProvider = useSettingsStore((st) => st.addProvider);
  const removeProvider = useSettingsStore((st) => st.removeProvider);
  const updateReasoning = useSettingsStore((st) => st.updateReasoning);
  const updateSimulation = useSettingsStore((st) => st.updateSimulation);
  const updatePerformance = useSettingsStore((st) => st.updatePerformance);
  const updatePersistence = useSettingsStore((st) => st.updatePersistence);

  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [credentialBusy, setCredentialBusy] = useState<string | null>(null);

  useEffect(() => {
    if (res.data) hydrate(res.data);
  }, [res.data, hydrate]);

  useChrome({ detail: 'Operator configuration', statusRight: dirty ? 'unsaved changes' : null });

  const apply = async () => {
    if (!draft) return;
    setApplying(true);
    setApplyError(null);
    try {
      const saved = await mutations.putSettings(draft);
      adopt(saved);
    } catch (e) {
      setApplyError(e instanceof Error ? e.message : 'Apply failed');
    } finally {
      setApplying(false);
    }
  };

  const setCredential = async (providerId: string, hasCredential: boolean) => {
    const value = window.prompt(hasCredential ? 'Enter the new credential (leave empty to remove it). It is stored on the backend only.' : 'Enter the credential for this provider. It is stored on the backend only.');
    if (value === null) return;
    setCredentialBusy(providerId);
    setApplyError(null);
    try {
      const saved = await mutations.setCredential(providerId, value.trim() || null);
      adopt(saved);
    } catch (e) {
      setApplyError(e instanceof Error ? e.message : 'Credential update failed');
    } finally {
      setCredentialBusy(null);
    }
  };

  const actions = (
    <div className={s.toolbar}>
      {applyError && (
        <span className={s.dirty} title={applyError}>
          <StatusDot tone="crit" /> {applyError}
        </span>
      )}
      {dirty && !applyError && (
        <span className={s.dirty}>
          <StatusDot tone="attn" /> Unsaved changes
        </span>
      )}
      <Button size="sm" variant="ghost" onClick={reset} disabled={!dirty || applying}>
        Discard
      </Button>
      <Button size="sm" variant="primary" onClick={apply} disabled={!live || !dirty || applying} title={live ? 'Persist these settings on the backend' : 'Applying settings requires a connected backend'}>
        {applying ? 'Applying…' : 'Apply'}
      </Button>
    </div>
  );

  return (
    <Page title="Settings" lede={live ? 'Operator configuration. Applied settings are persisted by the backend and used for new universes and future inference calls.' : 'Operator configuration. Values are held locally and applied to the engine once a backend is connected.'} actions={actions}>
      {!live && (
        <Notice tone="attn">
          No backend is connected. Edits are kept in this browser as a draft and are not applied anywhere. Model providers are described by an opaque adapter identifier; the interface does not special-case any vendor.
        </Notice>
      )}

      <ResourceBoundary resource={res} loadingLines={5}>
        {() =>
          !draft ? (
            <EmptyState title="Settings unavailable" />
          ) : (
            <div className={s.layout}>
              <nav className={s.toc} aria-label="Settings groups">
                {GROUPS.map((g) => (
                  <a key={g.id} href={`#${g.id}`} className={s.tocLink}>
                    {g.label}
                  </a>
                ))}
              </nav>

              <div className={s.groups}>
                <Panel id="providers" className={s.group} title="Model providers" subtitle="reasoning endpoints available to agents" actions={<Button size="sm" variant="ghost" icon="plus" onClick={addProvider}>Add</Button>}>
                  {draft.providers.length === 0 ? (
                    <EmptyState title="No providers" body="Add an endpoint the backend can route reasoning requests to." />
                  ) : (
                    <div className={s.providers}>
                      {draft.providers.map((p) => (
                        <div key={p.id} className={s.provider}>
                          <div className={s.providerHead}>
                            <Toggle checked={p.enabled} onChange={(v) => updateProvider(p.id, { enabled: v })} label={`Enable ${p.label}`} />
                            <span className={s.providerLabel}>
                              <Input value={p.label} onChange={(e) => updateProvider(p.id, { label: e.currentTarget.value })} aria-label="Provider label" size_="sm" />
                            </span>
                            <Tag mono>{p.adapter}</Tag>
                            <Tag tone={p.hasCredential ? 'live' : undefined}>{p.hasCredential ? 'credential stored' : 'no credential'}</Tag>
                            <IconButton icon="close" label="Remove provider" size="sm" onClick={() => removeProvider(p.id)} />
                          </div>
                          <Field label="Adapter" hint="Backend adapter identifier">
                            <Select size_="sm" mono value={p.adapter} onChange={(e) => updateProvider(p.id, { adapter: e.currentTarget.value })} options={ADAPTERS.some((a) => a.value === p.adapter) ? ADAPTERS : [...ADAPTERS, { value: p.adapter, label: p.adapter }]} />
                          </Field>
                          <Field label="Base URL" hint={p.adapter === 'ollama' ? 'Ollama server, e.g. http://127.0.0.1:11434' : 'OpenAI-compatible root, e.g. http://host:port/v1'}>
                            <Input mono size_="sm" value={p.baseUrl} onChange={(e) => updateProvider(p.id, { baseUrl: e.currentTarget.value })} placeholder={p.adapter === 'ollama' ? 'http://127.0.0.1:11434' : 'http://host:port/v1'} aria-label="Base URL" />
                          </Field>
                          <Field label="Model" hint={p.adapter === 'ollama' ? 'Must be pulled on the Ollama host (e.g. qwen3:4b)' : undefined}>
                            <Input mono size_="sm" value={p.model} onChange={(e) => updateProvider(p.id, { model: e.currentTarget.value })} placeholder="model identifier" aria-label="Model" />
                          </Field>
                          <Field label="Credential" hint="Stored server-side; never shown here">
                            <Button size="sm" variant="outline" disabled={!live || credentialBusy === p.id} title={live ? 'Store a credential for this provider on the backend' : 'Requires a connected backend'} onClick={() => setCredential(p.id, p.hasCredential)}>
                              {credentialBusy === p.id ? 'Saving…' : p.hasCredential ? 'Rotate' : 'Set'}
                            </Button>
                          </Field>
                        </div>
                      ))}
                    </div>
                  )}
                </Panel>

                {live && <InferencePanel id="inference" className={s.group} />}

                <Panel id="reasoning" className={s.group} title="Reasoning" subtitle="how and how often agents deliberate">
                  <Field label="Default provider">
                    <Select
                      size_="sm"
                      value={draft.reasoning.providerId ?? ''}
                      onChange={(e) => updateReasoning({ providerId: e.currentTarget.value || null })}
                      options={[{ value: '', label: 'None (reflex only)' }, ...draft.providers.map((p) => ({ value: p.id, label: p.label }))]}
                    />
                  </Field>
                  <Field label="Temperature" hint="Sampling temperature passed to the provider">
                    <Slider label="Temperature" min={0} max={2} step={0.05} value={draft.reasoning.temperature} onChange={(v) => updateReasoning({ temperature: v })} format={(v) => v.toFixed(2)} />
                  </Field>
                  <Field label="Max steps" hint="Attempts per deliberation: 1 = no repair turn after an invalid response">
                    <NumberField value={draft.reasoning.maxSteps} onChange={(v) => updateReasoning({ maxSteps: Math.max(1, Math.round(v)) })} min={1} max={8} />
                  </Field>
                  <Field label="Decision interval" hint="Ticks between scheduled decisions; needs and messages trigger earlier">
                    <NumberField value={draft.reasoning.decisionInterval ?? 120} onChange={(v) => updateReasoning({ decisionInterval: Math.max(1, Math.round(v)) })} min={1} unit="ticks" />
                  </Field>
                  <Field label="Reflection interval" hint="Ticks between reflective passes">
                    <NumberField value={draft.reasoning.reflectionInterval} onChange={(v) => updateReasoning({ reflectionInterval: Math.max(1, Math.round(v)) })} min={1} unit="ticks" />
                  </Field>
                  <Field label="Memory window" hint="Most recent records placed in the prompt">
                    <NumberField value={draft.reasoning.memoryWindow} onChange={(v) => updateReasoning({ memoryWindow: Math.max(1, Math.round(v)) })} min={1} unit="records" />
                  </Field>
                  <Field label="Context window" hint="num_ctx requested from the provider; prompts are budgeted to fit">
                    <NumberField value={draft.reasoning.numCtx ?? 4096} onChange={(v) => updateReasoning({ numCtx: Math.max(1024, Math.round(v)) })} min={1024} step={1024} unit="tokens" />
                  </Field>
                  <Field label="Thinking for decisions" hint="Qwen3 'think' mode on action choices — slower, rarely better for structured output">
                    <Toggle checked={draft.reasoning.thinkDecisions ?? false} onChange={(v) => updateReasoning({ thinkDecisions: v })} label="Thinking for decisions" />
                  </Field>
                  <Field label="Thinking for reflection" hint="Allow extended thinking on periodic reflections">
                    <Toggle checked={draft.reasoning.thinkReflection ?? true} onChange={(v) => updateReasoning({ thinkReflection: v })} label="Thinking for reflection" />
                  </Field>
                  <Field label="Concurrency" hint="Parallel inference requests; keep at 1 on a single small GPU">
                    <NumberField value={draft.reasoning.concurrency ?? 1} onChange={(v) => updateReasoning({ concurrency: Math.max(1, Math.min(8, Math.round(v))) })} min={1} max={8} />
                  </Field>
                  <Field label="Timeout" hint="Per request; a timed-out decision falls back to reflex">
                    <NumberField value={draft.reasoning.timeoutS ?? 120} onChange={(v) => updateReasoning({ timeoutS: Math.max(5, Math.round(v)) })} min={5} unit="s" />
                  </Field>
                </Panel>

                <Panel id="simulation" className={s.group} title="Simulation parameters" subtitle="defaults for newly created universes">
                  <Field label="Tick rate" hint="Engine ticks per real second at 1×">
                    <NumberField value={draft.simulation.tickRate} onChange={(v) => updateSimulation({ tickRate: Math.max(1, v) })} min={1} unit="t/s" />
                  </Field>
                  <Field label="World width" hint={`World units; ${draft.simulation.cellSize ?? 8} units per terrain cell`}>
                    <NumberField value={draft.simulation.worldWidth} onChange={(v) => updateSimulation({ worldWidth: Math.max(32, Math.round(v)) })} min={32} step={draft.simulation.cellSize ?? 8} unit="units" />
                  </Field>
                  <Field label="World height">
                    <NumberField value={draft.simulation.worldHeight} onChange={(v) => updateSimulation({ worldHeight: Math.max(32, Math.round(v)) })} min={32} step={draft.simulation.cellSize ?? 8} unit="units" />
                  </Field>
                  <Field label="Initial population">
                    <NumberField value={draft.simulation.initialPopulation} onChange={(v) => updateSimulation({ initialPopulation: Math.max(1, Math.round(v)) })} min={1} unit="agents" />
                  </Field>
                  <Field label="Mutation rate" hint="Per-trait probability per birth">
                    <Slider label="Mutation rate" min={0} max={0.1} step={0.001} value={draft.simulation.mutationRate} onChange={(v) => updateSimulation({ mutationRate: v })} format={(v) => v.toFixed(3)} />
                  </Field>
                  <Field label="Energy decay" hint="Per-tick energy loss">
                    <Slider label="Energy decay" min={0} max={0.02} step={0.0005} value={draft.simulation.energyDecay} onChange={(v) => updateSimulation({ energyDecay: v })} format={(v) => v.toFixed(4)} />
                  </Field>
                </Panel>

                <Panel id="performance" className={s.group} title="Performance" subtitle="viewport rendering budget">
                  <Field label="Render scale" hint="Fraction of device pixel ratio">
                    <Slider label="Render scale" min={0.5} max={2} step={0.25} value={draft.performance.renderScale} onChange={(v) => updatePerformance({ renderScale: v })} format={(v) => `${v.toFixed(2)}×`} />
                  </Field>
                  <Field label="Entity cap" hint="Maximum markers drawn per frame">
                    <NumberField value={draft.performance.entityCap} onChange={(v) => updatePerformance({ entityCap: Math.max(100, Math.round(v)) })} min={100} step={100} />
                  </Field>
                  <Field label="FPS cap">
                    <Select
                      size_="sm"
                      mono
                      value={String(draft.performance.fpsCap)}
                      onChange={(e) => updatePerformance({ fpsCap: Number(e.currentTarget.value) })}
                      options={[30, 60, 120].map((v) => ({ value: String(v), label: `${v} fps` }))}
                    />
                  </Field>
                  <Field label="Cull off-screen entities">
                    <Toggle checked={draft.performance.cullOffscreen} onChange={(v) => updatePerformance({ cullOffscreen: v })} label="Cull off-screen entities" />
                  </Field>
                </Panel>

                <Panel id="persistence" className={s.group} title="Persistence" subtitle="snapshots written by the backend">
                  <Field label="Autosave">
                    <Toggle checked={draft.persistence.autosave} onChange={(v) => updatePersistence({ autosave: v })} label="Autosave" />
                  </Field>
                  <Field label="Snapshot interval">
                    <NumberField value={draft.persistence.snapshotIntervalTicks} onChange={(v) => updatePersistence({ snapshotIntervalTicks: Math.max(1, Math.round(v)) })} min={1} unit="ticks" disabled={!draft.persistence.autosave} />
                  </Field>
                  <Field label="Retain snapshots" hint={`≈ ${fmtInt(draft.persistence.snapshotIntervalTicks * draft.persistence.retainSnapshots)} ticks of history`}>
                    <NumberField value={draft.persistence.retainSnapshots} onChange={(v) => updatePersistence({ retainSnapshots: Math.max(1, Math.round(v)) })} min={1} />
                  </Field>
                  <Field label="Store path" hint="Resolved on the backend host; read-only here">
                    <Input mono size_="sm" value={draft.persistence.storePath} readOnly aria-label="Store path" />
                  </Field>
                </Panel>
              </div>
            </div>
          )
        }
      </ResourceBoundary>
    </Page>
  );
}
