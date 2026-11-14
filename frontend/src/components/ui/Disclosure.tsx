import { useId, useState, type ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { Icon } from './Icon';
import s from './Disclosure.module.css';

export function Disclosure({ title, meta, defaultOpen = false, children, className }: { title: ReactNode; meta?: ReactNode; defaultOpen?: boolean; children: ReactNode; className?: string }) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div className={cn(s.root, open && s.open, className)}>
      <button type="button" className={s.summary} aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)}>
        <Icon name="chevronRight" size={12} className={s.chevron} />
        <span>{title}</span>
        {meta && <span className={s.meta}>{meta}</span>}
      </button>
      {open && (
        <div id={id} className={s.content}>
          {children}
        </div>
      )}
    </div>
  );
}
