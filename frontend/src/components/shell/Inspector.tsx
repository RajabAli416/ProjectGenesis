import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { IconButton } from '@/components/ui/Button';
import { useMediaQuery } from '@/lib/useMediaQuery';
import s from './Inspector.module.css';

export interface InspectorProps {
  title: ReactNode;
  open: boolean;
  onClose: () => void;
  actions?: ReactNode;
  children: ReactNode;
}

/**
 * Right-hand detail drawer. Docked at ≥1280px, overlaid below that.
 */
export function Inspector({ title, open, onClose, actions, children }: InspectorProps) {
  const overlay = useMediaQuery('(max-width: 1279px)');
  if (!open) return null;

  return (
    <>
      {overlay && <div className={s.scrim} onClick={onClose} aria-hidden="true" />}
      <aside className={cn(s.inspector, overlay && s.overlay)} aria-label="Inspector">
        <header className={s.header}>
          <h2 className={s.title}>{title}</h2>
          <div style={{ display: 'flex', gap: 2 }}>
            {actions}
            <IconButton icon="close" label="Close inspector" size="sm" onClick={onClose} />
          </div>
        </header>
        <div className={s.body}>{children}</div>
      </aside>
    </>
  );
}

export function InspectorSection({ title, meta, children }: { title: ReactNode; meta?: ReactNode; children: ReactNode }) {
  return (
    <section className={s.section}>
      <h3 className={s.sectionTitle}>
        <span>{title}</span>
        {meta && <span className={cn(s.sectionMeta, 'faint')}>{meta}</span>}
      </h3>
      {children}
    </section>
  );
}
