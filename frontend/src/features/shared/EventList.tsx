import { Link } from 'react-router';
import type { WorldEvent } from '@/domain';
import { useUniverseContext } from '@/app/universeContext';
import { StatusDot } from '@/components/ui/Indicators';
import { fmtTick } from '@/lib/format';
import { severityTone } from '@/lib/status';
import s from './EventList.module.css';

export function EventList({ events, showUniverse = true }: { events: WorldEvent[]; showUniverse?: boolean }) {
  const { byId } = useUniverseContext();
  return (
    <ol className={s.list}>
      {events.map((ev) => {
        const u = byId.get(ev.universeId);
        const agentRef = ev.refs?.find((r) => r.kind === 'agent');
        return (
          <li key={ev.id} className={s.item}>
            <span className={s.tick}>{fmtTick(ev.tick)}</span>
            <StatusDot tone={severityTone[ev.severity]} className={s.dot} />
            <div className={s.body}>
              <div className={s.summary}>{ev.summary}</div>
              <div className={s.meta}>
                {showUniverse && u && (
                  <Link to={`/realities/${u.id}`} className={s.ref}>
                    {u.code} {u.name}
                  </Link>
                )}
                <span>{ev.category}</span>
                {agentRef && (
                  <Link to={`/agents/${agentRef.id}`} className={s.ref}>
                    {agentRef.id.toUpperCase()}
                  </Link>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
