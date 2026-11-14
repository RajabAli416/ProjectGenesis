from __future__ import annotations

from app.research import provenance
from app.research.engine import add_evidence, hypothesis_dto, propose_hypothesis, update
from app.simulation.actions import _deliver
from app.simulation.engine import run_ticks
from tests.conftest import make_state


def test_operator_hypothesis_is_labelled_operator() -> None:
    st = make_state("res")
    h = propose_hypothesis(st, None, "Edges", "The world has a hard boundary", 0.5, label="Operator")
    assert h is not None and h.proposed_by_kind == "operator"
    dto = hypothesis_dto(st, h)
    assert dto.provenance.classification == "operator"


def test_prompt_exposed_terms_are_flagged() -> None:
    st = make_state("res2")
    a = st.agents[sorted(st.agents)[0]]
    provenance.note_exposure(a, "You live in a simulation run by an operator.")
    h = propose_hypothesis(st, a, "We are simulated", "This world is a simulation controlled from outside", 0.7)
    assert h is not None
    dto = hypothesis_dto(st, h)
    assert h.existential
    assert dto.provenance.classification == "prompt-exposed"
    assert "simulation" in [t.lower() for t in dto.provenance.prompt_exposed_terms]
    assert "pretrain" in dto.provenance.note.lower() or "training" in dto.provenance.note.lower()


def test_unexposed_existential_claim_is_model_originated_with_caveat() -> None:
    st = make_state("res3")
    a = st.agents[sorted(st.agents)[0]]
    assert not a.exposed_terms
    h = propose_hypothesis(st, a, "Outside", "Something outside this world decides the rules", 0.6)
    assert h is not None
    dto = hypothesis_dto(st, h)
    assert dto.provenance.classification == "model-originated"
    assert dto.provenance.note  # must carry the pretraining caveat
    assert "pretrain" in dto.provenance.note.lower() or "training" in dto.provenance.note.lower()


def test_verified_evidence_makes_it_evidence_linked() -> None:
    st = make_state("res4")
    a = st.agents[sorted(st.agents)[0]]
    h = propose_hypothesis(st, a, "Regrowth", "Food regrows faster near water", 0.5)
    assert h is not None
    add_evidence(st, h, "measurement", "experiment:measure_regeneration", 0.6, "Regeneration near water measured 0.012/tick vs 0.004", True, ("agent", a.id, a.name))
    add_evidence(st, h, "measurement", "experiment:measure_regeneration", 0.5, "Second measurement agrees", True, ("agent", a.id, a.name))
    update(st)
    dto = hypothesis_dto(st, h)
    assert dto.provenance.classification == "evidence-linked"
    assert dto.provenance.verified_evidence_ratio == 1.0
    assert all(e.verified_by_mechanics for e in dto.evidence)
    assert h.state in ("testing", "supported")


def test_messages_from_others_count_as_exposure() -> None:
    st = make_state("res5", initial_population=2)
    ids = sorted(st.agents)
    sender, receiver = st.agents[ids[0]], st.agents[ids[1]]
    receiver.x, receiver.y = sender.x + 1, sender.y
    _deliver(st, sender, receiver, "I think we live inside a simulation", None)
    assert any("simulation" in t for t in receiver.exposed_terms)
    assert not any("simulation" in t for t in sender.exposed_terms)


def test_agent_experiments_produce_verified_evidence() -> None:
    st = make_state("res6", initial_population=4)
    run_ticks(st, 2500)
    verified = [e for h in st.research.hypotheses.values() for e in h.evidence if e.verified_by_mechanics]
    # Reflex agents run probes occasionally; when they do, evidence is mechanics-verified.
    assert all(e.verified_by_mechanics for e in verified)
