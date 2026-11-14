from __future__ import annotations

from app.api import schemas as S
from app.intelligence.providers.scripted import ScriptedProvider, available_from_prompt
from app.recursion.spawn import ALLOWED_RULE_OVERRIDES, child_config
from app.simulation.actions import available_actions, validate_action
from app.simulation.engine import run_ticks, state_hash
from app.simulation.host import SimulationHost
from app.simulation.snapshot import world_snapshot
from app.simulation.state import TechState, UniverseState
from tests.conftest import make_state, small_config


def _unlock_subworld(state: UniverseState) -> None:
    state.civilization.technologies["subworld"] = TechState("subworld", "established", 1.0, state.tick, None)
    for a in state.agents.values():
        a.add_food(50, 1000)
        a.energy = 1.0


def test_child_config_derivation_and_allowed_overrides() -> None:
    parent = small_config("p")
    requested = {"hazard_amplitude": 0.9, "max_recursion_depth": 99}
    allowed = {k: v for k, v in requested.items() if k in ALLOWED_RULE_OVERRIDES}  # what request_subworld keeps
    cfg = child_config(parent, "child-seed", allowed)
    assert cfg.seed == "child-seed"
    assert cfg.width <= parent.width and cfg.height <= parent.height
    assert cfg.rules.hazard_amplitude == 0.9
    assert cfg.rules.max_recursion_depth == parent.rules.max_recursion_depth  # not in the allow-list
    assert "hazard_amplitude" in ALLOWED_RULE_OVERRIDES and "max_recursion_depth" not in ALLOWED_RULE_OVERRIDES


def test_agents_cannot_set_protected_rules() -> None:
    st = make_state("prot")
    _unlock_subworld(st)
    a = st.agents[sorted(st.agents)[0]]
    assert "instantiate_subworld" in [s.name for s in available_actions(st, a)]
    err = validate_action(st, a, {"type": "instantiate_subworld", "params": {"name": "x", "rules": {"max_recursion_depth": 50}}})
    assert err and "max_recursion_depth" in err
    assert validate_action(st, a, {"type": "instantiate_subworld", "params": {"name": "x", "rules": {"hazard_amplitude": 0.1}}}) is None


async def test_instantiate_subworld_creates_isolated_child(host: SimulationHost) -> None:
    def script(req):
        actions = available_from_prompt(req)
        if "instantiate_subworld" in actions:
            return {"action": {"type": "instantiate_subworld", "params": {"name": "Inner", "rules": {"hazard_amplitude": 0.1}}}, "rationale": "make a world", "beliefUpdates": []}
        return {"action": {"type": "rest" if "rest" in actions else actions[0], "params": {"ticks": 5}}, "rationale": "wait", "beliefUpdates": []}

    host.scripted_override = ScriptedProvider(script=script)
    await host.refresh_provider()
    parent = await host.create_universe(S.CreateUniverseRequest(name="Parent", seed="par", start=False, mode="lockstep", config={"width": 96, "height": 64, "reasoning.enabled": True, "initial_population": 3}))
    _unlock_subworld(parent)
    await host.command(parent.id, {"type": "step", "ticks": 300})
    assert parent.child_ids, "no sub-world was created"
    child = host.get(parent.child_ids[0])
    assert child.parent_id == parent.id and child.depth == 1
    assert child.created_by_kind == "agent"
    assert child.compute_share < 1.0 and parent.compute_share < 1.0
    assert child.config.rules.hazard_amplitude == 0.1
    assert child.config.width <= parent.config.width
    assert child.seed != parent.seed
    # Portal appears in the parent's snapshot.
    snap = world_snapshot(parent)
    assert any(e.kind == "portal" for e in snap.entities)
    # Isolation: stepping the child does not touch the parent, and no agent object is shared.
    h_parent = state_hash(parent)
    await host.command(child.id, {"type": "step", "ticks": 100})
    assert state_hash(parent) == h_parent
    assert not (set(child.agents) & set(parent.agents))
    assert child.rng is not parent.rng and child.grid["cls"] is not parent.grid["cls"]


def test_recursion_depth_limit() -> None:
    st = make_state("depth")
    _unlock_subworld(st)
    st.depth = st.config.rules.max_recursion_depth
    a = st.agents[sorted(st.agents)[0]]
    assert "instantiate_subworld" not in [s.name for s in available_actions(st, a)]
    run_ticks(st, 10)
