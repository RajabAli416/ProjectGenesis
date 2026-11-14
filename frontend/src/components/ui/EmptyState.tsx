import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import type { Resource } from '@/api/hooks';
import { Icon, type IconName } from './Icon';
import { Button } from './Button';
import s from './EmptyState.module.css';

export function EmptyState({ title, body, icon = 'dot', actions, center, className }: { title: ReactNode; body?: ReactNode; icon?: IconName; actions?: ReactNode; center?: boolean; className?: string }) {
  return (
    <div className={cn(s.empty, center && s.center, className)} role="status">
      <div className={s.glyph}>
        <Icon name={icon} size={14} />
      </div>
      <div className={s.title}>{title}</div>
      {body && <div className={s.body}>{body}</div>}
      {actions && <div className={s.actions}>{actions}</div>}
    </div>
  );
}

export function Notice({ children, tone, icon = 'info', className }: { children: ReactNode; tone?: 'attn'; icon?: IconName; className?: string }) {
  return (
    <div className={cn(s.notice, tone === 'attn' && s.noticeAttn, className)} role="note">
      <Icon name={icon} size={14} />
      <div>{children}</div>
    </div>
  );
}

export function LoadingState({ label = 'Loading', lines = 3 }: { label?: string; lines?: number }) {
  return (
    <div className={s.state} role="status" aria-live="polite" aria-label={label}>
      <div style={{ display: 'grid', gap: 10, flex: 1 }}>
        {Array.from({ length: lines }).map((_, i) => (
          <span key={i} className={s.skeleton} style={{ width: `${70 - i * 15}%` }} />
        ))}
      </div>
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error | null; onRetry?: () => void }) {
  return (
    <div className={cn(s.state, s.stateError)} role="alert">
      <Icon name="warn" size={14} />
      <span>{error?.message ?? 'Request failed'}</span>
      {onRetry && (
        <Button size="sm" variant="ghost" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

/**
 * Wraps the three resource states. Children render only when data is ready;
 * `isEmpty` lets callers treat e.g. an empty array as the empty state.
 */
export function ResourceBoundary<T>({ resource, isEmpty, empty, loadingLines, children }: { resource: Resource<T>; isEmpty?: (data: T) => boolean; empty?: ReactNode; loadingLines?: number; children: (data: T) => ReactNode }) {
  if (resource.status === 'loading' && resource.data === undefined) return <LoadingState lines={loadingLines} />;
  if (resource.status === 'error') return <ErrorState error={resource.error} onRetry={resource.reload} />;
  if (resource.data === undefined) return null;
  if (isEmpty?.(resource.data)) return <>{empty}</>;
  return <>{children(resource.data)}</>;
}
