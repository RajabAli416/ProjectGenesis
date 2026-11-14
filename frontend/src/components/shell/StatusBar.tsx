import { dataSource, env } from '@/api';
import { useChromeStore } from '@/store/chromeStore';
import { useConnectionStore } from '@/store/connectionStore';
import { StatusDot } from '@/components/ui/Indicators';
import { cn } from '@/lib/cn';
import { fmtRelative } from '@/lib/format';
import s from './StatusBar.module.css';

export function StatusBar() {
  const statusLeft = useChromeStore((c) => c.statusLeft);
  const statusRight = useChromeStore((c) => c.statusRight);
  const engineVersion = useConnectionStore((c) => c.engineVersion);
  const lastMessageAt = useConnectionStore((c) => c.lastMessageAt);

  return (
    <footer className={s.bar} aria-label="Status">
      {dataSource.kind === 'static' ? (
        <span className={cn(s.item, s.sample)} title="Static fixtures bundled with the interface. No simulation engine is connected; nothing shown was produced by agents.">
          <StatusDot tone="attn" />
          {dataSource.label}
        </span>
      ) : (
        <span className={s.item}>
          <StatusDot tone={engineVersion ? 'live' : 'neutral'} />
          {dataSource.label}
          {engineVersion && <span className={s.mono}>v{engineVersion}</span>}
        </span>
      )}

      <span className={s.sep} />
      <span className={cn(s.item, s.mono, s.hideNarrow)} title="Configured data source">
        source={env.dataSource}
      </span>

      {statusLeft && (
        <>
          <span className={s.sep} />
          <span className={cn(s.item, s.mono)}>{statusLeft}</span>
        </>
      )}

      <span className={s.spacer} />

      {statusRight && <span className={cn(s.item, s.mono)}>{statusRight}</span>}
      {lastMessageAt && (
        <>
          <span className={s.sep} />
          <span className={cn(s.item, s.hideNarrow)}>last message {fmtRelative(lastMessageAt)}</span>
        </>
      )}
    </footer>
  );
}
