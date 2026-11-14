import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';
import s from './DataList.module.css';

export interface DataRow {
  label: ReactNode;
  value: ReactNode;
  mono?: boolean;
  key?: string;
}

export function DataList({ rows, dense, alignLeft, className }: { rows: DataRow[]; dense?: boolean; alignLeft?: boolean; className?: string }) {
  return (
    <dl className={cn(s.list, dense && s.dense, alignLeft && s.left, className)}>
      {rows.map((r, i) => (
        <div key={r.key ?? i} className={s.row}>
          <dt className={s.label}>{r.label}</dt>
          <dd className={cn(s.value, r.mono !== false && s.valueMono)}>{r.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export interface ReadoutProps {
  label: ReactNode;
  value: ReactNode;
  unit?: ReactNode;
  note?: ReactNode;
  prefix?: ReactNode;
}

export function Readouts({ items, className }: { items: ReadoutProps[]; className?: string }) {
  return (
    <div className={cn(s.readouts, className)}>
      {items.map((it, i) => (
        <div key={i} className={s.readout}>
          <div className={s.readoutLabel}>
            {it.prefix}
            {it.label}
          </div>
          <div className={s.readoutValue}>
            {it.value}
            {it.unit && <span className={s.readoutUnit}>{it.unit}</span>}
          </div>
          {it.note && <div className={s.readoutNote}>{it.note}</div>}
        </div>
      ))}
    </div>
  );
}
