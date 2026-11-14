import { cn } from '@/lib/cn';
import { Icon, type IconName } from './Icon';
import s from './Segmented.module.css';

export interface SegmentedOption<T extends string | number> {
  value: T;
  label?: string;
  icon?: IconName;
  title?: string;
  disabled?: boolean;
}

export interface SegmentedProps<T extends string | number> {
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  size?: 'md' | 'sm';
  'aria-label': string;
  className?: string;
  mono?: boolean;
}

export function Segmented<T extends string | number>({ options, value, onChange, size = 'md', className, mono, ...rest }: SegmentedProps<T>) {
  return (
    <div role="radiogroup" aria-label={rest['aria-label']} className={cn(s.group, size === 'sm' && s.sm, className)}>
      {options.map((o) => (
        <button
          key={String(o.value)}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          aria-label={o.label ?? o.title}
          title={o.title ?? o.label}
          disabled={o.disabled}
          className={cn(s.item, o.value === value && s.active, mono && 'mono')}
          onClick={() => onChange(o.value)}
        >
          {o.icon && <Icon name={o.icon} size={size === 'sm' ? 13 : 14} />}
          {o.label}
        </button>
      ))}
    </div>
  );
}
