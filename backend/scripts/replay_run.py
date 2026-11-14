"""Reproduce an existing universe from its recorded inference responses and assert the state hash.

A fresh universe is created with the source universe's exact configuration (seed, rules, reasoning
settings) in lockstep mode, with the provider replaced by the `replay` adapter, which serves every
model response from the inference_requests table by prompt hash. Mechanics are deterministic per
seed, so if the recorded responses are complete the replica reaches the same identity-neutral state
hash as the source at the same tick. The replica is archived afterwards unless --keep is given.

Examples (from backend/, venv active, server stopped):

    python scripts/replay_run.py u-0002
    python scripts/replay_run.py u-0002 --ticks 1200 --keep
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from _common import add_db_args, refuse_if_server_running, settings_from_args

from app.api import schemas as S
from app.core.errors import NotFound
from app.intelligence.providers.scripted import ReplayProvider
from app.observability.logging import configure_logging
from app.persistence.store import open_store
from app.simulation.engine import state_hash
from app.simulation.host import SimulationHost
from app.simulation.state import UniverseState


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_db_args(p)
    p.add_argument("universe", help="source universe id, e.g. u-0002")
    p.add_argument("--ticks", type=int, help="replay up to this tick (default: the source's latest persisted snapshot tick)")
    p.add_argument("--keep", action="store_true", help="keep the replica universe instead of archiving it")
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    settings = settings_from_args(args)
    refuse_if_server_running(settings, args.force)
    configure_logging("WARNING")

    store = open_store(settings.db_url)
    found = store.latest_snapshot(args.universe)
    if found is None:
        print(f"no persisted snapshot for {args.universe}", file=sys.stderr)
        store.close()
        return 2
    source_data, snap = found
    source = UniverseState.from_dict(source_data)
    target_tick = args.ticks or source.tick
    if target_tick > source.tick:
        print(f"source snapshot is at tick {source.tick:,}; cannot compare beyond it (requested {target_tick:,})", file=sys.stderr)
        store.close()
        return 2

    host = SimulationHost(settings, store)
    host.scripted_override = ReplayProvider(host._replay_lookup)  # noqa: SLF001
    await host.start()
    try:
        # The live source (if restored) may be ahead of the snapshot; compare against the snapshot
        # when ticks match, otherwise against the in-memory state at the requested tick.
        try:
            live = host.get(args.universe)
            source_hash = state_hash(live) if live.tick == target_tick else None
        except NotFound:
            source_hash = None
        if source_hash is None:
            if source.tick != target_tick:
                print(f"source has no persisted state at tick {target_tick:,} (snapshot is at {source.tick:,}); pass --ticks {source.tick}", file=sys.stderr)
                return 2
            source_hash = state_hash(source)

        cfg = source.config.model_copy(update={"mode": "lockstep"})
        req = S.CreateUniverseRequest(name=f"Replay of {source.code}", seed=cfg.seed, start=False, mode="lockstep")
        replica = await host.create_universe(req, created_by=("operator", None, "replay_run"), config=cfg)
        res = await host.command(replica.id, {"type": "step", "ticks": target_tick})
        if not res.accepted:
            print(f"step rejected: {res.reason}", file=sys.stderr)
            return 2
        replica_hash = host.state_hash(replica.id)
        reqs = store.list_inference_requests(replica.id, None, 100_000)
        replayed = sum(1 for r in reqs if r.status == "ok")
        failed = sum(1 for r in reqs if r.status != "ok")
        print(f"source     {source.id} ({source.code}) · tick {target_tick:,} · {source_hash}")
        print(f"replica    {replica.id} ({replica.code}) · tick {replica.tick:,} · {replica_hash}")
        print(f"inference  {replayed} responses replayed · {failed} missing/failed")
        ok = replica_hash == source_hash
        print("REPRODUCED" if ok else "MISMATCH — recorded responses are incomplete, or engine/prompt versions differ from the source run")
        if not args.keep:
            await host.archive(replica.id)
        return 0 if ok else 1
    finally:
        await host.stop()
        store.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
