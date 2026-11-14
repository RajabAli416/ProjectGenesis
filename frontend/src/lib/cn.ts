export type ClassValue = string | number | null | undefined | false | Record<string, boolean | null | undefined>;

/** Tiny class-name joiner: cn('a', cond && 'b', { c: flag }) */
export function cn(...parts: ClassValue[]): string {
  const out: string[] = [];
  for (const p of parts) {
    if (!p) continue;
    if (typeof p === 'string' || typeof p === 'number') out.push(String(p));
    else for (const [k, v] of Object.entries(p)) if (v) out.push(k);
  }
  return out.join(' ');
}
