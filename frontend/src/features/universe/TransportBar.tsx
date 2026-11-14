import { useState } from 'react';
import type { Universe } from '@/domain';
import { commands, type SimulationCommand } from '@/api';
import type { ViewportTool } from '@/viewport/types';
import { IconButton, Segmented, StatusDot, Kbd } from '@/components/ui';
import { fmtSpeed } from '@/lib/format';
import { universeTone } from '@/lib/status';
import s from './UniversePage.module.css';

const SPEEDS = [0.5, 1, 2, 8] as const;

export interface TransportBarProps {
  universe: Universe | null;
  tool: ViewportTool;
  onTool: (t: ViewportTool) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
}

/**
 * Operator transport. Every control dispatches a SimulationCommand through
 * the active command channel; the bar reflects the result but never changes
 * the clock itself.
 */
export function TransportBar({ universe, tool, onTool, onZoomIn, onZoomOut, onFit }: TransportBarProps) {
  const [pending, setPending] = useState<SimulationCommand['type'] | null>(null);
  const [lastResult, setLastResult] = useState<{ accepted: boolean; reason?: string } | null>(null);

  const dispatch = async (cmd: SimulationCommand) => {
    if (!universe) return;
    setPending(cmd.type);
    try {
      const res = await commands.send(universe.id, cmd);
      setLastResult(res);
    } catch (e) {
      setLastResult({ accepted: false, reason: e instanceof Error ? e.message : 'Command failed' });
    } finally {
      setPending(null);
    }
  };

  const running = universe?.status === 'running';
  const controllable = !!universe && universe.status !== 'terminated' && universe.status !== 'archived';

  return (
    <div className={s.transport} role="toolbar" aria-label="Simulation transport">
      <div className={s.transportGroup}>
        {running ? (
          <IconButton icon="pause" label="Pause (Space)" variant="outline" disabled={!controllable || pending !== null} onClick={() => dispatch({ type: 'pause' })} />
        ) : (
          <IconButton icon="play" label="Resume (Space)" variant="outline" disabled={!controllable || pending !== null} onClick={() => dispatch({ type: 'resume' })} />
        )}
        <IconButton icon="step" label="Step one tick" variant="outline" disabled={!controllable || running || pending !== null} onClick={() => dispatch({ type: 'step', ticks: 1 })} />
      </div>

      <span className={s.transportSep} />

      <div className={s.transportGroup}>
        <span className={s.transportLabel}>Speed</span>
        <Segmented
          aria-label="Simulation speed"
          size="sm"
          mono
          value={universe?.clock.speed ?? 1}
          onChange={(v) => dispatch({ type: 'setSpeed', speed: v })}
          options={SPEEDS.map((v) => ({ value: v, label: fmtSpeed(v), disabled: !controllable }))}
        />
      </div>

      <span className={s.transportSep} />

      <div className={s.transportGroup}>
        <span className={s.transportLabel}>Tool</span>
        <Segmented<ViewportTool>
          aria-label="Viewport tool"
          size="sm"
          value={tool}
          onChange={onTool}
          options={[
            { value: 'select', icon: 'cursor', title: 'Select (V)' },
            { value: 'pan', icon: 'hand', title: 'Pan (H)' },
          ]}
        />
      </div>

      <span className={s.transportSep} />

      <div className={s.transportGroup}>
        <span className={s.transportLabel}>Zoom</span>
        <IconButton icon="zoomOut" label="Zoom out (−)" size="sm" onClick={onZoomOut} />
        <IconButton icon="zoomIn" label="Zoom in (+)" size="sm" onClick={onZoomIn} />
        <IconButton icon="fit" label="Fit world (F)" size="sm" onClick={onFit} />
      </div>

      <span className={s.transportSpacer} />

      <span className={s.engineNote}>
        {universe && <StatusDot tone={universeTone[universe.status]} />}
        {universe ? (
          lastResult && !lastResult.accepted ? (
            <span className={s.engineNoteAttn}>{lastResult.reason ?? 'Command declined'}</span>
          ) : lastResult?.accepted ? (
            'Command accepted'
          ) : universe.clock.rate > 0 ? (
            `${universe.clock.rate} ticks/s`
          ) : (
            'Clock halted'
          )
        ) : (
          'No universe selected'
        )}
        <span style={{ marginLeft: 8, display: 'inline-flex', gap: 4 }}>
          <Kbd>Space</Kbd>
        </span>
      </span>
    </div>
  );
}
