"""Create a universe offline, run it for N ticks in lockstep and print its state hash. With
--expect-hash the script exits non-zero when the hash differs, which makes it a reproduction check:
the same seed, configuration and engine version must yield the same hash on any machine.

The universe is persisted; the next backend start restores it (paused). Use --archive to keep the
database clean after a pure reproduction check.

Examples (from backend/, venv active, server stopped):

    python scripts/seed_demo.py --seed demo-1 --ticks 2000
    python scripts/seed_demo.py --seed demo-1 --ticks 2000 --expect-hash sha256:… --archive
    python scripts/seed_demo.py --seed demo-2 --population 12 --width 384 --height 256 --reasoning
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from _common import add_db_args, refuse_if_server_running, settings_from_args

from app.api import schemas as S
from app.observability.logging import configure_logging
from app.persistence.store import open_store
from app.simulation.host import SimulationHost


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_db_args(p)
    p.add_argument("--name", default="Demo", help="universe name")
    p.add_argument("--seed", default="demo", help="universe seed (any string)")
    p.add_argument("--ticks", type=int, default=2_000, help="ticks to run (default 2000)")
    p.add_argument("--population", type=int, help="founding population (default: operator settings)")
    p.add_argument("--width", type=int, help="world width in units")
    p.add_argument("--height", type=int, help="world height in units")
    p.add_argument("--reasoning", action="store_true", help="enable model reasoning (requires a reachable provider; the run is then not reproducible unless replayed)")
    p.add_argument("--expect-hash", help="fail unless the final state hash equals this value")
    p.add_argument("--archive", action="store_true", help="archive the universe afterwards")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    settings = settings_from_args(args)
    refuse_if_server_running(settings, args.force)
    configure_logging("ERROR" if args.quiet else "WARNING")

    store = open_store(settings.db_url)
    host = SimulationHost(settings, store)
    await host.start()
    try:
        config: dict[str, object] = {"reasoning.enabled": args.reasoning}
        if args.width:
            config["width"] = args.width
        if args.height:
            config["height"] = args.height
        req = S.CreateUniverseRequest(name=args.name, seed=args.seed, initial_population=args.population, mode="lockstep", start=False, config=config)
        state = await host.create_universe(req)
        t0 = time.perf_counter()
        remaining = args.ticks
        while remaining > 0:
            chunk = min(remaining, 10_000)
            res = await host.command(state.id, {"type": "step", "ticks": chunk})
            if not res.accepted:
                print(f"step rejected: {res.reason}", file=sys.stderr)
                return 2
            remaining -= chunk
            if state.status == "terminated":
                break
        elapsed = time.perf_counter() - t0
        digest = host.state_hash(state.id)
        await host.snapshot(state)
        alive = sum(1 for a in state.agents.values() if a.alive)
        if not args.quiet:
            print(f"universe   {state.id} ({state.code} {state.name})")
            print(f"seed       {state.config.seed}")
            print(f"engine     {state.engine_version} · mechanics v{state.mechanics_version} · config v{state.config.config_version}")
            print(f"ticks      {state.tick:,} in {elapsed:.1f}s ({state.tick / max(elapsed, 1e-6):,.0f} t/s)")
            print(f"population {alive} alive · {state.born} born · {state.died} died · stage {state.civilization.stage}")
            print(f"reasoning  {'model' if args.reasoning else 'reflex only'}")
        print(f"state_hash {digest}")
        ok = True
        if args.expect_hash:
            ok = digest == args.expect_hash
            print("REPRODUCED" if ok else f"MISMATCH (expected {args.expect_hash})")
        if args.archive:
            await host.archive(state.id)
        return 0 if ok else 1
    finally:
        await host.stop()
        store.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
