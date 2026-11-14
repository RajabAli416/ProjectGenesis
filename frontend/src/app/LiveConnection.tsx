import { useEffect } from 'react';
import { env, LiveClient, resolveWsUrl } from '@/api';
import { useConnectionStore } from '@/store/connectionStore';

/**
 * Opens the live channel to the backend when the http data source is active.
 * With the static source nothing is opened and the state stays 'disabled'.
 */
export function LiveConnection() {
  const setState = useConnectionStore((s) => s.setState);
  const setClient = useConnectionStore((s) => s.setClient);
  const ingest = useConnectionStore((s) => s.ingest);

  useEffect(() => {
    if (env.dataSource !== 'http') return;
    const url = resolveWsUrl();
    if (!url) return;
    const client = new LiveClient({ url, onMessage: ingest, onState: setState });
    setClient(client);
    client.connect();
    return () => {
      client.close();
      setClient(null);
    };
  }, [setState, setClient, ingest]);

  return null;
}
