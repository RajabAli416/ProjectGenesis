"""Per-agent state. Every agent owns its own memories, beliefs, relationships, inbox and decision
history. Nothing here is shared between agents, even when they are advised by the same model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

TRAIT_LABELS = {"curiosity": "Curiosity", "endurance": "Endurance", "sociality": "Sociality", "risk": "Risk tolerance"}


@dataclass
class Memory:
    id: str
    tick: int
    kind: str  # perception | action | social | reflection
    summary: str
    salience: float
    source: str = "observation"  # observation | inference | taught | inherited
    data: dict[str, Any] | None = None


@dataclass
class Belief:
    id: str
    topic: str
    statement: str
    confidence: float
    source: str  # observation | inference | taught | inherited
    acquired_at_tick: int
    revision: int = 1
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class Relationship:
    agent_id: str
    kind: str
    affinity: float
    since_tick: int


@dataclass
class Message:
    id: str
    tick: int
    sender_id: str
    text: str
    topic: str | None = None


@dataclass
class Intent:
    type: str
    params: dict[str, Any]
    started_tick: int
    policy: str  # reflex | model
    decision_id: int | None = None
    ttl: int = 200
    progress: float = 0.0
    state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentState:
    id: str
    name: str
    born_at_tick: int
    generation: int
    x: float
    y: float
    traits: dict[str, float]
    energy: float = 0.8
    status: str = "active"  # active | dormant | deceased
    age: int = 0
    died_at_tick: int | None = None
    parent_ids: list[str] = field(default_factory=list)
    offspring_ids: list[str] = field(default_factory=list)
    relationships: dict[str, Relationship] = field(default_factory=dict)
    memories: list[Memory] = field(default_factory=list)
    beliefs: dict[str, Belief] = field(default_factory=dict)
    inventory: dict[str, float] = field(default_factory=lambda: {"food": 0.0})
    inbox: list[Message] = field(default_factory=list)
    intent: Intent | None = None
    last_decision_tick: int = -10_000
    last_reflection_tick: int = 0
    last_reproduction_tick: int = -10_000
    pending_request: bool = False
    decisions_total: int = 0
    decisions_model: int = 0
    policy: str = "reflex"
    model_ref: str | None = None
    # Existential-lexicon terms this agent has been exposed to through prompts or messages.
    exposed_terms: list[str] = field(default_factory=list)
    # Knowledge about tech topics: progress toward investigation.
    tech_knowledge: dict[str, float] = field(default_factory=dict)
    known_resources: list[list[float]] = field(default_factory=list)
    salient_since_decision: float = 0.0
    hypothesis_ids: list[str] = field(default_factory=list)
    memory_counter: int = 0

    # ------------------------------------------------------------------ helpers

    @property
    def alive(self) -> bool:
        return self.status != "deceased"

    @property
    def pos(self) -> tuple[float, float]:
        return (self.x, self.y)

    def food(self) -> float:
        return self.inventory.get("food", 0.0)

    def add_food(self, amount: float, cap: float) -> float:
        before = self.food()
        after = min(cap, before + amount)
        self.inventory["food"] = after
        return after - before

    def take_food(self, amount: float) -> float:
        have = self.food()
        taken = min(have, amount)
        self.inventory["food"] = have - taken
        return taken

    def remember(self, mem: Memory, max_items: int = 400) -> None:
        self.memories.append(mem)
        self.salient_since_decision += mem.salience
        if len(self.memories) > max_items:
            # Drop the least salient old memories, keeping the newest half intact.
            keep_new = self.memories[-max_items // 2 :]
            old = sorted(self.memories[: -max_items // 2], key=lambda m: m.salience, reverse=True)[: max_items // 2]
            old.sort(key=lambda m: m.tick)
            self.memories = old + keep_new

    def relationship(self, other_id: str) -> Relationship | None:
        return self.relationships.get(other_id)

    def adjust_affinity(self, other_id: str, delta: float, kind: str, tick: int) -> Relationship:
        rel = self.relationships.get(other_id)
        if rel is None:
            rel = Relationship(agent_id=other_id, kind=kind, affinity=0.0, since_tick=tick)
            self.relationships[other_id] = rel
        rel.affinity = max(-1.0, min(1.0, rel.affinity + delta))
        if rel.kind not in ("parent", "offspring", "partner"):
            if rel.affinity < -0.3:
                rel.kind = "rival"
            elif rel.affinity > 0.5 and rel.kind not in ("mentor", "student"):
                rel.kind = "ally"
        return rel

    # ------------------------------------------------------------------ serialization

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentState:
        d = dict(d)
        d["relationships"] = {k: Relationship(**v) for k, v in d.get("relationships", {}).items()}
        d["memories"] = [Memory(**m) for m in d.get("memories", [])]
        d["beliefs"] = {k: Belief(**v) for k, v in d.get("beliefs", {}).items()}
        d["inbox"] = [Message(**m) for m in d.get("inbox", [])]
        d["intent"] = Intent(**d["intent"]) if d.get("intent") else None
        return cls(**d)
