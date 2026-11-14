const intFmt = new Intl.NumberFormat('en-US');
const compactFmt = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });

export const fmtInt = (n: number): string => intFmt.format(Math.round(n));

export const fmtCompact = (n: number): string => (Math.abs(n) < 10_000 ? intFmt.format(Math.round(n)) : compactFmt.format(n));

/** Tick counter with thousands separators; ticks are the engine's unit of time. */
export const fmtTick = (tick: number): string => intFmt.format(tick);

export const fmtPct = (v: number, digits = 0): string => `${(v * 100).toFixed(digits)}%`;

export const fmtFixed = (v: number, digits = 2): string => v.toFixed(digits);

export const fmtSigned = (v: number, digits = 2): string => `${v > 0 ? '+' : ''}${v.toFixed(digits)}`;

export const fmtCoord = (x: number, y: number): string => `${Math.round(x)}, ${Math.round(y)}`;

/** Relative-time label for an ISO timestamp against now. */
export function fmtRelative(iso: string, now: Date = new Date()): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const s = Math.max(0, Math.round((now.getTime() - then) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}

export function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toISOString().replace('T', ' ').slice(0, 16) + 'Z';
}

export const fmtSpeed = (speed: number): string => (Number.isInteger(speed) ? `${speed}×` : `${speed.toFixed(1)}×`);

export const titleCase = (s: string): string => s.charAt(0).toUpperCase() + s.slice(1);

/** Agent ids in fixtures look like "a-0412"; present them as "A-0412". */
export const fmtAgentCode = (id: string): string => id.toUpperCase();
