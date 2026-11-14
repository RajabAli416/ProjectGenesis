"""Provenance and contamination tracking for hypotheses.

A hypothesis mentioning the simulation hypothesis is not a discovery. For every hypothesis we record
which existential terms the proposing agent had already been exposed to through prompts or other
agents' messages, and how much of its evidence is mechanics-verified. The classification never
claims independence: model pretraining priors cannot be excluded for any locally hosted model."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.agents.agent import AgentState

if TYPE_CHECKING:
    from app.simulation.state import HypothesisState, UniverseState

# Terms whose presence in a hypothesis marks it as touching on the nature/origin of the world.
EXISTENTIAL_TERMS = [
    "simulation", "simulated", "simulator", "creator", "created us", "designer", "designed", "god", "deity",
    "observer", "observed by", "watched", "outside world", "outside the world", "beyond the edge", "program",
    "programmed", "computer", "artificial", "nested", "sub-world", "subworld", "higher world", "operator",
    "experiment on us", "not real", "illusion", "rules were set", "someone made",
]
# Broader lexicon used for exposure tracking (includes the existential terms).
LEXICON = EXISTENTIAL_TERMS + ["universe", "world boundary", "edge of the world", "instantiat", "hypothesis", "rules of the world"]

PRETRAINING_NOTE = "Model pretraining priors cannot be excluded for any locally hosted model."


def find_terms(text: str, lexicon: list[str] = LEXICON) -> list[str]:
    low = text.lower()
    return sorted({t for t in lexicon if t in low})


def note_exposure(agent: AgentState, text: str) -> None:
    for t in find_terms(text):
        if t not in agent.exposed_terms:
            agent.exposed_terms.append(t)


def is_existential(title: str, statement: str) -> bool:
    return bool(find_terms(f"{title} {statement}", EXISTENTIAL_TERMS))


def classify(state: UniverseState, hyp: HypothesisState) -> None:
    """Recompute provenance fields on a hypothesis in place."""
    if hyp.proposed_by_kind == "operator":
        hyp.provenance_class = "operator"
        return
    terms = find_terms(f"{hyp.title} {hyp.statement}")
    hyp.topic_terms = terms
    overlap = [t for t in terms if t in hyp.exposed_terms]
    verified = [e for e in hyp.evidence if e.verified_by_mechanics]
    ratio = len(verified) / len(hyp.evidence) if hyp.evidence else 0.0
    if overlap:
        hyp.provenance_class = "prompt-exposed"
    elif hyp.evidence and ratio >= 0.5:
        hyp.provenance_class = "evidence-linked"
    else:
        hyp.provenance_class = "model-originated"


def provenance_note(hyp: HypothesisState) -> str:
    verified = [e for e in hyp.evidence if e.verified_by_mechanics]
    ratio = len(verified) / len(hyp.evidence) if hyp.evidence else 0.0
    overlap = [t for t in hyp.topic_terms if t in hyp.exposed_terms]
    if hyp.provenance_class == "operator":
        return "Proposed by the operator; not an agent claim."
    if hyp.provenance_class == "prompt-exposed":
        return f"Key terms ({', '.join(overlap)}) appeared in prompts or messages the proposer received before proposing. {PRETRAINING_NOTE}"
    if hyp.provenance_class == "evidence-linked":
        return f"{ratio:.0%} of evidence was produced by world mechanics. {PRETRAINING_NOTE}"
    return f"No prior prompt exposure to its key terms was recorded and little or no mechanics-verified evidence exists. {PRETRAINING_NOTE}"


def verified_ratio(hyp: HypothesisState) -> float:
    if not hyp.evidence:
        return 0.0
    return len([e for e in hyp.evidence if e.verified_by_mechanics]) / len(hyp.evidence)


_ws = re.compile(r"\s+")


def squash(text: str, limit: int) -> str:
    text = _ws.sub(" ", text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"
