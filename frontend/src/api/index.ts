import { env } from './env';
import type { DataSource } from './dataSource';
import { staticDataSource } from './staticDataSource';
import { httpDataSource } from './httpDataSource';
import { httpCommands, noEngineCommands, type SimulationCommands } from './commands';
import { httpMutations, noEngineMutations, type Mutations } from './mutations';

/** The single active read source for the whole interface. */
export const dataSource: DataSource = env.dataSource === 'http' ? httpDataSource : staticDataSource;

/** The single active command channel. */
export const commands: SimulationCommands = env.dataSource === 'http' ? httpCommands : noEngineCommands;

/** The single active mutation channel (create / apply / run). */
export const mutations: Mutations = env.dataSource === 'http' ? httpMutations : noEngineMutations;

export { NoEngineError, type Mutations } from './mutations';

export { env, resolveWsUrl } from './env';
export type { DataSource } from './dataSource';
export type { SimulationCommand, CommandResult, SimulationCommands } from './commands';
export { LiveClient, type ServerMessage, type ClientMessage, type ConnectionState } from './ws';
export { HttpError } from './http';
export { endpoints } from './endpoints';
