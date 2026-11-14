import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react';
import { cn } from '@/lib/cn';
import { Icon } from './Icon';
import s from './Forms.module.css';

/* ---- Field: label + hint + control in an aligned row ---- */

export function Field({ label, hint, children, htmlFor }: { label: ReactNode; hint?: ReactNode; children: ReactNode; htmlFor?: string }) {
  return (
    <div className={s.field}>
      <label className={s.fieldLabel} htmlFor={htmlFor}>
        <span className={s.fieldName}>{label}</span>
        {hint && <span className={s.fieldHint}>{hint}</span>}
      </label>
      <div className={s.fieldControl}>{children}</div>
    </div>
  );
}

/* ---- Text / number inputs ---- */

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  mono?: boolean;
  narrow?: boolean;
  size_?: 'md' | 'sm';
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ mono, narrow, size_ = 'md', className, ...rest }, ref) {
  return <input ref={ref} className={cn(s.input, mono && s.inputMono, narrow && s.inputNarrow, size_ === 'sm' && s.inputSm, className)} {...rest} />;
});

export function SearchInput({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className={cn(s.inputWithIcon, className)}>
      <Icon name="search" size={14} />
      <input type="search" className={s.input} {...rest} />
    </div>
  );
}

export interface NumberFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'value'> {
  value: number;
  onChange: (v: number) => void;
  unit?: string;
}

export function NumberField({ value, onChange, unit, className, ...rest }: NumberFieldProps) {
  return (
    <>
      <input
        type="number"
        className={cn(s.input, s.inputMono, s.inputNarrow, className)}
        value={Number.isFinite(value) ? value : ''}
        onChange={(e) => {
          const n = e.currentTarget.valueAsNumber;
          if (Number.isFinite(n)) onChange(n);
        }}
        {...rest}
      />
      {unit && <span className="faint" style={{ fontSize: 'var(--fs-11)', minWidth: '3em' }}>{unit}</span>}
    </>
  );
}

/* ---- Select ---- */

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  options: Array<{ value: string; label: string; disabled?: boolean }>;
  mono?: boolean;
  size_?: 'md' | 'sm';
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select({ options, mono, size_ = 'md', className, ...rest }, ref) {
  return (
    <span className={cn(s.selectWrap, className)}>
      <select ref={ref} className={cn(s.input, s.select, mono && s.inputMono, size_ === 'sm' && s.inputSm)} {...rest}>
        {options.map((o) => (
          <option key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </option>
        ))}
      </select>
      <Icon name="chevronDown" size={12} />
    </span>
  );
});

/* ---- Toggle ---- */

export function Toggle({ checked, onChange, disabled, label }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      className={cn(s.toggle, checked && s.toggleOn)}
      onClick={() => onChange(!checked)}
    />
  );
}

/* ---- Slider ---- */

export function Slider({ value, onChange, min, max, step = 1, format, label }: { value: number; onChange: (v: number) => void; min: number; max: number; step?: number; format?: (v: number) => string; label: string }) {
  const id = useId();
  return (
    <div className={s.sliderRow}>
      <input
        id={id}
        type="range"
        className={s.slider}
        min={min}
        max={max}
        step={step}
        value={value}
        aria-label={label}
        onChange={(e) => onChange(Number(e.currentTarget.value))}
      />
      <output htmlFor={id} className={s.sliderValue}>
        {format ? format(value) : value}
      </output>
    </div>
  );
}

/* ---- Kbd ---- */

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className={s.kbd}>{children}</kbd>;
}
