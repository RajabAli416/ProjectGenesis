import type { CSSProperties, ReactNode } from 'react';
import { cn } from '@/lib/cn';
import type { Tone } from '@/lib/status';
import { fmtPct, fmtSigned } from '@/lib/format';
import s from './Indicators.module.css';

const toneClass = (prefix: 'dot' | 'tag' | 'meter', tone: Tone | undefined) => {
  if (!tone) return undefined;
  const key = `${prefix}${tone.charAt(0).toUpperCase()}${tone.slice(1)}`;
  return s[key as keyof typeof s];
};

export function StatusDot({ tone = 'neutral', pulse, className }: { tone?: Tone; pulse?: boolean; className?: string }) {
  return <span className={cn(s.dot, toneClass('dot', tone), pulse && s.pulse, className)} style={pulse ? ({ color: `var(--acc-${tone})` } as CSSProperties) : undefined} />;
}

export function StatusLabel({ tone, pulse, children, className }: { tone: Tone; pulse?: boolean; children: ReactNode; className?: string }) {
  return (
    <span className={cn(s.statusLabel, className)}>
      <StatusDot tone={tone} pulse={pulse} />
      {children}
    </span>
  );
}

export function Tag({ tone, mono, children, className, title }: { tone?: Tone; mono?: boolean; children: ReactNode; className?: string; title?: string }) {
  return (
    <span className={cn(s.tag, tone && tone !== 'neutral' && toneClass('tag', tone), mono && s.tagMono, className)} title={title}>
      {children}
    </span>
  );
}

export interface MeterProps {
  /** 0..1 for unipolar; -1..1 when bipolar. */
  value: number;
  tone?: Tone;
  bipolar?: boolean;
  showValue?: boolean;
  format?: (v: number) => string;
  tall?: boolean;
  className?: string;
  style?: CSSProperties;
  'aria-label'?: string;
}

export function Meter({ value, tone, bipolar, showValue = true, format, tall, className, style, ...rest }: MeterProps) {
  const clamped = bipolar ? Math.max(-1, Math.min(1, value)) : Math.max(0, Math.min(1, value));
  const label = format ? format(clamped) : bipolar ? fmtSigned(clamped) : fmtPct(clamped);
  const fillStyle: CSSProperties = bipolar
    ? clamped >= 0
      ? { left: '50%', width: `${(clamped / 2) * 100}%` }
      : { left: `${50 + (clamped / 2) * 100}%`, width: `${(-clamped / 2) * 100}%` }
    : { width: `${clamped * 100}%` };
  return (
    <div
      className={cn(s.meter, toneClass('meter', tone), bipolar && s.bipolar, tall && s.meterTall, className)}
      style={style}
      role="meter"
      aria-valuemin={bipolar ? -1 : 0}
      aria-valuemax={1}
      aria-valuenow={clamped}
      aria-label={rest['aria-label']}
    >
      <div className={s.meterTrack}>
        <div className={s.meterFill} style={fillStyle} />
      </div>
      {showValue && <span className={s.meterValue}>{label}</span>}
    </div>
  );
}
