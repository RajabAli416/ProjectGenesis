import { create } from 'zustand';
import type { SimulationClock, WorldEvent } from '@/domain';
import type { WorldSnapshot } from '@/viewport/types';
import type { ConnectionState, LiveClient, ServerMessage } from '@/api/ws';
import { env } from '@/api/env';

/**
 * Holds what the backend has told us over the live channel. Clocks and
 * snapshots here are as received — the frontend never increments or
 * interpolates them.
 */
interface ConnectionStore {
  state: ConnectionState;
  engineVersion: string | null;
  clocks: Record<string, SimulationClock>;
  /** Latest streamed world snapshot per universe (only for subscribed universes). */
  snapshots: Record<string, WorldSnapshot>;
  liveEvents: WorldEvent[];
  lastMessageAt: string | null;
  /** Incremented on every `universe.changed`; consumers reload the catalogue when it moves. */
  catalogRevision: number;
  /** Per-universe revision counters, for targeted reloads (agents, civilization, events). */
  universeRevisions: Record<string, number>;

  client: LiveClient | null;

  setState: (s: ConnectionState) => void;
  setClient: (c: LiveClient | null) => void;
  ingest: (msg: ServerMessage) => void;
  /** Ask the backend to stream snapshots for these universes (null = all). */
  subscribe: (universeIds: string[] | null) => void;
}

const MAX_LIVE_EVENTS = 200;

export const useConnectionStore = create<ConnectionStore>()((set, get) => ({
  state: env.dataSource === 'http' ? 'connecting' : 'disabled',
  engineVersion: null,
  clocks: {},
  snapshots: {},
  liveEvents: [],
  lastMessageAt: null,
  catalogRevision: 0,
  universeRevisions: {},
  client: null,

  setState: (state) => set({ state }),
  setClient: (client) => set({ client }),
  subscribe: (universeIds) => get().client?.send({ type: 'subscribe', universeIds }),
  ingest: (msg) =>
    set((s) => {
      const lastMessageAt = new Date().toISOString();
      switch (msg.type) {
        case 'hello':
          return { engineVersion: msg.engineVersion, lastMessageAt };
        case 'clock':
          return { clocks: { ...s.clocks, [msg.universeId]: msg.clock }, lastMessageAt };
        case 'snapshot': {
          const prev = s.snapshots[msg.snapshot.universeId];
          // Frames can arrive out of order under load; never regress the tick.
          if (prev && prev.tick > msg.snapshot.tick) return { lastMessageAt };
          return { snapshots: { ...s.snapshots, [msg.snapshot.universeId]: msg.snapshot }, lastMessageAt };
        }
        case 'event':
          return { liveEvents: [msg.event, ...s.liveEvents].slice(0, MAX_LIVE_EVENTS), lastMessageAt };
        case 'universe.changed':
          return {
            catalogRevision: s.catalogRevision + 1,
            universeRevisions: { ...s.universeRevisions, [msg.universeId]: (s.universeRevisions[msg.universeId] ?? 0) + 1 },
            lastMessageAt,
          };
        default:
          return { lastMessageAt };
      }
    }),
}));
