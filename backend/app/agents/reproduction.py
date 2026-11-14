"""Reproduction and inheritance: traits blend with mutation, a share of the parents' beliefs is
inherited at reduced confidence (source 'inherited'), and lineage/relationships are recorded."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agents.agent import AgentState, Belief, Memory, Relationship

if TYPE_CHECKING:
    from app.simulation.state import UniverseState


def spawn_agent(state: UniverseState, x: float, y: float, traits: dict[str, float], generation: int, parent_ids: list[str], energy: float = 0.8) -> AgentState:
    assert state.ids is not None
    agent = AgentState(
        id=state.ids.agent(),
        name=state.next_name(),
        born_at_tick=state.tick,
        generation=generation,
        x=x,
        y=y,
        traits=traits,
        energy=energy,
        parent_ids=list(parent_ids),
    )
    agent.last_decision_tick = state.tick - state.config.reasoning.decision_interval  # eligible soon, not instantly
    state.agents[agent.id] = agent
    state.born += 1
    state.max_generation = max(state.max_generation, generation)
    return agent


def random_traits(state: UniverseState) -> dict[str, float]:
    rng = state.rng.agents  # type: ignore[union-attr]
    return {k: round(min(1.0, max(0.0, rng.gauss(0.5, 0.18))), 3) for k in ("curiosity", "endurance", "sociality", "risk")}


def reproduce(state: UniverseState, parent: AgentState, partner: AgentState | None) -> AgentState | None:
    rules = state.config.rules
    rng = state.rng.agents  # type: ignore[union-attr]
    assert state.ids is not None
    if parent.energy < rules.reproduction_threshold:
        return None
    if partner is not None and partner.energy < rules.reproduction_threshold * 0.8:
        partner = None
    parents = [parent] + ([partner] if partner else [])
    traits: dict[str, float] = {}
    for key in ("curiosity", "endurance", "sociality", "risk"):
        base = sum(p.traits.get(key, 0.5) for p in parents) / len(parents)
        if rng.random() < rules.mutation_rate * 10:  # per-trait mutation chance scaled from per-birth rate
            base += rng.gauss(0, 0.08)
        traits[key] = round(min(1.0, max(0.0, base)), 3)
    generation = max(p.generation for p in parents) + 1
    child = spawn_agent(state, parent.x + rng.uniform(-1, 1), parent.y + rng.uniform(-1, 1), traits, generation, [p.id for p in parents], energy=0.6)

    for p in parents:
        p.energy -= rules.reproduction_cost / len(parents)
        p.last_reproduction_tick = state.tick
        p.offspring_ids.append(child.id)
        p.relationships[child.id] = Relationship(child.id, "offspring", 0.7, state.tick)
        child.relationships[p.id] = Relationship(p.id, "parent", 0.6, state.tick)
        p.remember(Memory(state.ids.memory(), state.tick, "social", f"Offspring {child.name} ({child.id.upper()}) was born.", 0.8, data={"child": child.id}))
        # Inherit the most confident beliefs at reduced confidence.
        for b in sorted(p.beliefs.values(), key=lambda b: -b.confidence)[:3]:
            if b.topic not in child.beliefs:
                child.beliefs[b.topic] = Belief(state.ids.belief(), b.topic, b.statement, round(b.confidence * 0.6, 3), "inherited", state.tick)
        for topic, prog in p.tech_knowledge.items():
            child.tech_knowledge[topic] = max(child.tech_knowledge.get(topic, 0.0), prog * 0.5)
    if partner is not None:
        parent.adjust_affinity(partner.id, 0.1, "partner", state.tick).kind = "partner"
        partner.adjust_affinity(parent.id, 0.1, "partner", state.tick).kind = "partner"
    child.remember(Memory(state.ids.memory(), state.tick, "perception", "I came into being.", 0.5))
    state.emit("notice", "population", f"{child.name} ({child.id.upper()}) born to {' and '.join(p.name for p in parents)}; generation {generation}.", [{"kind": "agent", "id": child.id}] + [{"kind": "agent", "id": p.id} for p in parents])
    return child
