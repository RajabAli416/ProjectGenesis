import type { SimulationClock, WorldEvent } from '@/domain';
import type { WorldSnapshot } from '@/viewport/types';

/**
 * Typed message envelope expected from the backend's WebSocket.
 * Extend this union as the backend protocol grows; consumers switch on `type`.
 */
export type ServerMessage =
  | { type: 'hello'; engineVersion: string }
  | { type: 'clock'; universeId: string; clock: SimulationClock }
  | { type: 'snapshot'; snapshot: WorldSnapshot }
  | { type: 'event'; event: WorldEvent }
  | { type: 'universe.changed'; universeId: string };

/** Client → server. Snapshots are only streamed for subscribed universes (null = all). */
export type ClientMessage = { type: 'subscribe'; universeIds: string[] | null };

export type ConnectionState = 'disabled' | 'connecting' | 'open' | 'reconnecting' | 'closed';

export interface LiveClientOptions {
  url: string;
  onMessage: (msg: ServerMessage) => void;
  onState: (state: ConnectionState) => void;
  /** Reconnect back-off ceiling in milliseconds. */
  maxBackoffMs?: number;
}

/**
 * Minimal reconnecting WebSocket client. It does no interpretation of messages;
 * it only parses JSON and reports connection state transitions.
 */
export class LiveClient {
  private ws: WebSocket | null = null;
  private attempt = 0;
  private timer: number | null = null;
  private closedByUser = false;
  private lastSubscribe: ClientMessage | null = null;

  constructor(private readonly opts: LiveClientOptions) {}

  connect(): void {
    this.closedByUser = false;
    this.open();
  }

  /** Send a client message; the latest subscription is replayed after a reconnect. */
  send(msg: ClientMessage): void {
    if (msg.type === 'subscribe') this.lastSubscribe = msg;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
  }

  close(): void {
    this.closedByUser = true;
    if (this.timer !== null) window.clearTimeout(this.timer);
    this.timer = null;
    this.ws?.close();
    this.ws = null;
    this.opts.onState('closed');
  }

  private open(): void {
    this.opts.onState(this.attempt === 0 ? 'connecting' : 'reconnecting');
    let ws: WebSocket;
    try {
      ws = new WebSocket(this.opts.url);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      this.attempt = 0;
      this.opts.onState('open');
      if (this.lastSubscribe) ws.send(JSON.stringify(this.lastSubscribe));
    };
    ws.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(String(ev.data)) as ServerMessage;
        if (parsed && typeof parsed === 'object' && 'type' in parsed) this.opts.onMessage(parsed);
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onclose = () => {
      this.ws = null;
      if (!this.closedByUser) this.scheduleReconnect();
    };
    ws.onerror = () => {
      /* onclose follows */
    };
  }

  private scheduleReconnect(): void {
    const ceiling = this.opts.maxBackoffMs ?? 15_000;
    const delay = Math.min(ceiling, 500 * 2 ** Math.min(this.attempt, 6));
    this.attempt += 1;
    this.opts.onState('reconnecting');
    this.timer = window.setTimeout(() => this.open(), delay);
  }
}
