import { isRouteErrorResponse, useRouteError } from 'react-router';
import { EmptyState } from '@/components/ui/EmptyState';
import { Button } from '@/components/ui/Button';

export function RouteError() {
  const err = useRouteError();
  const title = isRouteErrorResponse(err) ? `${err.status} ${err.statusText}` : 'Interface error';
  const body = isRouteErrorResponse(err) ? err.data : err instanceof Error ? err.message : 'An unexpected error occurred while rendering this section.';
  return (
    <div style={{ display: 'flex', flex: 1, alignItems: 'center', justifyContent: 'center', height: '100%' }}>
      <EmptyState
        icon="warn"
        title={title}
        body={String(body)}
        center
        actions={
          <Button size="sm" onClick={() => window.location.assign('/')}>
            Return to overview
          </Button>
        }
      />
    </div>
  );
}
