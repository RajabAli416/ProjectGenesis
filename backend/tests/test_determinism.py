from __future__ import annotations

from app.simulation.engine import run_ticks, state_hash
from app.simulation.state import UniverseState
from tests.conftest import make_state


def test_same_seed_same_hash_different_universe_numbers() -> None:
    a = make_state("seed-1", number=1)
    b = make_state("seed-1", number=7)
    run_ticks(a, 800)
    run_ticks(b, 800)
    assert a.tick == b.tick == 800
    assert state_hash(a) == state_hash(b)


def test_different_seed_different_hash() -> None:
    a = make_state("seed-1")
    b = make_state("seed-2")
    run_ticks(a, 200)
    run_ticks(b, 200)
    assert state_hash(a) != state_hash(b)


def test_snapshot_roundtrip_continues_identically() -> None:
    a = make_state("rt")
    run_ticks(a, 300)
    restored = UniverseState.from_dict(a.to_dict())
    assert state_hash(restored) == state_hash(a)
    run_ticks(a, 300)
    run_ticks(restored, 300)
    assert state_hash(restored) == state_hash(a)
    assert restored.tick == 600


def test_population_dynamics_run() -> None:
    st = make_state("pop", initial_population=8)
    run_ticks(st, 1500)
    assert st.born >= 8
    assert len(st.alive_agents()) >= 1
    assert st.status in ("paused", "running")
