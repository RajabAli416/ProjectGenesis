import type { IconName } from '@/components/ui/Icon';

export interface SectionDef {
  id: string;
  path: string;
  label: string;
  short: string;
  icon: IconName;
  /** Keyboard shortcut (digit) */
  key: string;
  description: string;
}

export const sections: SectionDef[] = [
  { id: 'overview', path: '/', label: 'Overview', short: 'Ovw', icon: 'overview', key: '1', description: 'Status of universes, populations and recent events' },
  { id: 'universe', path: '/universe', label: 'Universe', short: 'Uni', icon: 'universe', key: '2', description: 'Primary observation viewport' },
  { id: 'agents', path: '/agents', label: 'Agents', short: 'Agt', icon: 'agents', key: '3', description: 'Individual identities, lineage, knowledge and memory' },
  { id: 'civilization', path: '/civilization', label: 'Civilization', short: 'Civ', icon: 'civilization', key: '4', description: 'Population development, technology and institutions' },
  { id: 'realities', path: '/realities', label: 'Recursive Realities', short: 'Rec', icon: 'realities', key: '5', description: 'Parent and child universe hierarchy' },
  { id: 'observatory', path: '/observatory', label: 'Research Observatory', short: 'Obs', icon: 'observatory', key: '6', description: 'Hypotheses, evidence and reasoning' },
  { id: 'experiments', path: '/experiments', label: 'Experiments', short: 'Exp', icon: 'experiments', key: '7', description: 'Configurations, variables and run history' },
  { id: 'settings', path: '/settings', label: 'Settings', short: 'Set', icon: 'settings', key: '8', description: 'Providers, reasoning, simulation and persistence' },
];

export const sectionForPath = (pathname: string): SectionDef =>
  sections.find((s) => (s.path === '/' ? pathname === '/' : pathname.startsWith(s.path))) ?? sections[0];
