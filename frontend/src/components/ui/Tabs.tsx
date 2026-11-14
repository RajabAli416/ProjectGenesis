import { cn } from '@/lib/cn';
import s from './Tabs.module.css';

export interface TabItem<T extends string> {
  value: T;
  label: string;
  count?: number;
}

export function Tabs<T extends string>({ items, value, onChange, className, 'aria-label': ariaLabel }: { items: TabItem<T>[]; value: T; onChange: (v: T) => void; className?: string; 'aria-label': string }) {
  return (
    <div role="tablist" aria-label={ariaLabel} className={cn(s.list, className)}>
      {items.map((t) => (
        <button
          key={t.value}
          role="tab"
          type="button"
          aria-selected={t.value === value}
          className={cn(s.tab, t.value === value && s.active)}
          onClick={() => onChange(t.value)}
        >
          {t.label}
          {t.count !== undefined && <span className={s.count}>{t.count}</span>}
        </button>
      ))}
    </div>
  );
}
