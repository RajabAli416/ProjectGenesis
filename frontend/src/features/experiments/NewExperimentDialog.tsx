import { useState } from 'react';
import type { CreateExperimentRequest, ExecutionMode, Experiment, ExperimentVariable, Hypothesis, OperatorSettings } from '@/domain';
import { mutations } from '@/api';
import { Button, Field, IconButton, Input, NumberField, Select, Toggle } from '@/components/ui';
import { Modal } from '@/components/ui/Modal';
import s from './ExperimentsPage.module.css';

/**
 * Well-known UniverseConfig paths an experiment can manipulate. The list is a
 * convenience; any dot-path the backend's UniverseConfig accepts can be typed.
 */
const KNOWN_VARIABLES: Array<{ key: string; label: string; unit?: string; control: number | string | boolean }> = [
  { key: 'rules.energy_decay', label: 'Energy decay', unit: '/tick', control: 0.002 },
  { key: 'rules.base_hazard', label: 'Base hazard', control: 0.12 },
  { key: 'rules.hazard_amplitude', label: 'Hazard amplitude', control: 0.6 },
  { key: 'rules.hazard_period', label: 'Hazard period', unit: 'ticks', control: 2400 },
  { key: 'rules.resource_regen', label: 'Resource regeneration', unit: '/tick', control: 0.0012 },
  { key: 'rules.base_fertility', label: 'Base fertility', control: 0.54 },
  { key: 'rules.edge_mode', label: 'Edge mode', control: 'clamp' },
  { key: 'rules.mutation_rate', label: 'Mutation rate', control: 0.015 },
  { key: 'rules.perception_radius', label: 'Perception radius', unit: 'units', control: 24 },
  { key: 'rules.speak_radius', label: 'Speak radius', unit: 'units', control: 12 },
  { key: 'rules.max_population', label: 'Population cap', unit: 'agents', control: 200 },
  { key: 'reasoning.enabled', label: 'Model reasoning', control: true },
  { key: 'reasoning.prompt_profile', label: 'Prompt profile', control: 'neutral' },
  { key: 'reasoning.decision_interval', label: 'Decision interval', unit: 'ticks', control: 120 },
  { key: 'initial_population', label: 'Founding population', unit: 'agents', control: 5 },
];

interface VarDraft {
  key: string;
  label: string;
  control: string;
  treatment: string;
  unit: string;
}

/** Parse a typed value into the JSON type the backend's config expects. */
function parseValue(raw: string): string | number | boolean {
  const t = raw.trim();
  if (t === 'true') return true;
  if (t === 'false') return false;
  if (t !== '' && !Number.isNaN(Number(t))) return Number(t);
  return t;
}

export interface NewExperimentDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: (e: Experiment) => void;
  hypotheses: Hypothesis[];
  defaults?: OperatorSettings | null;
}

export function NewExperimentDialog({ open, onClose, onCreated, hypotheses, defaults }: NewExperimentDialogProps) {
  const [name, setName] = useState('');
  const [objective, setObjective] = useState('');
  const [vars, setVars] = useState<VarDraft[]>([{ key: 'rules.energy_decay', label: 'Energy decay', control: '0.002', treatment: '0.004', unit: '/tick' }]);
  const [replicates, setReplicates] = useState(2);
  const [duration, setDuration] = useState(3000);
  const [seed, setSeed] = useState('');
  const [mode, setMode] = useState<ExecutionMode>('lockstep');
  const [population, setPopulation] = useState(defaults?.simulation.initialPopulation ?? 5);
  const [reasoning, setReasoning] = useState(false);
  const [hypothesisIds, setHypothesisIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateVar = (i: number, patch: Partial<VarDraft>) => setVars((vs) => vs.map((v, j) => (j === i ? { ...v, ...patch } : v)));
  const pick = (i: number, key: string) => {
    const known = KNOWN_VARIABLES.find((k) => k.key === key);
    updateVar(i, known ? { key, label: known.label, unit: known.unit ?? '', control: String(known.control) } : { key });
  };

  const deterministicClaim = mode === 'lockstep' && !reasoning;

  const submit = async () => {
    const variables: ExperimentVariable[] = vars
      .filter((v) => v.key.trim())
      .map((v) => ({ key: v.key.trim(), label: v.label.trim() || v.key.trim(), control: parseValue(v.control), treatment: parseValue(v.treatment), unit: v.unit.trim() || undefined }));
    if (variables.length === 0) {
      setError('Add at least one variable.');
      return;
    }
    setBusy(true);
    setError(null);
    const req: CreateExperimentRequest = {
      name: name.trim() || 'Untitled experiment',
      objective: objective.trim(),
      variables,
      replicates,
      durationTicks: duration,
      seed: seed.trim() || null,
      mode,
      hypothesisIds,
      baseConfig: { initial_population: population, 'reasoning.enabled': reasoning },
    };
    try {
      const e = await mutations.createExperiment(req);
      onCreated(e);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create experiment');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} title="New experiment" onClose={onClose} onSubmit={submit} submitLabel="Create draft" busy={busy} error={error} wide>
      <Field label="Name">
        <Input value={name} onChange={(e) => setName(e.currentTarget.value)} placeholder="e.g. Hazard amplitude vs. settlement rate" aria-label="Experiment name" size_="sm" autoFocus />
      </Field>
      <Field label="Objective" hint="What a difference between arms would show">
        <Input value={objective} onChange={(e) => setObjective(e.currentTarget.value)} placeholder="Does doubling hazard amplitude delay the first settlement?" aria-label="Objective" size_="sm" />
      </Field>

      <div className={s.varBlock}>
        <div className={s.varBlockHead}>
          <span className={s.varBlockTitle}>Variables</span>
          <span className={s.varBlockHint}>Each run instantiates a control universe and a treatment universe differing only in these values. Columns: path · label · control · treatment · unit.</span>
        </div>
        <div className={s.varEditor}>
          {vars.map((v, i) => {
            const known = KNOWN_VARIABLES.some((k) => k.key === v.key);
            return (
              <div key={i} className={s.varEditorRow}>
                <Select
                  size_="sm"
                  mono
                  aria-label="Variable key"
                  value={known ? v.key : '__custom'}
                  onChange={(e) => pick(i, e.currentTarget.value === '__custom' ? '' : e.currentTarget.value)}
                  options={[...KNOWN_VARIABLES.map((k) => ({ value: k.key, label: k.key })), { value: '__custom', label: 'custom path…' }]}
                />
                <Input size_="sm" value={v.label} onChange={(e) => updateVar(i, { label: e.currentTarget.value })} placeholder="label" aria-label="Variable label" />
                <Input mono size_="sm" value={v.control} onChange={(e) => updateVar(i, { control: e.currentTarget.value })} placeholder="control" aria-label="Control value" />
                <Input mono size_="sm" value={v.treatment} onChange={(e) => updateVar(i, { treatment: e.currentTarget.value })} placeholder="treatment" aria-label="Treatment value" />
                <Input size_="sm" value={v.unit} onChange={(e) => updateVar(i, { unit: e.currentTarget.value })} placeholder="unit" aria-label="Unit" />
                <IconButton icon="close" label="Remove variable" size="sm" onClick={() => setVars((vs) => vs.filter((_, j) => j !== i))} disabled={vars.length === 1} />
                {!known && <Input mono size_="sm" className={s.varEditorCustom} value={v.key} onChange={(e) => updateVar(i, { key: e.currentTarget.value })} placeholder="custom UniverseConfig path, e.g. rules.max_age" aria-label="Custom variable path" />}
              </div>
            );
          })}
          <div>
            <Button size="sm" variant="ghost" icon="plus" onClick={() => setVars((vs) => [...vs, { key: '', label: '', control: '', treatment: '', unit: '' }])}>
              Add variable
            </Button>
          </div>
        </div>
      </div>

      <Field label="Replicates" hint="Control/treatment pairs; each gets a seed derived from the experiment seed">
        <NumberField value={replicates} onChange={(v) => setReplicates(Math.max(1, Math.min(12, Math.round(v))))} min={1} max={12} />
      </Field>
      <Field label="Duration" hint="Universes pause here and metrics are taken">
        <NumberField value={duration} onChange={(v) => setDuration(Math.max(100, Math.round(v)))} min={100} step={100} unit="ticks" />
      </Field>
      <Field label="Seed" hint="Blank draws one; it is recorded and reused for re-runs">
        <Input mono size_="sm" value={seed} onChange={(e) => setSeed(e.currentTarget.value)} placeholder="random" aria-label="Seed" />
      </Field>
      <Field label="Execution mode" hint={mode === 'lockstep' ? 'Clock waits for every decision' : 'Decisions apply whenever they arrive; model latency becomes a variable'}>
        <Select size_="sm" value={mode} onChange={(e) => setMode(e.currentTarget.value as ExecutionMode)} options={[{ value: 'lockstep', label: 'lockstep' }, { value: 'realtime', label: 'realtime' }]} />
      </Field>
      <Field label="Founding population" hint="Shared by both arms unless overridden by a variable">
        <NumberField value={population} onChange={(v) => setPopulation(Math.max(1, Math.min(200, Math.round(v))))} min={1} max={200} unit="agents" />
      </Field>
      <Field label="Model reasoning" hint={deterministicClaim ? 'Off: mechanics only, so the run is fully reproducible from its seed' : 'On: outcomes depend on model output and will not be claimed deterministic'}>
        <Toggle checked={reasoning} onChange={setReasoning} label="Enable model reasoning in both arms" />
      </Field>
      {hypotheses.length > 0 && (
        <Field label="Hypotheses under test" hint="Optional links to Observatory claims">
          <div className={s.hypPick}>
            {hypotheses.slice(0, 40).map((h) => {
              const on = hypothesisIds.includes(h.id);
              return (
                <label key={h.id} className={s.hypPickItem}>
                  <input type="checkbox" checked={on} onChange={(e) => setHypothesisIds((ids) => (e.currentTarget.checked ? [...ids, h.id] : ids.filter((x) => x !== h.id)))} />
                  <span className="mono">{h.id.toUpperCase()}</span>
                  <span>{h.title}</span>
                </label>
              );
            })}
          </div>
        </Field>
      )}
    </Modal>
  );
}
