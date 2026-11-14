import { createBrowserRouter } from 'react-router';
import { AppShell } from '@/components/shell/AppShell';
import { RouteError } from './RouteError';
import { AgentsPage, CivilizationPage, ExperimentsPage, ObservatoryPage, OverviewPage, RealitiesPage, SettingsPage, UniversePage } from './pages';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <OverviewPage /> },
      { path: 'universe', element: <UniversePage /> },
      { path: 'universe/:universeId', element: <UniversePage /> },
      { path: 'agents', element: <AgentsPage /> },
      { path: 'agents/:agentId', element: <AgentsPage /> },
      { path: 'civilization', element: <CivilizationPage /> },
      { path: 'realities', element: <RealitiesPage /> },
      { path: 'realities/:universeId', element: <RealitiesPage /> },
      { path: 'observatory', element: <ObservatoryPage /> },
      { path: 'observatory/:hypothesisId', element: <ObservatoryPage /> },
      { path: 'experiments', element: <ExperimentsPage /> },
      { path: 'experiments/:experimentId', element: <ExperimentsPage /> },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
]);
