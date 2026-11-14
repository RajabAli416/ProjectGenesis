"""One simulation tick. The order of operations is fixed and agents are visited in id order so that
the same seed and the same sequence of applied decisions always yields the same state."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from app.agents import perception, reflex
from app.agents.agent import AgentState, Memory
from app.simulation import terrain
from app.simulation.actions import REGISTRY

if TYPE_CHECKING:
    from app.simulation.state import UniverseState

PERCEPTION_EVERY = 10


def _stable_offset(aid: str) -> int:
    """Process-independent stagger derived from the agent's sequence number only, so it does not
    depend on which universe number the agent lives in (keeps same-seed universes identical)."""
    try:
        return int(aid.rsplit("-", 1)[1]) % PERCEPTION_EVERY
    except (IndexError, ValueError):
        return sum(ord(c) for c in aid) % PERCEPTION_EVERY


def update_environment(state: UniverseState) -> None:
    rules = state.config.rules
    g = state.grid
    phase = math.sin(math.tau * state.tick / max(1, rules.hazard_period))
    g["hazard"] = np.clip(g["hazard_base"] * (1.0 + rules.hazard_amplitude * phase), 0.0, 1.0).astype(np.float32)
    regen = rules.resource_regen * (1.3 if _established(state, "irrigation") else 1.0)
    fertile = g["cls"] == terrain.FERTILE
    g["resource"] = np.where(fertile, np.minimum(rules.resource_cap * g["fertility"] * 1.4, g["resource"] + regen * g["fertility"]), g["resource"]).astype(np.float32)


def _established(state: UniverseState, tech: str) -> bool:
    t = state.civilization.technologies.get(tech)
    return bool(t and t.state == "established")


def metabolism(state: UniverseState, agent: AgentState) -> None:
    rules = state.config.rules
    cx, cy = state.cell_of(agent.x, agent.y)
    hazard = float(state.grid["hazard"][cy, cx])
    if perception.sheltered_at(state, agent.x, agent.y):
        hazard *= rules.shelter_hazard_factor
    if _established(state, "fire"):
        hazard *= 0.8
    decay = rules.energy_decay * (1.0 + hazard * rules.hazard_decay_multiplier)
    decay *= 1.0 - 0.3 * agent.traits.get("endurance", 0.5)
    if agent.intent is not None and agent.intent.state.get("resting"):
        decay *= rules.rest_decay_factor
    if agent.status == "dormant":
        decay *= rules.rest_decay_factor
    agent.energy -= decay
    agent.age += 1

    if agent.status == "active" and agent.energy < rules.dormant_threshold:
        agent.status = "dormant"
        agent.remember(Memory(state.ids.memory(), state.tick, "reflection", f"Energy below action threshold ({agent.energy:.2f}); entered dormancy.", 0.6))  # type: ignore[union-attr]
        state.emit("info", "agent", f"{agent.name} entered dormancy (energy {agent.energy:.2f}).", [{"kind": "agent", "id": agent.id}])
    elif agent.status == "dormant" and agent.energy > rules.wake_threshold:
        agent.status = "active"

    if agent.energy <= 0.0:
        _die(state, agent, "starvation")
    elif rules.max_age > 0 and agent.age > rules.max_age:
        over = (agent.age - rules.max_age) / rules.max_age
        if state.rng.agents.random() < 0.002 * (1 + over * 10):  # type: ignore[union-attr]
            _die(state, agent, "old age")


def _die(state: UniverseState, agent: AgentState, cause: str) -> None:
    agent.status = "deceased"
    agent.died_at_tick = state.tick
    agent.energy = 0.0
    agent.intent = None
    state.died += 1
    state.emit("info", "agent", f"{agent.name} ({agent.id.upper()}) deceased at age {agent.age:,} ({cause}).", [{"kind": "agent", "id": agent.id}])
    for other in state.agents.values():
        if other.alive and other.id != agent.id and agent.id in other.relationships:
            rel = other.relationships[agent.id]
            sal = 0.7 if rel.kind in ("parent", "offspring", "partner") else 0.4
            other.remember(Memory(state.ids.memory(), state.tick, "social", f"{agent.name} ({rel.kind}) has died.", sal, data={"agentId": agent.id}))  # type: ignore[union-attr]


def run_intent(state: UniverseState, agent: AgentState) -> None:
    intent = agent.intent
    if intent is None:
        return
    spec = REGISTRY.get(intent.type)
    if spec is None:
        agent.intent = None
        return
    done = spec.step(state, agent, intent)
    expired = state.tick - intent.started_tick >= intent.ttl
    if done or expired:
        if intent.policy == "model":
            agent.remember(
                Memory(
                    state.ids.memory(),  # type: ignore[union-attr]
                    state.tick,
                    "action",
                    f"{'Completed' if done else 'Gave up on'} {intent.type}" + (f" ({', '.join(f'{k}={v}' for k, v in list(intent.params.items())[:2] if k != 'text')})" if intent.params else "") + ".",
                    0.3 if done else 0.4,
                )
            )
        if intent.decision_id is not None:
            state.outbox_decisions.append({"_update": intent.decision_id, "outcome_json": {"done": done, "expired": expired, "tick": state.tick, "progress": intent.progress, **{k: v for k, v in intent.state.items() if isinstance(v, (int, float, str, bool))}}})
        agent.intent = None


def decide_reflex(state: UniverseState, agent: AgentState, obs: perception.Observation) -> None:
    intent = reflex.choose(state, agent, obs)
    agent.intent = intent
    agent.decisions_total += 1
    agent.policy = "reflex"


def structures_decay(state: UniverseState) -> None:
    rules = state.config.rules
    dead = []
    for s in state.structures.values():
        s.condition -= rules.structure_decay
        if s.condition <= 0:
            dead.append(s.id)
    for sid in dead:
        s = state.structures.pop(sid)
        state.grid["built"][s.cy, s.cx] = 0
        state.emit("info", "civilization", f"A {s.kind} at ({s.x:.0f}, {s.y:.0f}) collapsed.")


def step(state: UniverseState) -> None:
    """Advance the universe by one tick."""
    state.tick += 1
    update_environment(state)

    for aid in sorted(state.agents):
        agent = state.agents[aid]
        if not agent.alive:
            continue
        metabolism(state, agent)
        if not agent.alive:
            continue
        if agent.intent is None and not agent.pending_request:
            obs = perception.observe(state, agent)
            decide_reflex(state, agent, obs)
        if agent.intent is not None:
            run_intent(state, agent)
        if (state.tick + _stable_offset(aid)) % PERCEPTION_EVERY == 0:
            obs = perception.observe(state, agent)
            perception.perceive_and_remember(state, agent, obs)

    structures_decay(state)

    rules = state.config.rules
    if rules.civilization_interval > 0 and state.tick % rules.civilization_interval == 0:
        from app.civilization.engine import update as civ_update

        civ_update(state)
    if rules.research_interval > 0 and state.tick % rules.research_interval == 0:
        from app.research.engine import update as research_update

        research_update(state)

    if state.tick > 1 and not state.alive_agents() and state.status == "running":
        state.status = "terminated"
        state.terminated_reason = "population reached zero"
        state.emit("critical", "population", "Population reached zero. Universe terminated.", [{"kind": "universe", "id": state.id}])
