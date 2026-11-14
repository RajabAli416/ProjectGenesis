import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/cn';
import s from './Panel.module.css';

export interface PanelProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  /** No padding inside the body (for tables and lists that manage their own). */
  flushBody?: boolean;
  /** Body scrolls independently; the panel must then be given a height. */
  scroll?: boolean;
  /** Panel fills the available flex space. */
  grow?: boolean;
  /** No border or background — a labelled region only. */
  flush?: boolean;
  as?: 'section' | 'div' | 'aside';
}

export function Panel({ title, subtitle, actions, flushBody, scroll, grow, flush, as: Tag = 'section', className, children, ...rest }: PanelProps) {
  return (
    <Tag className={cn(s.panel, flush && s.flush, grow && s.grow, className)} {...rest}>
      {(title || actions) && (
        <header className={s.header}>
          <div className={s.titleGroup}>
            {title && <h2 className={s.title}>{title}</h2>}
            {subtitle && <span className={s.subtitle}>{subtitle}</span>}
          </div>
          {actions && <div className={s.actions}>{actions}</div>}
        </header>
      )}
      <div className={cn(s.body, flushBody && s.bodyFlush, scroll && s.bodyScroll)}>{children}</div>
    </Tag>
  );
}
