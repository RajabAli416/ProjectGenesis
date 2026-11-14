import { createContext, useContext } from 'react';
import type { Universe } from '@/domain';
import type { Resource } from '@/api/hooks';

export interface UniverseContextValue {
  resource: Resource<Universe[]>;
  universes: Universe[];
  byId: Map<string, Universe>;
  active: Universe | null;
  setActive: (id: string | null) => void;
}

export const UniverseCtx = createContext<UniverseContextValue | null>(null);

export function useUniverseContext(): UniverseContextValue {
  const v = useContext(UniverseCtx);
  if (!v) throw new Error('useUniverseContext must be used within UniverseProvider');
  return v;
}
