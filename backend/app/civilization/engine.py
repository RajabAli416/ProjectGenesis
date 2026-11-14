"""Civilization is *derived* from mechanics: relationship graphs, structures, technology holders
and recorded trades. No model text is ever consulted here."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from app.api import schemas as S
from app.simulation.state import EraState, InstitutionState, TechState

if TYPE_CHECKING:
    from app.simulation.state import UniverseState

STAGES = ["none", "bands", "settlements", "polities", "industrial", "reflective"]
STAGE_LABELS = {"none": "Dispersal", "bands": "Bands", "settlements": "Settlements", "polities": "Polities", "industrial": "Industrial", "reflective": "Reflective"}
GROUP_AFFINITY = 0.3
MIN_GROUP = 3


def _spec(state: UniverseState, tid: str):
    return next((t for t in state.config.technology_tree if t.id == tid), None)


def tech_holders(state: UniverseState, tid: str) -> list[str]:
    spec = _spec(state, tid)
    if spec is None:
        return []
    need = spec.effort * 0.5
    return [a.id for a in state.alive_agents() if a.tech_knowledge.get(tid, 0.0) >= need]


def update_technologies(state: UniverseState) -> None:
    for tid, ts in state.civilization.technologies.items():
        spec = _spec(state, tid)
        if spec is None:
            continue
        if ts.state == "emerging":
            holders = tech_holders(state, tid)
            if len(holders) >= spec.establish_holders:
                ts.state = "established"
                state.emit("notice", "civilization", f"{spec.name} is now established ({len(holders)} holders).")


def compute_groups(state: UniverseState) -> list[list[str]]:
    alive = {a.id: a for a in state.alive_agents()}
    parent: dict[str, str] = {aid: aid for aid in alive}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    for aid, a in alive.items():
        for rel in a.relationships.values():
            if rel.agent_id in alive and rel.affinity >= GROUP_AFFINITY:
                union(aid, rel.agent_id)
    buckets: dict[str, list[str]] = defaultdict(list)
    for aid in alive:
        buckets[find(aid)].append(aid)
    groups = [sorted(g) for g in buckets.values() if len(g) >= MIN_GROUP]
    groups.sort(key=lambda g: g[0])
    return groups


def _group_key(state: UniverseState, group: list[str]) -> str:
    # The earliest-born member anchors the institution's identity across recomputations.
    return min(group, key=lambda aid: (state.agents[aid].born_at_tick, aid))


def _ensure_institution(state: UniverseState, key: str, name: str, kind: str, members: list[str], present: set[str]) -> None:
    present.add(key)
    inst = next((i for i in state.civilization.institutions.values() if i.key == key), None)
    if inst is None:
        assert state.ids is not None
        inst = InstitutionState(id=state.ids.institution(), name=name, kind=kind, members=sorted(members), founded_at_tick=state.tick, key=key)
        state.civilization.institutions[inst.id] = inst
        state.emit("notice", "civilization", f"{name} formed ({kind}, {len(members)} members).")
    else:
        inst.members = sorted(members)
        inst.name = name


def update_institutions(state: UniverseState, groups: list[list[str]]) -> None:
    present: set[str] = set()
    for group in groups:
        key = _group_key(state, group)
        anchor = state.agents[key].name
        _ensure_institution(state, f"kinship:{key}", f"{anchor} kin-group", "kinship", group, present)
        member_set = set(group)
        structures = [s for s in state.structures.values() if s.builder_id in member_set]
        if len(structures) >= 3:
            _ensure_institution(state, f"council:{key}", f"{anchor} council", "council", group, present)
        if state.civilization.trades >= 10:
            _ensure_institution(state, f"market:{key}", f"{anchor} exchange", "market", group, present)
    for tid, ts in state.civilization.technologies.items():
        if ts.state == "established":
            holders = tech_holders(state, tid)
            if len(holders) >= 3:
                spec = _spec(state, tid)
                _ensure_institution(state, f"guild:{tid}", f"{spec.name if spec else tid} guild", "guild", holders, present)
    proposers = sorted({h.proposed_by_id for h in state.research.hypotheses.values() if h.proposed_by_kind == "agent" and h.proposed_by_id in state.agents and state.agents[h.proposed_by_id].alive})
    if len(proposers) >= 2:
        _ensure_institution(state, "academy", "Observers", "academy", [p for p in proposers if p], present)
    for iid in [iid for iid, inst in state.civilization.institutions.items() if inst.key not in present]:
        inst = state.civilization.institutions.pop(iid)
        state.emit("info", "civilization", f"{inst.name} dissolved.")


def compute_stage(state: UniverseState, groups: list[list[str]]) -> str:
    civ = state.civilization
    alive = len(state.alive_agents())
    structures = len(state.structures)
    councils = [i for i in civ.institutions.values() if i.kind == "council"]
    established = [t for t in civ.technologies.values() if t.state == "established"]
    tier3 = [t for t in established if (_spec(state, t.id) and _spec(state, t.id).tier >= 3)]
    subworld = civ.technologies.get("subworld")
    existential = any(h.existential and h.state in ("testing", "supported") for h in state.research.hypotheses.values())

    stage = "none"
    if groups:
        stage = "bands"
    if groups and structures >= 3:
        stage = "settlements"
    if councils and (len(groups) >= 2 or alive >= 12):
        stage = "polities"
    if len(tier3) >= 2 and stage == "polities":
        stage = "industrial"
    if (subworld and subworld.state != "unknown") or existential:
        if STAGES.index(stage) >= STAGES.index("settlements"):
            stage = "reflective"
    return stage


def update_eras(state: UniverseState, stage: str) -> None:
    civ = state.civilization
    alive = len(state.alive_agents())
    if not civ.eras:
        assert state.ids is not None
        civ.eras.append(EraState(state.ids.era(), STAGE_LABELS["none"], 0, None, alive, "Unstructured foraging; no persistent groups."))
    current = civ.eras[-1]
    current.peak_population = max(current.peak_population, alive)
    if stage != civ.stage:
        # Stages only move forward; a collapse is recorded as an era note rather than a regression.
        if STAGES.index(stage) > STAGES.index(civ.stage):
            current.to_tick = state.tick
            assert state.ids is not None
            civ.eras.append(EraState(state.ids.era(), STAGE_LABELS[stage], state.tick, None, alive))
            civ.stage = stage
            state.emit("notice", "civilization", f"Civilization reached the {STAGE_LABELS[stage].lower()} stage.", [{"kind": "universe", "id": state.id}])


def update(state: UniverseState) -> None:
    update_technologies(state)
    groups = compute_groups(state)
    state.civilization.groups = groups
    update_institutions(state, groups)
    stage = compute_stage(state, groups)
    update_eras(state, stage)


def collective_knowledge(state: UniverseState, min_holders: int = 2) -> list[S.CollectiveKnowledge]:
    by_topic: dict[str, list[float]] = defaultdict(list)
    for a in state.alive_agents():
        for b in a.beliefs.values():
            by_topic[b.topic].append(b.confidence)
    out = []
    for i, (topic, confs) in enumerate(sorted(by_topic.items())):
        if len(confs) >= min_holders:
            out.append(S.CollectiveKnowledge(id=f"ck-{state.number:02d}-{i + 1}", topic=topic, holders=len(confs), confidence=round(sum(confs) / len(confs), 3)))
    return out


def infrastructure(state: UniverseState) -> list[S.Infrastructure]:
    by_kind: dict[str, list[float]] = defaultdict(list)
    for s in state.structures.values():
        by_kind[s.kind].append(s.condition)
    labels = {"shelter": "Shelters", "granary": "Granaries", "kiln": "Kilns", "channel": "Irrigation channels", "record_stone": "Record stones"}
    return [S.Infrastructure(id=f"inf-{kind}", name=labels.get(kind, kind.title()), count=len(c), condition=round(sum(c) / len(c), 3)) for kind, c in sorted(by_kind.items())]


def civilization_dto(state: UniverseState) -> S.Civilization:
    civ = state.civilization
    techs = []
    for spec in state.config.technology_tree:
        ts = civ.technologies.get(spec.id, TechState(id=spec.id))
        techs.append(S.Technology(id=spec.id, name=spec.name, tier=spec.tier, state=ts.state, requires=list(spec.requires), discovered_at_tick=ts.discovered_at_tick, discovered_by=ts.discovered_by, progress=round(min(1.0, ts.progress / spec.effort), 3)))  # type: ignore[arg-type]
    return S.Civilization(
        universe_id=state.id,
        stage=civ.stage,  # type: ignore[arg-type]
        eras=[S.PopulationEra(id=e.id, label=e.label, from_tick=e.from_tick, to_tick=e.to_tick, peak_population=e.peak_population, note=e.note) for e in civ.eras],
        technologies=techs,
        institutions=[S.Institution(id=i.id, name=i.name, kind=i.kind, members=len(i.members), founded_at_tick=i.founded_at_tick) for i in sorted(civ.institutions.values(), key=lambda i: i.founded_at_tick)],  # type: ignore[arg-type]
        infrastructure=infrastructure(state),
        collective_knowledge=collective_knowledge(state),
    )
