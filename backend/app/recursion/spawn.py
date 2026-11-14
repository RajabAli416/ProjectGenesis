"""Civilization-created child universes. An agent's `instantiate_subworld` action pays the cost and
queues a request; the SimulationHost (which owns all universes) fulfils it by constructing an
independent UniverseState with a deep-copied, derived configuration and its own RNG streams.
Nothing mutable is ever shared between parent and child."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.agents.agent import AgentState, Memory
from app.core.rng import derive_seed
from app.simulation.config import UniverseConfig, build_config
from app.simulation.state import Portal

if TYPE_CHECKING:
    from app.simulation.state import UniverseState

ALLOWED_RULE_OVERRIDES = {"energy_decay", "edge_mode", "base_hazard", "hazard_amplitude", "resource_regen", "base_fertility", "hazard_period"}


def request_subworld(state: UniverseState, agent: AgentState, params: dict[str, Any]) -> None:
    rules = state.config.rules
    agent.take_food(rules.subworld_cost_food)
    agent.energy = max(0.05, agent.energy - rules.subworld_cost_energy)
    overrides = {k: v for k, v in (params.get("rules") or {}).items() if k in ALLOWED_RULE_OVERRIDES}
    req = {
        "creator_id": agent.id,
        "creator_label": f"{agent.name} ({agent.id.upper()})",
        "name": str(params.get("name") or f"{agent.name}'s world")[:40],
        "rule_overrides": overrides,
        "x": agent.x,
        "y": agent.y,
        "tick": state.tick,
    }
    state.pending_subworlds.append(req)
    assert state.ids is not None
    agent.remember(Memory(state.ids.memory(), state.tick, "action", f"Instantiated a sub-world ({req['name']}).", 0.97, data={"subworld": True}))
    state.emit("notice", "universe", f"Sub-world instantiation requested by {agent.name} ({agent.id.upper()}).", [{"kind": "agent", "id": agent.id}])


def child_config(parent: UniverseConfig, child_seed: str, overrides: dict[str, Any]) -> UniverseConfig:
    r = parent.rules
    base = parent.model_dump(mode="json")
    width = max(64, int(parent.width * r.subworld_size_factor) // parent.cell_size * parent.cell_size)
    height = max(40, int(parent.height * r.subworld_size_factor) // parent.cell_size * parent.cell_size)
    base.update({"width": width, "height": height, "seed": child_seed, "initial_population": r.subworld_population})
    cfg = build_config(base, {f"rules.{k}": v for k, v in overrides.items()})
    return cfg


def attach_child(parent: UniverseState, child_id: str, req: dict[str, Any], child_share: float) -> None:
    portal = Portal(child_id=child_id, x=float(req["x"]), y=float(req["y"]), created_tick=parent.tick, creator_id=req.get("creator_id"), rule_overrides=dict(req.get("rule_overrides") or {}))
    parent.portals.append(portal)
    parent.child_ids.append(child_id)
    parent.compute_share = max(0.05, parent.compute_share - child_share)
    parent.emit("notice", "universe", f"Sub-world instantiated by {req.get('creator_label', 'unknown')}; designated {child_id.upper()}.", [{"kind": "universe", "id": child_id}] + ([{"kind": "agent", "id": req["creator_id"]}] if req.get("creator_id") else []))


def child_seed_for(parent_seed: str, index: int) -> str:
    return derive_seed(parent_seed, f"child:{index}")
