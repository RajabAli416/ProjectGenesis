"""Render-facing WorldSnapshot and domain DTO builders (domain state -> API schemas)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from app.agents.agent import TRAIT_LABELS, AgentState
from app.api import schemas as S
from app.core.timeutil import now_iso
from app.simulation import terrain

if TYPE_CHECKING:
    from app.simulation.state import UniverseState


def world_snapshot(state: UniverseState, resource_threshold: float = 0.2) -> S.WorldSnapshot:
    g = state.grid
    cs = state.config.cell_size
    cls = g["cls"]
    elev = g["elevation"]
    built = g["built"]
    cells: list[S.TerrainCell] = []
    rows, cols = cls.shape
    for y in range(rows):
        for x in range(cols):
            c = int(cls[y, x])
            name = "built" if built[y, x] else terrain.CLASS_NAMES[c]
            cells.append(S.TerrainCell(x=x, y=y, cls=name, v=float(elev[y, x])))

    entities: list[S.EntityMarker] = []
    for a in sorted(state.agents.values(), key=lambda a: a.id):
        if a.status == "deceased" and a.died_at_tick is not None and state.tick - a.died_at_tick > 600:
            continue
        entities.append(S.EntityMarker(id=a.id, kind="agent", x=round(a.x, 2), y=round(a.y, 2), level=round(max(0.0, min(1.0, a.energy)), 3), faded=a.status != "active", label=a.name))
    for s in state.structures.values():
        entities.append(S.EntityMarker(id=s.id, kind="structure", x=s.x, y=s.y, level=round(max(0.0, min(1.0, s.condition)), 3), label=s.kind))
    res = g["resource"]
    ys, xs = np.nonzero(res >= resource_threshold)
    for y, x in zip(ys.tolist(), xs.tolist(), strict=True):
        wx, wy = state.cell_center(x, y)
        entities.append(S.EntityMarker(id=f"r-{x}-{y}", kind="resource", x=wx, y=wy, level=round(float(min(1.0, res[y, x])), 3)))
    for p in state.portals:
        entities.append(S.EntityMarker(id=f"portal-{p.child_id}", kind="portal", x=p.x, y=p.y, level=1.0, label=p.child_id))

    return S.WorldSnapshot(universe_id=state.id, tick=state.tick, width=state.config.width, height=state.config.height, cell_size=cs, terrain=cells, entities=entities)


def population_stats(state: UniverseState) -> S.PopulationStats:
    alive = state.alive_agents()
    n = len(alive)
    return S.PopulationStats(
        total=len(state.agents),
        alive=n,
        born=state.born,
        died=state.died,
        mean_energy=round(sum(a.energy for a in alive) / n, 4) if n else 0.0,
        mean_age=round(sum(a.age for a in alive) / n, 1) if n else 0.0,
        generations=state.max_generation,
    )


def world_conditions(state: UniverseState) -> S.WorldConditions:
    g = state.grid
    fertile = g["cls"] == terrain.FERTILE
    return S.WorldConditions(
        width=state.config.width,
        height=state.config.height,
        seed=state.seed,
        fields=[
            S.WorldField(key="fertility", label="Fertility", value=round(float(g["fertility"].mean()), 3)),
            S.WorldField(key="hazard", label="Hazard", value=round(float(g["hazard"].mean()), 3)),
            S.WorldField(key="resource", label="Resource density", value=round(float(g["resource"][fertile].mean()) if fertile.any() else 0.0, 3)),
            S.WorldField(key="temperature", label="Temperature", value=round(state.config.rules.temperature, 3)),
        ],
    )


def universe_dto(state: UniverseState, rate: float) -> S.Universe:
    stage = state.civilization.stage if state.status != "initialising" else None
    return S.Universe(
        id=state.id,
        name=state.name,
        code=state.code,
        status=state.status,  # type: ignore[arg-type]
        clock=S.SimulationClock(tick=state.tick, rate=round(rate, 2), speed=state.speed, observed_at=now_iso()),
        lineage=S.UniverseLineage(
            parent_id=state.parent_id,
            depth=state.depth,
            created_by=S.CreatedBy(kind=state.created_by_kind, id=state.created_by_id, label=state.created_by_label),  # type: ignore[arg-type]
            created_at_tick=state.created_at_tick,
            created_at=state.created_at,
        ),
        population=population_stats(state),
        world=world_conditions(state),
        civilization_stage=stage,  # type: ignore[arg-type]
        child_ids=list(state.child_ids),
        mode=state.config.mode,
        cell_size=state.config.cell_size,
        model_ref=state.model_ref,
        compute_share=state.compute_share,
        config_version=state.config.config_version,
        engine_version=state.engine_version,
    )


def agent_dto(state: UniverseState, a: AgentState, memory_limit: int | None = None) -> S.Agent:
    mems = a.memories if memory_limit is None else a.memories[-memory_limit:]
    return S.Agent(
        id=a.id,
        universe_id=state.id,
        name=a.name,
        status=a.status,  # type: ignore[arg-type]
        generation=a.generation,
        born_at_tick=a.born_at_tick,
        died_at_tick=a.died_at_tick,
        age=a.age,
        energy=round(max(0.0, min(1.0, a.energy)), 4),
        position=S.Position(x=round(a.x, 2), y=round(a.y, 2)),
        lineage=S.AgentLineage(parent_ids=list(a.parent_ids), offspring_ids=list(a.offspring_ids)),
        relationships=[S.AgentRelationship(agent_id=r.agent_id, kind=r.kind, affinity=round(r.affinity, 3), since_tick=r.since_tick) for r in sorted(a.relationships.values(), key=lambda r: r.since_tick)],  # type: ignore[arg-type]
        knowledge=[S.KnowledgeItem(id=b.id, topic=b.topic, confidence=round(b.confidence, 3), acquired_at_tick=b.acquired_at_tick, source=b.source, statement=b.statement) for b in a.beliefs.values()]  # type: ignore[arg-type]
        + [S.KnowledgeItem(id=f"tk-{a.id}-{t}", topic=f"Technique: {t}", confidence=round(min(1.0, p / 100.0), 3), acquired_at_tick=a.born_at_tick, source="taught" if a.parent_ids else "observation") for t, p in a.tech_knowledge.items() if p > 0],
        memory=[S.MemoryRecord(id=m.id, tick=m.tick, kind=m.kind, summary=m.summary, salience=round(m.salience, 3), source=m.source) for m in mems],  # type: ignore[arg-type]
        traits=[S.Trait(key=k, label=TRAIT_LABELS.get(k, k.title()), value=round(v, 3)) for k, v in a.traits.items()],
        inventory={k: round(v, 3) for k, v in a.inventory.items()},
        intent={"type": a.intent.type, "params": a.intent.params, "startedTick": a.intent.started_tick, "policy": a.intent.policy, "progress": round(a.intent.progress, 3), "decisionId": a.intent.decision_id} if a.intent else None,
        policy=a.policy,  # type: ignore[arg-type]
        model_ref=a.model_ref,
        decisions_total=a.decisions_total,
        decisions_model=a.decisions_model,
    )
