import { dataSource } from '@/api';
import { SAMPLE_DATA } from '@/sample/meta';
import { Notice } from '@/components/ui/EmptyState';

/** Shown at the top of sections while the static fixtures are the active source. */
export function SampleNotice({ compact }: { compact?: boolean }) {
  if (dataSource.kind !== 'static') return null;
  return (
    <Notice tone="attn" icon="info">
      <strong style={{ color: 'var(--fg-1)', fontWeight: 500 }}>{SAMPLE_DATA.label}.</strong>{' '}
      {compact ? 'No simulation engine is connected.' : SAMPLE_DATA.description}
    </Notice>
  );
}
