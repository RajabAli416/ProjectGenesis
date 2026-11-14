"""The complete mutable state of one universe. One instance per universe; never shared.
Serialisable to a dict for snapshots and restorable from it."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from app.agents.agent import AgentState
from app.core.ids import LocalIdFactory
from app.core.rng import RngStreams
from app.simulation import terrain
from app.simulation.config import UniverseConfig

GRID_DTYPES = {
    "elevation": np.float32,
    "moisture": np.float32,
    "fertility": np.float32,
    "cls": np.int8,
    "resource": np.float32,
    "hazard_base": np.float32,
    "hazard": np.float32,
    "built": np.int8,
}


@dataclass
class Structure:
    id: str
    kind: str  # shelter | granary | kiln | channel | record_stone
    cx: int
    cy: int
    x: float
    y: float
    condition: float
    built_tick: int
    builder_id: str | None


@dataclass
class TechState:
    id: str
    state: str = "unknown"  # unknown | emerging | established
    progress: float = 0.0
    discovered_at_tick: int | None = None
    discovered_by: str | None = None


@dataclass
class InstitutionState:
    id: str
    name: str
    kind: str
    members: list[str]
    founded_at_tick: int
    key: str


@dataclass
class EraState:
    id: str
    label: str
    from_tick: int
    to_tick: int | None
    peak_population: int
    note: str | None = None


@dataclass
class CivilizationState:
    stage: str = "none"
    eras: list[EraState] = field(default_factory=list)
    technologies: dict[str, TechState] = field(default_factory=dict)
    institutions: dict[str, InstitutionState] = field(default_factory=dict)
    groups: list[list[str]] = field(default_factory=list)
    trades: int = 0
    messages: int = 0
    first_structure_tick: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CivilizationState:
        return cls(
            stage=d.get("stage", "none"),
            eras=[EraState(**e) for e in d.get("eras", [])],
            technologies={k: TechState(**v) for k, v in d.get("technologies", {}).items()},
            institutions={k: InstitutionState(**v) for k, v in d.get("institutions", {}).items()},
            groups=[list(g) for g in d.get("groups", [])],
            trades=d.get("trades", 0),
            messages=d.get("messages", 0),
            first_structure_tick=d.get("first_structure_tick"),
        )


@dataclass
class EvidenceState:
    id: str
    kind: str
    source: str
    weight: float
    tick: int
    summary: str
    verified_by_mechanics: bool = False


@dataclass
class ReasoningStepState:
    id: str
    index: int
    tick: int
    actor_kind: str
    actor_id: str | None
    actor_label: str
    statement: str
    confidence: float


@dataclass
class HypothesisState:
    id: str
    title: str
    statement: str
    state: str
    confidence: float
    proposed_at_tick: int
    proposed_by_kind: str
    proposed_by_id: str | None
    proposed_by_label: str
    evidence: list[EvidenceState] = field(default_factory=list)
    reasoning: list[ReasoningStepState] = field(default_factory=list)
    experiment_ids: list[str] = field(default_factory=list)
    existential: bool = False
    exposed_terms: list[str] = field(default_factory=list)
    provenance_class: str = "model-originated"
    topic_terms: list[str] = field(default_factory=list)
    dirty: bool = True


@dataclass
class ResearchState:
    hypotheses: dict[str, HypothesisState] = field(default_factory=dict)
    # Agent experiments in flight: id -> dict
    active_experiments: dict[str, dict[str, Any]] = field(default_factory=dict)
    measurements: dict[str, list[float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypotheses": {k: asdict(v) for k, v in self.hypotheses.items()},
            "active_experiments": self.active_experiments,
            "measurements": self.measurements,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ResearchState:
        hyps = {}
        for k, v in d.get("hypotheses", {}).items():
            v = dict(v)
            v["evidence"] = [EvidenceState(**e) for e in v.get("evidence", [])]
            v["reasoning"] = [ReasoningStepState(**r) for r in v.get("reasoning", [])]
            hyps[k] = HypothesisState(**v)
        return cls(hypotheses=hyps, active_experiments=d.get("active_experiments", {}), measurements=d.get("measurements", {}))


@dataclass
class Portal:
    child_id: str
    x: float
    y: float
    created_tick: int
    creator_id: str | None
    rule_overrides: dict[str, Any] = field(default_factory=dict)


@dataclass
class UniverseState:
    id: str
    number: int
    code: str
    name: str
    config: UniverseConfig
    seed: str
    created_at: str
    status: str = "initialising"
    tick: int = 0
    speed: float = 1.0
    parent_id: str | None = None
    depth: int = 0
    created_by_kind: str = "operator"
    created_by_id: str | None = None
    created_by_label: str = "Operator"
    created_at_tick: int = 0
    compute_share: float = 1.0
    model_ref: str | None = None
    engine_version: str = ""
    mechanics_version: int = 1
    terminated_reason: str | None = None

    grid: dict[str, np.ndarray] = field(default_factory=dict)
    agents: dict[str, AgentState] = field(default_factory=dict)
    structures: dict[str, Structure] = field(default_factory=dict)
    portals: list[Portal] = field(default_factory=list)
    child_ids: list[str] = field(default_factory=list)
    ids: LocalIdFactory | None = None
    rng: RngStreams | None = None
    civilization: CivilizationState = field(default_factory=CivilizationState)
    research: ResearchState = field(default_factory=ResearchState)

    born: int = 0
    died: int = 0
    max_generation: int = 0
    name_counter: int = 0

    # Transient outboxes drained by the runner each tick; also persisted so nothing is lost on pause.
    outbox_events: list[dict[str, Any]] = field(default_factory=list)
    outbox_memories: list[dict[str, Any]] = field(default_factory=list)
    outbox_beliefs: list[dict[str, Any]] = field(default_factory=list)
    outbox_decisions: list[dict[str, Any]] = field(default_factory=list)
    cognition_requests: list[tuple[str, str]] = field(default_factory=list)
    pending_subworlds: list[dict[str, Any]] = field(default_factory=list)
    event_counter: int = 0

    # ------------------------------------------------------------------ construction

    @classmethod
    def create(
        cls,
        *,
        id: str,
        number: int,
        code: str,
        name: str,
        config: UniverseConfig,
        created_at: str,
        engine_version: str,
        mechanics_version: int,
        parent_id: str | None = None,
        depth: int = 0,
        created_by: tuple[str, str | None, str] = ("operator", None, "Operator"),
        created_at_tick: int = 0,
        compute_share: float = 1.0,
    ) -> UniverseState:
        st = cls(
            id=id,
            number=number,
            code=code,
            name=name,
            config=config,
            seed=config.seed,
            created_at=created_at,
            parent_id=parent_id,
            depth=depth,
            created_by_kind=created_by[0],
            created_by_id=created_by[1],
            created_by_label=created_by[2],
            created_at_tick=created_at_tick,
            compute_share=compute_share,
            engine_version=engine_version,
            mechanics_version=mechanics_version,
        )
        st.ids = LocalIdFactory(universe_n=number)
        st.rng = RngStreams(config.seed)
        st.grid = terrain.generate(config)
        for spec in config.technology_tree:
            st.civilization.technologies[spec.id] = TechState(id=spec.id)
        return st

    # ------------------------------------------------------------------ grid helpers

    @property
    def cols(self) -> int:
        return self.config.cols

    @property
    def rows(self) -> int:
        return self.config.rows

    def cell_of(self, x: float, y: float) -> tuple[int, int]:
        cs = self.config.cell_size
        cx = int(min(self.cols - 1, max(0, x // cs)))
        cy = int(min(self.rows - 1, max(0, y // cs)))
        return cx, cy

    def cell_center(self, cx: int, cy: int) -> tuple[float, float]:
        cs = self.config.cell_size
        return (cx * cs + cs / 2, cy * cs + cs / 2)

    def passable(self, cx: int, cy: int) -> bool:
        c = int(self.grid["cls"][cy, cx])
        return c not in (terrain.WATER, terrain.VOID)

    def alive_agents(self) -> list[AgentState]:
        return [a for a in self.agents.values() if a.alive]

    def emit(self, severity: str, category: str, summary: str, refs: list[dict[str, str]] | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
        self.event_counter += 1
        ev = {
            "id": f"ev-{self.number:02d}-{self.event_counter:06d}",
            "universeId": self.id,
            "tick": self.tick,
            "severity": severity,
            "category": category,
            "summary": summary,
            "refs": refs,
            "data": data,
        }
        self.outbox_events.append(ev)
        return ev

    def next_name(self) -> str:
        self.name_counter += 1
        return NAMES[(self.name_counter - 1) % len(NAMES)] + ("" if self.name_counter <= len(NAMES) else f"-{(self.name_counter - 1) // len(NAMES) + 1}")

    # ------------------------------------------------------------------ serialisation

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "number": self.number,
            "code": self.code,
            "name": self.name,
            "config": self.config.model_dump(mode="json"),
            "seed": self.seed,
            "created_at": self.created_at,
            "status": self.status,
            "tick": self.tick,
            "speed": self.speed,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "created_by_kind": self.created_by_kind,
            "created_by_id": self.created_by_id,
            "created_by_label": self.created_by_label,
            "created_at_tick": self.created_at_tick,
            "compute_share": self.compute_share,
            "model_ref": self.model_ref,
            "engine_version": self.engine_version,
            "mechanics_version": self.mechanics_version,
            "terminated_reason": self.terminated_reason,
            "grid": {k: v.tolist() for k, v in self.grid.items()},
            "agents": {k: a.to_dict() for k, a in self.agents.items()},
            "structures": {k: asdict(s) for k, s in self.structures.items()},
            "portals": [asdict(p) for p in self.portals],
            "child_ids": list(self.child_ids),
            "ids": self.ids.to_dict() if self.ids else None,
            "rng": self.rng.to_dict() if self.rng else None,
            "civilization": self.civilization.to_dict(),
            "research": self.research.to_dict(),
            "born": self.born,
            "died": self.died,
            "max_generation": self.max_generation,
            "name_counter": self.name_counter,
            "event_counter": self.event_counter,
            "cognition_requests": [list(t) for t in self.cognition_requests],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UniverseState:
        config = UniverseConfig.model_validate(d["config"])
        st = cls(
            id=d["id"],
            number=d["number"],
            code=d["code"],
            name=d["name"],
            config=config,
            seed=d["seed"],
            created_at=d["created_at"],
            status=d.get("status", "paused"),
            tick=d["tick"],
            speed=d.get("speed", 1.0),
            parent_id=d.get("parent_id"),
            depth=d.get("depth", 0),
            created_by_kind=d.get("created_by_kind", "operator"),
            created_by_id=d.get("created_by_id"),
            created_by_label=d.get("created_by_label", "Operator"),
            created_at_tick=d.get("created_at_tick", 0),
            compute_share=d.get("compute_share", 1.0),
            model_ref=d.get("model_ref"),
            engine_version=d.get("engine_version", ""),
            mechanics_version=d.get("mechanics_version", 1),
            terminated_reason=d.get("terminated_reason"),
        )
        st.grid = {k: np.asarray(v, dtype=GRID_DTYPES.get(k, np.float32)) for k, v in d["grid"].items()}
        st.agents = {k: AgentState.from_dict(v) for k, v in d.get("agents", {}).items()}
        st.structures = {k: Structure(**v) for k, v in d.get("structures", {}).items()}
        st.portals = [Portal(**p) for p in d.get("portals", [])]
        st.child_ids = list(d.get("child_ids", []))
        st.ids = LocalIdFactory.from_dict(d["ids"]) if d.get("ids") else LocalIdFactory(universe_n=st.number)
        st.rng = RngStreams.from_dict(st.seed, d["rng"]) if d.get("rng") else RngStreams(st.seed)
        st.civilization = CivilizationState.from_dict(d.get("civilization", {}))
        st.research = ResearchState.from_dict(d.get("research", {}))
        st.born = d.get("born", 0)
        st.died = d.get("died", 0)
        st.max_generation = d.get("max_generation", 0)
        st.name_counter = d.get("name_counter", 0)
        st.event_counter = d.get("event_counter", 0)
        st.cognition_requests = [tuple(t) for t in d.get("cognition_requests", [])]
        for spec in config.technology_tree:
            st.civilization.technologies.setdefault(spec.id, TechState(id=spec.id))
        return st

    def state_hash_payload(self) -> dict[str, Any]:
        """Deterministic payload for hashing: excludes wall-clock fields and transient outboxes."""
        d = self.to_dict()
        for k in ("created_at", "status", "speed", "engine_version", "model_ref", "compute_share", "cognition_requests"):
            d.pop(k, None)
        return d


NAMES = [
    "Ilse", "Tove", "Brann", "Kael", "Ren", "Sae", "Hal", "Mira", "Orun", "Vel",
    "Ash", "Nia", "Dov", "Lira", "Tam", "Esk", "Rua", "Pell", "Yan", "Oda",
    "Fen", "Isa", "Kir", "Mo", "Nell", "Rook", "Sil", "Ude", "Wren", "Zia",
]
