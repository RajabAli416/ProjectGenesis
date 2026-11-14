import { useState } from 'react';
import type { BenchmarkRecord } from '@/domain';
import { mutations } from '@/api';
import { useBenchmarks, useInferenceStatus, usePolling } from '@/api/hooks';
import { Panel, DataList, StatusLabel, Tag, Button, Table, EmptyState, Notice, type Column } from '@/components/ui';
import { fmtDateTime, fmtInt, fmtPct } from '@/lib/format';
import s from './SettingsPage.module.css';

/**
 * Live view of the inference provider the backend is using: reachability,
 * resident model, queue and latency; plus recorded benchmarks. Everything here
 * is reported by the backend — nothing is inferred client-side.
 */
export function InferencePanel({ className, id }: { className?: string; id?: string }) {
  const status = useInferenceStatus();
  const benchmarks = useBenchmarks();
  usePolling(status.reload, 5000);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const st = status.data ?? null;

  const bench = async () => {
    setRunning(true);
    setError(null);
    try {
      await mutations.runBenchmark({ requests: 5 });
      benchmarks.reload();
      status.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Benchmark failed');
    } finally {
      setRunning(false);
    }
  };

  const cols: Column<BenchmarkRecord>[] = [
    { key: 'when', header: 'When', mono: true, render: (b) => fmtDateTime(b.createdAt), sortValue: (b) => b.createdAt },
    { key: 'model', header: 'Model', mono: true, render: (b) => b.modelRef ?? b.model, fill: true },
    { key: 'ctx', header: 'ctx', num: true, render: (b) => fmtInt(b.numCtx) },
    { key: 'think', header: 'Think', render: (b) => (b.think ? 'on' : 'off') },
    { key: 'schema', header: 'Schema valid', num: true, render: (b) => fmtPct(b.schemaValidRate), sortValue: (b) => b.schemaValidRate },
    { key: 'p50', header: 'p50', num: true, render: (b) => `${fmtInt(b.latencyP50Ms)} ms`, sortValue: (b) => b.latencyP50Ms },
    { key: 'p95', header: 'p95', num: true, render: (b) => `${fmtInt(b.latencyP95Ms)} ms`, sortValue: (b) => b.latencyP95Ms },
    { key: 'tps', header: 'gen tok/s', num: true, render: (b) => (b.evalRateTps !== null ? b.evalRateTps.toFixed(1) : '—') },
  ];

  const reachable = !!st?.reachable;
  const ready = reachable && (st?.modelLoaded || (st?.completed ?? 0) > 0);

  return (
    <Panel
      id={id}
      className={className}
      title="Inference"
      subtitle="what the engine is actually talking to"
      actions={
        <Button size="sm" variant="outline" onClick={bench} disabled={!reachable || running} title={reachable ? 'Send 5 representative decision prompts and record validity and latency' : 'Provider unreachable'}>
          {running ? 'Benchmarking…' : 'Run benchmark'}
        </Button>
      }
    >
      {status.status === 'error' && <Notice tone="attn">Inference status unavailable: {status.error?.message}</Notice>}
      {st && !reachable && (
        <Notice tone="attn">
          The default provider is unreachable{st.lastError ? ` — ${st.lastError}` : ''}. Agents fall back to their reflex policy; no decision is attributed to a model until the provider answers.
        </Notice>
      )}
      {st && reachable && !ready && st.model && (
        <Notice tone="attn">
          Provider reachable but <span className="mono">{st.model}</span> is not resident. For Ollama run <span className="mono">ollama pull {st.model}</span>; the first decision loads it (Qwen3 needs Ollama ≥ 0.6.6; thinking control needs ≥ 0.9).
        </Notice>
      )}
      {st && (
        <DataList
          dense
          alignLeft
          rows={[
            { label: 'Provider', value: st.providerId ? <span>{st.providerId} <Tag mono>{st.adapter}</Tag></span> : '—', mono: false },
            { label: 'Reachable', value: <StatusLabel tone={reachable ? 'live' : 'crit'}>{reachable ? `yes${st.providerVersion ? ` · v${st.providerVersion}` : ''}` : 'no'}</StatusLabel>, mono: false },
            { label: 'Model', value: st.model ?? '—' },
            { label: 'Model ref', value: st.modelRef ? `${st.modelRef.id}${st.modelRef.quantization ? ` · ${st.modelRef.quantization}` : ''}${st.modelRef.parameterSize ? ` · ${st.modelRef.parameterSize}` : ''}` : 'not resolved yet' },
            { label: 'Resident', value: <StatusLabel tone={st.modelLoaded ? 'live' : 'neutral'}>{st.modelLoaded ? 'loaded' : 'not loaded'}</StatusLabel>, mono: false },
            { label: 'Queue', value: `${st.queueDepth} waiting · ${st.inFlight} in flight · ${st.concurrency} worker${st.concurrency === 1 ? '' : 's'}` },
            { label: 'Requests', value: `${fmtInt(st.completed)} ok · ${fmtInt(st.invalid)} invalid · ${fmtInt(st.failed)} failed` },
            { label: 'Latency', value: st.latencyP50Ms !== null ? `p50 ${fmtInt(st.latencyP50Ms)} ms · p95 ${fmtInt(st.latencyP95Ms ?? 0)} ms` : '—' },
            ...(st.lastError ? [{ label: 'Last error', value: st.lastError, mono: false }] : []),
          ]}
        />
      )}
      {error && <div className={s.dirty} style={{ marginTop: 'var(--sp-2)' }}>{error}</div>}
      <div style={{ marginTop: 'var(--sp-3)' }}>
        {benchmarks.data && benchmarks.data.length > 0 ? (
          <Table compact aria-label="Benchmarks" rows={benchmarks.data} rowKey={(b) => String(b.id)} columns={cols} initialSort={{ key: 'when', dir: 'desc' }} />
        ) : (
          <EmptyState title="No benchmarks recorded" body="Benchmarks measure JSON/schema validity and latency for the current model so the choice of model and quantization is documented with the results." />
        )}
      </div>
    </Panel>
  );
}
