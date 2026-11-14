from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.api import schemas as S
from app.config import Settings
from app.intelligence.providers.scripted import ScriptedProvider
from app.main import create_app
from app.persistence.store import Store, make_memory_store
from app.simulation.config import UniverseConfig, build_config
from app.simulation.engine import new_universe
from app.simulation.host import SimulationHost

REPO_ROOT = Path(__file__).resolve().parents[2]


def small_config(seed: str = "test-seed", **overrides) -> UniverseConfig:
    base = {"width": 96, "height": 64, "cell_size": 8, "seed": seed, "initial_population": 5, "mode": "lockstep"}
    return build_config(base, overrides)


def make_state(seed: str = "test-seed", number: int = 1, **overrides):
    cfg = small_config(seed, **overrides)
    return new_universe(id=f"u-{number:04d}", number=number, code=f"U-{number - 1:02d}", name="T", config=cfg, created_at="2026-01-01T00:00:00Z")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, initial_population=4, world_width=96, world_height=64, event_flush_ticks=20, snapshot_interval_ticks=200)


@pytest.fixture
def store() -> Iterator[Store]:
    s = make_memory_store()
    yield s
    s.close()


@pytest_asyncio.fixture
async def host(settings: Settings, store: Store) -> AsyncIterator[SimulationHost]:
    h = SimulationHost(settings, store)
    h.scripted_override = ScriptedProvider()
    await h.start()
    yield h
    await h.stop()


@pytest.fixture
def client(settings: Settings, store: Store) -> Iterator[TestClient]:
    h = SimulationHost(settings, store)
    h.scripted_override = ScriptedProvider()
    app = create_app(settings, store, h)
    with TestClient(app) as c:
        c.host = h  # type: ignore[attr-defined]
        yield c


async def create_and_step(host: SimulationHost, ticks: int, seed: str = "abc", **config) -> str:
    st = await host.create_universe(S.CreateUniverseRequest(name="T", seed=seed, start=False, mode="lockstep", config={"width": 96, "height": 64, **config}))
    r = await host.command(st.id, {"type": "step", "ticks": ticks})
    assert r.accepted, r.reason
    return st.id


async def wait_until(pred, timeout: float = 10.0, interval: float = 0.05) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if pred():
            return
        await asyncio.sleep(interval)
    raise AssertionError("condition not met in time")
