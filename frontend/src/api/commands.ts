import { endpoints } from './endpoints';
import { fetchJson } from './http';

/**
 * Write-side boundary: operator commands addressed to a universe's engine.
 * The frontend only *requests*; it never mutates clock or population locally.
 * Confirmation arrives as new state via REST or WebSocket.
 */
export type SimulationCommand =
  | { type: 'pause' }
  | { type: 'resume' }
  | { type: 'step'; ticks: number }
  | { type: 'setSpeed'; speed: number };

export interface CommandResult {
  accepted: boolean;
  /** Human-readable reason when not accepted. */
  reason?: string;
}

export interface SimulationCommands {
  send(universeId: string, command: SimulationCommand): Promise<CommandResult>;
}

export const httpCommands: SimulationCommands = {
  async send(universeId, command) {
    return fetchJson<CommandResult>(endpoints.universeCommand(universeId), { method: 'POST', body: command });
  },
};

/** With no engine attached, every command is declined explicitly rather than faked. */
export const noEngineCommands: SimulationCommands = {
  async send() {
    return { accepted: false, reason: 'No simulation engine connected.' };
  },
};
