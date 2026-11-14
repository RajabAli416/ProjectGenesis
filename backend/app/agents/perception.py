"""What an agent can perceive. Observations are produced by mechanics only; they are the one source
of `observation`-grade memories and are what the model is shown when asked for a decision."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from app.agents.agent import AgentState, Memory
from app.simulation import terrain

if TYPE_CHECKING:
    from app.simulation.state import Structure, UniverseState


@dataclass
class NearbyAgent:
    agent: AgentState
    distance: float


@dataclass
class VisibleResource:
    cx: int
    cy: int
    x: float
    y: float
    level: float
    distance: float


@dataclass
class Observation:
    tick: int
    x: float
    y: float
    cx: int
    cy: int
    terrain: str
    resource_here: float
    hazard_here: float
    sheltered: bool
    energy: float
    food: float
    status: str
    nearby_agents: list[NearbyAgent] = field(default_factory=list)
    nearby_structures: list[Structure] = field(default_factory=list)
    visible_resources: list[VisibleResource] = field(default_factory=list)
    near_edge: list[str] = field(default_factory=list)
    portals_nearby: int = 0
    season_phase: float = 0.0


def distance(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def sheltered_at(state: UniverseState, x: float, y: float) -> bool:
    r = state.config.rules.structure_shelter_radius
    for s in state.structures.values():
        if s.kind == "shelter" and s.condition > 0.1 and distance(x, y, s.x, s.y) <= r:
            return True
    return False


def observe(state: UniverseState, agent: AgentState) -> Observation:
    rules = state.config.rules
    cs = state.config.cell_size
    cx, cy = state.cell_of(agent.x, agent.y)
    grid = state.grid
    radius = rules.perception_radius
    obs = Observation(
        tick=state.tick,
        x=agent.x,
        y=agent.y,
        cx=cx,
        cy=cy,
        terrain=terrain.CLASS_NAMES[int(grid["cls"][cy, cx])] if int(grid["built"][cy, cx]) == 0 else "built",
        resource_here=float(grid["resource"][cy, cx]),
        hazard_here=float(grid["hazard"][cy, cx]),
        sheltered=sheltered_at(state, agent.x, agent.y),
        energy=agent.energy,
        food=agent.food(),
        status=agent.status,
        season_phase=(state.tick % max(1, rules.hazard_period)) / max(1, rules.hazard_period),
    )

    for other in state.agents.values():
        if other.id == agent.id or not other.alive:
            continue
        d = distance(agent.x, agent.y, other.x, other.y)
        if d <= radius:
            obs.nearby_agents.append(NearbyAgent(other, d))
    obs.nearby_agents.sort(key=lambda n: (n.distance, n.agent.id))

    for s in state.structures.values():
        if distance(agent.x, agent.y, s.x, s.y) <= radius:
            obs.nearby_structures.append(s)
    obs.nearby_structures.sort(key=lambda s: s.id)

    rc = int(math.ceil(radius / cs))
    x0, x1 = max(0, cx - rc), min(state.cols - 1, cx + rc)
    y0, y1 = max(0, cy - rc), min(state.rows - 1, cy + rc)
    sub = grid["resource"][y0 : y1 + 1, x0 : x1 + 1]
    ys, xs = np.nonzero(sub > 0.08)
    for yy, xx in zip(ys.tolist(), xs.tolist(), strict=True):
        gx, gy = x0 + xx, y0 + yy
        wx, wy = state.cell_center(gx, gy)
        d = distance(agent.x, agent.y, wx, wy)
        if d <= radius:
            obs.visible_resources.append(VisibleResource(gx, gy, wx, wy, float(sub[yy, xx]), d))
    obs.visible_resources.sort(key=lambda v: (-v.level / (1 + v.distance), v.cx, v.cy))

    edge = radius / 2
    if agent.x < edge:
        obs.near_edge.append("west")
    if agent.x > state.config.width - edge:
        obs.near_edge.append("east")
    if agent.y < edge:
        obs.near_edge.append("north")
    if agent.y > state.config.height - edge:
        obs.near_edge.append("south")

    obs.portals_nearby = sum(1 for p in state.portals if distance(agent.x, agent.y, p.x, p.y) <= radius)
    return obs


def perceive_and_remember(state: UniverseState, agent: AgentState, obs: Observation) -> None:
    """Turn salient facts in an observation into observation-grade memories. Called from the tick
    loop at a low rate so memories stay sparse and meaningful."""
    rules = state.config.rules
    ids = state.ids
    assert ids is not None

    for vr in obs.visible_resources[:3]:
        known = any(abs(k[0] - vr.x) < 1e-6 and abs(k[1] - vr.y) < 1e-6 for k in agent.known_resources)
        if not known:
            agent.known_resources.append([vr.x, vr.y])
            if len(agent.known_resources) > 12:
                agent.known_resources = agent.known_resources[-12:]
            agent.remember(Memory(ids.memory(), state.tick, "perception", f"Noticed a resource patch at ({vr.x:.0f}, {vr.y:.0f}) with level {vr.level:.2f}.", 0.25, data={"x": vr.x, "y": vr.y}))

    if agent.energy < 0.25 and not any(m.kind == "perception" and "critically low" in m.summary and state.tick - m.tick < 200 for m in agent.memories[-10:]):
        agent.remember(Memory(ids.memory(), state.tick, "perception", f"Energy critically low ({agent.energy:.2f}).", 0.5))

    if obs.hazard_here > 0.45 and rules.hazard_amplitude > 0 and not any("hazard" in m.summary and state.tick - m.tick < 300 for m in agent.memories[-10:]):
        agent.remember(Memory(ids.memory(), state.tick, "perception", f"Hazard here is high ({obs.hazard_here:.2f}); the air feels dangerous.", 0.4))

    for n in obs.nearby_agents[:3]:
        if n.agent.id not in agent.relationships:
            agent.adjust_affinity(n.agent.id, 0.0, "ally", state.tick)
            agent.relationships[n.agent.id].kind = "ally" if agent.relationships[n.agent.id].affinity >= 0 else "rival"
            agent.remember(Memory(ids.memory(), state.tick, "social", f"Met {n.agent.name} ({n.agent.id.upper()}) nearby.", 0.3, data={"agentId": n.agent.id}))
