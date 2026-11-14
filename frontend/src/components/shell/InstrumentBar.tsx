import { useLocation } from 'react-router';
import { sectionForPath } from '@/app/sections';
import { useUniverseContext } from '@/app/universeContext';
import { useConnectionStore } from '@/store/connectionStore';
import { useUiStore } from '@/store/uiStore';
import { Select } from '@/components/ui/Forms';
import { IconButton } from '@/components/ui/Button';
import { StatusDot } from '@/components/ui/Indicators';
import { fmtSpeed, fmtTick } from '@/lib/format';
import { universeTone } from '@/lib/status';
import type { ConnectionState } from '@/api/ws';
import s from './InstrumentBar.module.css';

const connLabel: Record<ConnectionState, { label: string; tone: 'live' | 'attn' | 'crit' | 'neutral' }> = {
  disabled: { label: 'No engine', tone: 'neutral' },
  connecting: { label: 'Connecting', tone: 'attn' },
  open: { label: 'Live', tone: 'live' },
  reconnecting: { label: 'Reconnecting', tone: 'attn' },
  closed: { label: 'Disconnected', tone: 'crit' },
};

export function InstrumentBar({ detail, showInspectorToggle }: { detail?: string; showInspectorToggle?: boolean }) {
  const { pathname } = useLocation();
  const section = sectionForPath(pathname);
  const { universes, active, setActive } = useUniverseContext();
  const conn = useConnectionStore((st) => st.state);
  const inspectorOpen = useUiStore((st) => st.inspectorOpen);
  const toggleInspector = useUiStore((st) => st.toggleInspector);

  const c = connLabel[conn];

  return (
    <header className={s.bar}>
      <div className={s.crumbs}>
        <h1 className={s.section}>{section.label}</h1>
        {detail && (
          <>
            <span className={s.sep}>/</span>
            <span className={s.detail}>{detail}</span>
          </>
        )}
      </div>

      <div className={s.group}>
        {universes.length > 0 && (
          <Select
            className={s.universeSelect}
            aria-label="Active universe"
            value={active?.id ?? ''}
            onChange={(e) => setActive(e.currentTarget.value || null)}
            options={universes.map((u) => ({ value: u.id, label: `${u.code}  ${u.name}` }))}
            mono
          />
        )}

        <div className={s.clock} aria-label="Simulation clock" title="Tick count of the active universe, as last reported by the engine">
          <span className={s.clockLabel}>Tick</span>
          <span>{active ? fmtTick(active.clock.tick) : '—'}</span>
          <span className={s.clockSep} />
          <span className={s.clockRate}>
            {active ? (active.clock.rate > 0 ? `${active.clock.rate} t/s · ${fmtSpeed(active.clock.speed)}` : 'halted') : '—'}
          </span>
          {active && <StatusDot tone={universeTone[active.status]} pulse={active.status === 'running' && conn === 'open'} />}
        </div>

        <div className={s.conn} title="Backend connection state">
          <StatusDot tone={c.tone} />
          {c.label}
        </div>

        {showInspectorToggle && <IconButton icon="panelRight" label={inspectorOpen ? 'Hide inspector' : 'Show inspector'} pressed={inspectorOpen} onClick={toggleInspector} />}
      </div>
    </header>
  );
}
