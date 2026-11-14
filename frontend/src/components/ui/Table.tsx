import { useMemo, useState, type ReactNode } from 'react';
import { cn } from '@/lib/cn';
import s from './Table.module.css';

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  /** Right-aligned mono numeric column. */
  num?: boolean;
  mono?: boolean;
  width?: number | string;
  /** Provide to make the column sortable. */
  sortValue?: (row: T) => number | string;
  /** This column absorbs leftover width. */
  fill?: boolean;
}

export interface TableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  selectedKey?: string | null;
  rowClassName?: (row: T) => string | undefined;
  compact?: boolean;
  initialSort?: { key: string; dir: 'asc' | 'desc' };
  className?: string;
  'aria-label'?: string;
  emptyMessage?: ReactNode;
}

export function Table<T>({ columns, rows, rowKey, onRowClick, selectedKey, rowClassName, compact, initialSort, className, emptyMessage, ...rest }: TableProps<T>) {
  const [sort, setSort] = useState(initialSort ?? null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const sv = col.sortValue;
    const dir = sort.dir === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = sv(a);
      const bv = sv(b);
      if (av === bv) return 0;
      return (av < bv ? -1 : 1) * dir;
    });
  }, [rows, sort, columns]);

  const toggleSort = (key: string) =>
    setSort((cur) => (cur?.key === key ? { key, dir: cur.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' }));

  return (
    <div className={cn(s.wrap, className)}>
      <table className={cn(s.table, compact && s.compact)} aria-label={rest['aria-label']}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                style={c.width ? { width: c.width } : undefined}
                className={cn(c.num && s.num, c.sortValue && s.sortable)}
                onClick={c.sortValue ? () => toggleSort(c.key) : undefined}
                aria-sort={sort?.key === c.key ? (sort.dir === 'asc' ? 'ascending' : 'descending') : undefined}
              >
                {c.header}
                {sort?.key === c.key && <span className={s.sortIcon}>{sort.dir === 'asc' ? '↑' : '↓'}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className={s.tbody}>
          {sorted.length === 0 && emptyMessage && (
            <tr>
              <td colSpan={columns.length} className="faint" style={{ height: 48, textAlign: 'center' }}>
                {emptyMessage}
              </td>
            </tr>
          )}
          {sorted.map((row) => {
            const k = rowKey(row);
            return (
              <tr
                key={k}
                className={cn(s.row, onRowClick && s.clickable, selectedKey === k && s.selected, rowClassName?.(row))}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                tabIndex={onRowClick ? 0 : undefined}
                onKeyDown={
                  onRowClick
                    ? (e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          onRowClick(row);
                        }
                      }
                    : undefined
                }
                aria-selected={selectedKey === k || undefined}
              >
                {columns.map((c) => (
                  <td key={c.key} className={cn(c.num && s.num, c.mono && s.mono)} style={c.fill ? { width: '100%' } : undefined}>
                    {c.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
