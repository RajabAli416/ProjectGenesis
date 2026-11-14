"""Research engine: hypotheses, evidence, reasoning steps, belief revision and technology
investigation. Evidence produced by mechanics is marked verified; evidence derived from model text
is not."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.agents.agent import AgentState, Belief, Intent, Memory
from app.api import schemas as S
from app.research import provenance
from app.simulation.state import EvidenceState, HypothesisState, ReasoningStepState

if TYPE_CHECKING:
    from app.simulation.state import UniverseState

MAX_HYPOTHESES_PER_AGENT = 6
MAX_BELIEFS = 40


def propose_hypothesis(state: UniverseState, proposer: AgentState | None, title: str, statement: str, confidence: float, label: str | None = None, experiment_ids: list[str] | None = None) -> HypothesisState | None:
    assert state.ids is not None
    title = provenance.squash(title, 120)
    statement = provenance.squash(statement, 600)
    if not title or not statement:
        return None
    # Deduplicate on title for the same proposer.
    for h in state.research.hypotheses.values():
        if h.title.lower() == title.lower() and (proposer is None or h.proposed_by_id == proposer.id):
            return h
    if proposer is not None and len([h for h in state.research.hypotheses.values() if h.proposed_by_id == proposer.id]) >= MAX_HYPOTHESES_PER_AGENT:
        return None
    hyp = HypothesisState(
        id=state.ids.hypothesis(),
        title=title,
        statement=statement,
        state="proposed",
        confidence=max(0.0, min(1.0, confidence)),
        proposed_at_tick=state.tick,
        proposed_by_kind="agent" if proposer else "operator",
        proposed_by_id=proposer.id if proposer else None,
        proposed_by_label=label or (f"{proposer.name} ({proposer.id.upper()})" if proposer else "Operator"),
        experiment_ids=list(experiment_ids or []),
        existential=provenance.is_existential(title, statement),
        exposed_terms=list(proposer.exposed_terms) if proposer else [],
    )
    hyp.reasoning.append(ReasoningStepState(state.ids.reasoning(), 1, state.tick, "agent" if proposer else "operator", proposer.id if proposer else None, proposer.name if proposer else "Operator", f"Proposed: {statement[:200]}", hyp.confidence))
    provenance.classify(state, hyp)
    state.research.hypotheses[hyp.id] = hyp
    if proposer is not None:
        proposer.hypothesis_ids.append(hyp.id)
        proposer.remember(Memory(state.ids.memory(), state.tick, "reflection", f"Proposed hypothesis: {title}", 0.7, source="inference", data={"hypothesis": hyp.id}))
    state.emit("notice", "research", f"Hypothesis {hyp.id.upper()} proposed by {hyp.proposed_by_label}: {title}", [{"kind": "hypothesis", "id": hyp.id}] + ([{"kind": "agent", "id": proposer.id}] if proposer else []))
    return hyp


def add_evidence(state: UniverseState, hyp: HypothesisState, kind: str, source: str, weight: float, summary: str, verified: bool, actor: tuple[str, str | None, str]) -> EvidenceState:
    assert state.ids is not None
    weight = max(-1.0, min(1.0, weight))
    ev = EvidenceState(state.ids.evidence(), kind, source, round(weight, 3), state.tick, provenance.squash(summary, 300), verified)
    hyp.evidence.append(ev)
    before = hyp.confidence
    hyp.confidence = max(0.02, min(0.98, hyp.confidence + weight * (0.25 if verified else 0.08)))
    hyp.reasoning.append(ReasoningStepState(state.ids.reasoning(), len(hyp.reasoning) + 1, state.tick, actor[0], actor[1], actor[2], f"{'Verified' if verified else 'Unverified'} {kind}: {ev.summary[:160]} Confidence {before:.2f} → {hyp.confidence:.2f}.", hyp.confidence))
    hyp.dirty = True
    return ev


def update_states(state: UniverseState) -> None:
    for hyp in state.research.hypotheses.values():
        if hyp.state in ("withdrawn",):
            continue
        verified = [e for e in hyp.evidence if e.verified_by_mechanics]
        active = any(x.get("hypothesisId") == hyp.id for x in state.research.active_experiments.values())
        new_state = hyp.state
        if hyp.confidence >= 0.8 and len(verified) >= 2:
            new_state = "supported"
        elif hyp.confidence <= 0.2 and verified:
            new_state = "refuted"
        elif active or hyp.experiment_ids or (hyp.evidence and hyp.state == "proposed"):
            new_state = "testing"
        if new_state != hyp.state:
            hyp.state = new_state
            state.emit("notice", "research", f"Hypothesis {hyp.id.upper()} is now {new_state}.", [{"kind": "hypothesis", "id": hyp.id}])
        if hyp.dirty:
            provenance.classify(state, hyp)
            hyp.dirty = False


def update(state: UniverseState) -> None:
    update_states(state)


def apply_belief_updates(state: UniverseState, agent: AgentState, updates: list[dict[str, Any]]) -> list[Belief]:
    """Model-asserted belief changes. Always recorded with source 'inference'."""
    assert state.ids is not None
    out: list[Belief] = []
    for u in updates[:4]:
        topic = provenance.squash(str(u.get("topic", "")), 80)
        statement = provenance.squash(str(u.get("statement", "")), 240)
        if not topic or not statement:
            continue
        conf = float(u.get("confidence", 0.5))
        conf = max(0.0, min(1.0, conf))
        existing = agent.beliefs.get(topic)
        if existing is None:
            if len(agent.beliefs) >= MAX_BELIEFS:
                weakest = min(agent.beliefs.values(), key=lambda b: b.confidence)
                del agent.beliefs[weakest.topic]
            b = Belief(state.ids.belief(), topic, statement, conf, "inference", state.tick)
            agent.beliefs[topic] = b
        else:
            # Observation-grade beliefs are not overwritten by model assertions; they are only nudged.
            if existing.source == "observation":
                existing.confidence = round((existing.confidence * 3 + conf) / 4, 3)
            else:
                existing.statement = statement
                existing.confidence = conf
            existing.revision += 1
            b = existing
        out.append(b)
        state.outbox_beliefs.append({"id": b.id, "agent_id": agent.id, "universe_id": state.id, "tick": state.tick, "topic": b.topic, "statement": b.statement, "confidence": b.confidence, "source": b.source, "revision": b.revision})
    return out


# ------------------------------------------------------------------------------ investigation

NATURAL_TOPICS = {"world_edge", "hazard_cycle", "resource_regeneration"}


def investigate_step(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    topic = str(intent.params["topic"])
    rules = state.config.rules
    gain = rules.investigate_rate * (0.5 + agent.traits.get("curiosity", 0.5))
    intent.progress += gain
    assert state.ids is not None
    if topic in NATURAL_TOPICS:
        if intent.progress < 60:
            return False
        if topic == "world_edge":
            stmt = "The world has an edge that stops movement." if rules.edge_mode == "clamp" else "Moving past the edge brings one back on the far side."
        elif topic == "hazard_cycle":
            stmt = f"Hazard rises and falls in a cycle of about {rules.hazard_period:,} ticks." if rules.hazard_amplitude > 0.05 else "Hazard does not follow a cycle."
        else:
            stmt = "Resource patches regenerate over time on fertile ground." if rules.resource_regen > 0 else "Resource patches do not regenerate."
        b = agent.beliefs.get(topic)
        if b is None:
            agent.beliefs[topic] = Belief(state.ids.belief(), topic.replace("_", " ").title(), stmt, 0.6, "observation", state.tick)
        else:
            b.confidence = min(0.95, b.confidence + 0.1)
            b.revision += 1
        agent.remember(Memory(state.ids.memory(), state.tick, "reflection", f"Studied {topic.replace('_', ' ')}: {stmt}", 0.6))
        return True

    spec = next((t for t in state.config.technology_tree if t.id == topic), None)
    if spec is None:
        return True
    ts = state.civilization.technologies[topic]
    agent.tech_knowledge[topic] = agent.tech_knowledge.get(topic, 0.0) + gain
    ts.progress = max(ts.progress, agent.tech_knowledge[topic])
    if ts.state == "unknown" and agent.tech_knowledge[topic] >= spec.effort:
        ts.state = "emerging"
        ts.discovered_at_tick = state.tick
        ts.discovered_by = agent.id
        agent.remember(Memory(state.ids.memory(), state.tick, "reflection", f"Worked out {spec.name.lower()}.", 0.9, data={"tech": topic}))
        state.emit("notice", "civilization", f"{spec.name} reached emerging state (discovered by {agent.name}).", [{"kind": "agent", "id": agent.id}])
        return True
    return ts.state != "unknown" and agent.tech_knowledge[topic] >= spec.effort


# ------------------------------------------------------------------------------ DTO


def hypothesis_dto(state: UniverseState, h: HypothesisState) -> S.Hypothesis:
    return S.Hypothesis(
        id=h.id,
        universe_id=state.id,
        title=h.title,
        statement=h.statement,
        state=h.state,  # type: ignore[arg-type]
        confidence=round(h.confidence, 3),
        proposed_at_tick=h.proposed_at_tick,
        proposed_by=S.ProposedBy(kind=h.proposed_by_kind, id=h.proposed_by_id, label=h.proposed_by_label),  # type: ignore[arg-type]
        evidence=[S.Evidence(id=e.id, kind=e.kind, source=e.source, weight=e.weight, tick=e.tick, summary=e.summary, verified_by_mechanics=e.verified_by_mechanics) for e in h.evidence],  # type: ignore[arg-type]
        reasoning=[S.ReasoningStep(id=r.id, index=r.index, tick=r.tick, actor=S.Actor(kind=r.actor_kind, id=r.actor_id, label=r.actor_label), statement=r.statement, confidence=round(r.confidence, 3)) for r in h.reasoning],  # type: ignore[arg-type]
        experiment_ids=list(h.experiment_ids),
        provenance=S.Provenance(classification=h.provenance_class, prompt_exposed_terms=[t for t in h.topic_terms if t in h.exposed_terms], verified_evidence_ratio=round(provenance.verified_ratio(h), 3), note=provenance.provenance_note(h)),  # type: ignore[arg-type]
        existential=h.existential,
    )
