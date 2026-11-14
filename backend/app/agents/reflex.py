"""Deterministic fallback policy. Used when an agent has no model-provided intent, when the model
is unavailable, or when a model response fails validation. Every intent it produces is labelled
``policy='reflex'`` so analyses can separate reflex behaviour from model-driven behaviour."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agents.agent import AgentState, Intent
from app.agents.perception import Observation

if TYPE_CHECKING:
    from app.simulation.state import UniverseState


def choose(state: UniverseState, agent: AgentState, obs: Observation) -> Intent:
    rules = state.config.rules
    rng = state.rng.agents  # type: ignore[union-attr]
    t = state.tick

    hungry = agent.energy < 0.55
    if hungry and agent.food() > 0.05:
        return Intent("eat", {}, t, "reflex", ttl=40)

    if agent.status == "dormant":
        if obs.resource_here > 0.05:
            return Intent("gather", {}, t, "reflex", ttl=60)
        return Intent("rest", {"ticks": 40}, t, "reflex", ttl=40)

    if obs.resource_here > 0.05 and (hungry or agent.food() < rules.inventory_cap * 0.5):
        return Intent("gather", {}, t, "reflex", ttl=80)

    if hungry or agent.food() < rules.inventory_cap * 0.3:
        target = None
        if obs.visible_resources:
            target = obs.visible_resources[0]
            return Intent("move_to", {"x": target.x, "y": target.y, "reason": "resource"}, t, "reflex", ttl=120)
        if agent.known_resources:
            k = agent.known_resources[-1]
            return Intent("move_to", {"x": k[0], "y": k[1], "reason": "remembered resource"}, t, "reflex", ttl=160)
        return Intent("explore", {}, t, "reflex", ttl=60)

    # Comfortable: occasionally reproduce, socialise or wander; otherwise rest.
    if (
        agent.energy > rules.reproduction_threshold
        and agent.age >= rules.maturity_age
        and t - agent.last_reproduction_tick >= rules.reproduction_cooldown
        and len(state.alive_agents()) < rules.max_population
        and obs.nearby_agents
        and rng.random() < rules.reflex_reproduction_probability
    ):
        partner = next((n.agent for n in obs.nearby_agents if n.agent.age >= rules.maturity_age and n.agent.energy > rules.reproduction_threshold), None)
        if partner is not None:
            return Intent("reproduce", {"with": partner.id}, t, "reflex", ttl=60)

    if rng.random() < agent.traits.get("curiosity", 0.5) * 0.3:
        return Intent("explore", {}, t, "reflex", ttl=60)
    return Intent("rest", {"ticks": 30}, t, "reflex", ttl=30)
