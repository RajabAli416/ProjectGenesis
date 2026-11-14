import { useState } from 'react';
import type { CreateUniverseRequest, ExecutionMode, OperatorSettings, Universe } from '@/domain';
import { mutations } from '@/api';
import { Field, Input, NumberField, Select, Toggle } from '@/components/ui';
import { Modal } from '@/components/ui/Modal';

export interface NewUniverseDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated: (u: Universe) => void;
  /** Current operator settings; used only to pre-fill the form. */
  defaults?: OperatorSettings | null;
}

/**
 * Creates a root universe. Every value is sent to the backend as an explicit
 * override on its UniverseConfig; blank seed lets the engine draw one and report it back.
 */
export function NewUniverseDialog({ open, onClose, onCreated, defaults }: NewUniverseDialogProps) {
  const sim = defaults?.simulation;
  const [name, setName] = useState('');
  const [seed, setSeed] = useState('');
  const [population, setPopulation] = useState(sim?.initialPopulation ?? 5);
  const [width, setWidth] = useState(sim?.worldWidth ?? 256);
  const [height, setHeight] = useState(sim?.worldHeight ?? 160);
  const [mode, setMode] = useState<ExecutionMode>('realtime');
  const [reasoning, setReasoning] = useState(true);
  const [start, setStart] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cell = sim?.cellSize ?? 8;
  const snap = (v: number) => Math.max(cell * 4, Math.round(v / cell) * cell);

  const submit = async () => {
    setBusy(true);
    setError(null);
    const req: CreateUniverseRequest = {
      name: name.trim() || undefined,
      seed: seed.trim() || null,
      initialPopulation: population,
      mode,
      start,
      config: { width: snap(width), height: snap(height), 'reasoning.enabled': reasoning },
    };
    try {
      const u = await mutations.createUniverse(req);
      onCreated(u);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create universe');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} title="New universe" onClose={onClose} onSubmit={submit} submitLabel={start ? 'Create and run' : 'Create paused'} busy={busy} error={error}>
      <Field label="Name" hint="Optional; the engine numbers universes itself">
        <Input value={name} onChange={(e) => setName(e.currentTarget.value)} placeholder="e.g. Baseline hazard world" aria-label="Universe name" size_="sm" autoFocus />
      </Field>
      <Field label="Seed" hint="Blank draws a random seed, recorded for reproduction">
        <Input mono value={seed} onChange={(e) => setSeed(e.currentTarget.value)} placeholder="random" aria-label="Seed" size_="sm" />
      </Field>
      <Field label="Founding population">
        <NumberField value={population} onChange={(v) => setPopulation(Math.max(1, Math.min(200, Math.round(v))))} min={1} max={200} unit="agents" />
      </Field>
      <Field label="Extent" hint={`World units; snapped to the ${cell}-unit cell size`}>
        <NumberField value={width} onChange={setWidth} onBlur={() => setWidth(snap(width))} min={cell * 4} step={cell} aria-label="Width" />
        <span className="faint">×</span>
        <NumberField value={height} onChange={setHeight} onBlur={() => setHeight(snap(height))} min={cell * 4} step={cell} aria-label="Height" unit="units" />
      </Field>
      <Field label="Execution mode" hint={mode === 'lockstep' ? 'Clock waits for every model decision — reproducible, slower' : 'Clock runs on; decisions apply when they arrive'}>
        <Select
          size_="sm"
          value={mode}
          onChange={(e) => setMode(e.currentTarget.value as ExecutionMode)}
          options={[
            { value: 'realtime', label: 'realtime' },
            { value: 'lockstep', label: 'lockstep' },
          ]}
        />
      </Field>
      <Field label="Model reasoning" hint={reasoning ? 'Agents deliberate with the configured provider when triggered' : 'Reflex policy only — no inference calls'}>
        <Toggle checked={reasoning} onChange={setReasoning} label="Enable model reasoning" />
      </Field>
      <Field label="Start immediately">
        <Toggle checked={start} onChange={setStart} label="Start immediately" />
      </Field>
    </Modal>
  );
}
