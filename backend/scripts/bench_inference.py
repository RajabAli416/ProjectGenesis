"""Benchmark the configured inference provider with the real decision schema and representative
prompts. Results are persisted (benchmarks table, visible in Settings → Inference) unless
--no-store is given.

Examples (from backend/, venv active, Ollama running with the model pulled):

    python scripts/bench_inference.py                       # 20 requests, configured model/ctx
    python scripts/bench_inference.py --num-ctx 4096 8192 --think both --requests 20
    python scripts/bench_inference.py --model qwen3:1.7b --requests 10 --json

OLLAMA_NUM_PARALLEL is a server-side Ollama setting; to cover that axis of the grid, restart
Ollama with the variable set and run the script again (the notes column records the server version).
Peak VRAM must be read from `nvidia-smi` alongside the run; it is not available from the API.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from _common import add_db_args, refuse_if_server_running, settings_from_args

from app.api import schemas as S
from app.core.errors import InvalidCommand, ProviderError
from app.intelligence.benchmark import run_benchmark
from app.observability.logging import configure_logging
from app.persistence.store import open_store
from app.simulation.host import SimulationHost


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_db_args(p)
    p.add_argument("--provider", help="provider id from operator settings (default: the default reasoning provider)")
    p.add_argument("--model", help="model name to benchmark (default: the provider's configured model)")
    p.add_argument("--num-ctx", type=int, nargs="*", default=None, help="one or more context sizes (default: configured num_ctx)")
    p.add_argument("--think", choices=["on", "off", "both"], default="off", help="thinking mode cells (default: off)")
    p.add_argument("--requests", type=int, default=20, help="requests per cell (1..50, default 20)")
    p.add_argument("--no-store", action="store_true", help="do not persist results to the database")
    p.add_argument("--json", action="store_true", help="print machine-readable JSON instead of a table")
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    settings = settings_from_args(args)
    refuse_if_server_running(settings, args.force)
    configure_logging("WARNING")

    store = open_store(settings.db_url)
    host = SimulationHost(settings, store)
    records: list[S.BenchmarkRecord] = []
    try:
        await host.refresh_provider()
        ctxs = args.num_ctx or [host.operator.reasoning.num_ctx]
        thinks = [True, False] if args.think == "both" else [args.think == "on"]
        for ctx in ctxs:
            for think in thinks:
                req = S.BenchmarkRequest(provider_id=args.provider, model=args.model, num_ctx=ctx, think=think, requests=args.requests)
                print(f"→ {args.model or 'configured model'} · num_ctx {ctx} · think {'on' if think else 'off'} · {args.requests} requests", file=sys.stderr, flush=True)
                if args.no_store:
                    insert = store.insert_benchmark
                    store.insert_benchmark = lambda row: 0  # type: ignore[method-assign]
                    try:
                        rec = await run_benchmark(host, req)
                    finally:
                        store.insert_benchmark = insert  # type: ignore[method-assign]
                else:
                    rec = await run_benchmark(host, req)
                records.append(rec)
    except (ProviderError, InvalidCommand, TimeoutError) as e:
        print(f"benchmark aborted: {e}", file=sys.stderr)
        if "not found" in str(e):
            print("The model is not present on the provider. For Ollama: `ollama pull <model>` (Qwen3 requires Ollama >= 0.6.6).", file=sys.stderr)
        return 2
    finally:
        await host.registry.close()
        store.close()

    if args.json:
        print(json.dumps([r.model_dump(by_alias=True) for r in records], indent=2))
        return 0

    header = f"{'model':<22}{'ctx':>6}{'think':>7}{'n':>4}{'json%':>7}{'schema%':>9}{'p50 ms':>9}{'p95 ms':>9}{'prompt tok':>12}{'out tok':>9}{'gen tok/s':>11}{'load ms':>9}"
    print(header)
    print("-" * len(header))
    for r in records:
        print(
            f"{r.model:<22}{r.num_ctx:>6}{('on' if r.think else 'off'):>7}{r.requests:>4}{r.json_valid_rate * 100:>7.0f}{r.schema_valid_rate * 100:>9.0f}{r.latency_p50_ms:>9.0f}{r.latency_p95_ms:>9.0f}"
            f"{r.prompt_tokens_mean:>12.0f}{r.completion_tokens_mean:>9.0f}{(r.eval_rate_tps if r.eval_rate_tps is not None else float('nan')):>11.1f}{(r.load_duration_ms if r.load_duration_ms is not None else float('nan')):>9.0f}"
        )
    if records:
        print(f"\n{records[0].notes}")
        print("Decision rule: pick the largest model whose p95 × population keeps a decision round under your target; recorded rows are listed in Settings → Inference.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
