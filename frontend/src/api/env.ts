export type DataSourceKind = 'static' | 'http';

function readDataSource(): DataSourceKind {
  const raw = (import.meta.env.VITE_DATA_SOURCE as string | undefined)?.trim().toLowerCase();
  return raw === 'http' ? 'http' : 'static';
}

export const env = {
  dataSource: readDataSource(),
  apiBaseUrl: ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api').replace(/\/$/, ''),
  wsUrl: ((import.meta.env.VITE_WS_URL as string | undefined) ?? '').trim(),
} as const;

/** Derive a WebSocket URL from the page origin when none is configured. */
export function resolveWsUrl(): string {
  if (env.wsUrl) return env.wsUrl;
  if (typeof window === 'undefined') return '';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws`;
}
