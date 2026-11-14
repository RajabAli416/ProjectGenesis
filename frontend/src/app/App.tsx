import { RouterProvider } from 'react-router';
import { router } from './router';
import { UniverseProvider } from './UniverseProvider';
import { LiveConnection } from './LiveConnection';

export function App() {
  return (
    <UniverseProvider>
      <LiveConnection />
      <RouterProvider router={router} />
    </UniverseProvider>
  );
}
