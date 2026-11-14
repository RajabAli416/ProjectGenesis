from __future__ import annotations

from app.agents.agent import Intent
from app.civilization.engine import civilization_dto, compute_groups, compute_stage, update
from app.simulation.engine import run_ticks
from tests.conftest import make_state


def test_groups_from_affinity() -> None:
    st = make_state("civ", initial_population=4)
    ids = sorted(st.agents)
    a, b, c, d = (st.agents[i] for i in ids)
    a.adjust_affinity(b.id, 0.6, "ally", st.tick)
    b.adjust_affinity(c.id, 0.6, "ally", st.tick)
    c.adjust_affinity(d.id, 0.1, "ally", st.tick)  # below the group threshold
    groups = compute_groups(st)
    assert groups == [[a.id, b.id, c.id]]
    assert all(d.id not in g for g in groups)


def test_stage_progression_is_mechanical() -> None:
    st = make_state("civ2", initial_population=6)
    assert compute_stage(st, compute_groups(st)) == "none"
    run_ticks(st, 1200)
    update(st)
    dto = civilization_dto(st)
    assert dto.stage in ("none", "bands", "settlements", "polities", "industrial", "reflective")
    assert len(dto.technologies) == len(st.config.technology_tree)
    assert all(t.state == "unknown" or t.discovered_at_tick is not None for t in dto.technologies)
    assert dto.universe_id == st.id


def test_build_creates_infrastructure() -> None:
    st = make_state("build", initial_population=3)
    a = st.agents[sorted(st.agents)[0]]
    a.add_food(20, 1000)
    a.energy = 0.9
    a.intent = Intent("build", {"kind": "shelter"}, st.tick, "reflex", ttl=400)
    run_ticks(st, 120)
    assert st.structures, "build intent produced no structure"
    update(st)
    dto = civilization_dto(st)
    assert any(i.count >= 1 for i in dto.infrastructure)
    assert st.civilization.first_structure_tick is not None
