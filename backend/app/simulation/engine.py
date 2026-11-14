"""Universe construction, population and deterministic stepping helpers."""

from __future__ import annotations

from app.agents.reproduction import random_traits, spawn_agent
from app.core.hashing import canonical_json, neutralise_ids, sha256_hex
from app.core.timeutil import now_iso
from app.simulation import terrain
from app.simulation.config import UniverseConfig
from app.simulation.state import UniverseState
from app.simulation.tick import step as tick_step
from app.version import ENGINE_VERSION, MECHANICS_VERSION


def new_universe(
    *,
    id: str,
    number: int,
    code: str,
    name: str,
    config: UniverseConfig,
    parent_id: str | None = None,
    depth: int = 0,
    created_by: tuple[str, str | None, str] = ("operator", None, "Operator"),
    created_at_tick: int = 0,
    compute_share: float = 1.0,
    created_at: str | None = None,
) -> UniverseState:
    state = UniverseState.create(
        id=id,
        number=number,
        code=code,
        name=name,
        config=config,
        created_at=created_at or now_iso(),
        engine_version=ENGINE_VERSION,
        mechanics_version=MECHANICS_VERSION,
        parent_id=parent_id,
        depth=depth,
        created_by=created_by,
        created_at_tick=created_at_tick,
        compute_share=compute_share,
    )
    populate(state, config.initial_population)
    state.status = "paused"
    state.emit("notice", "universe", f"Universe {code} '{name}' created with {config.initial_population} founding agents (seed {config.seed}).", [{"kind": "universe", "id": id}])
    return state


def populate(state: UniverseState, count: int) -> None:
    """Place founding agents on passable, preferably fertile cells near the world centre."""
    rng = state.rng.agents  # type: ignore[union-attr]
    cls = state.grid["cls"]
    fertile = [(x, y) for y in range(state.rows) for x in range(state.cols) if cls[y, x] == terrain.FERTILE]
    passable = fertile or [(x, y) for y in range(state.rows) for x in range(state.cols) if state.passable(x, y)]
    if not passable:
        passable = [(state.cols // 2, state.rows // 2)]
    cx0, cy0 = state.cols / 2, state.rows / 2
    passable.sort(key=lambda c: (c[0] - cx0) ** 2 + (c[1] - cy0) ** 2)
    pool = passable[: max(8, len(passable) // 4)]
    for _ in range(count):
        cx, cy = pool[rng.randrange(len(pool))]
        wx, wy = state.cell_center(cx, cy)
        spawn_agent(state, wx + rng.uniform(-2, 2), wy + rng.uniform(-2, 2), random_traits(state), generation=1, parent_ids=[], energy=0.8)
    state.born = count  # founders count as born for population stats


def run_ticks(state: UniverseState, n: int) -> None:
    for _ in range(n):
        tick_step(state)
        if state.status == "terminated":
            break


def state_hash(state: UniverseState) -> str:
    """Hash of the mechanics state, independent of the universe's identity (id, number, code, name,
    lineage) so that two universes created from the same seed and config compare equal."""
    payload = state.state_hash_payload()
    for k in ("id", "number", "code", "name", "parent_id", "depth", "created_by_kind", "created_by_id", "created_by_label", "created_at_tick", "child_ids", "portals"):
        payload.pop(k, None)
    # Operator/system events (pause, restore, ...) are not mechanics; neither are unflushed outboxes.
    for k in list(payload):
        if k.startswith("outbox_") or k == "event_counter":
            payload.pop(k)
    if isinstance(payload.get("ids"), dict):
        payload["ids"] = {k: v for k, v in payload["ids"].items() if k != "universeN"}
    # Which model produced a decision is provenance metadata, not mechanics state; memory_counter is
    # persistence bookkeeping (how many memories have been written) and depends on snapshot timing.
    for a in payload.get("agents", {}).values():
        a.pop("model_ref", None)
        a.pop("memory_counter", None)
    return sha256_hex(neutralise_ids(canonical_json(payload)))
