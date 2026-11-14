"""Immutable, versioned universe configuration. Every number that affects mechanics lives here so
that experiments can vary it by dot-path (e.g. ``rules.energy_decay``) and so that it is recorded
with each universe for reproducibility."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CONFIG_VERSION = 1


class TechnologySpec(BaseModel):
    id: str
    name: str
    tier: int
    requires: list[str] = Field(default_factory=list)
    # Investigation effort (progress units) needed before a tech becomes 'emerging'.
    effort: float = 60.0
    # Number of distinct holders needed before 'established'.
    establish_holders: int = 2


DEFAULT_TECH_TREE: list[TechnologySpec] = [
    TechnologySpec(id="fire", name="Controlled fire", tier=1, effort=40),
    TechnologySpec(id="tools", name="Shaped tools", tier=1, effort=50),
    TechnologySpec(id="storage", name="Grain storage", tier=2, requires=["tools"], effort=80),
    TechnologySpec(id="clay", name="Clay firing", tier=2, requires=["fire"], effort=80),
    TechnologySpec(id="irrigation", name="Irrigation", tier=3, requires=["storage", "tools"], effort=120),
    TechnologySpec(id="record", name="Record keeping", tier=3, requires=["clay"], effort=120),
    TechnologySpec(id="subworld", name="Sub-world instantiation", tier=4, requires=["record"], effort=200, establish_holders=1),
    TechnologySpec(id="metal", name="Metallurgy", tier=4, requires=["clay", "fire"], effort=200),
]


class UniverseRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # metabolism
    energy_decay: float = 0.002
    hazard_decay_multiplier: float = 2.0
    rest_decay_factor: float = 0.5
    shelter_hazard_factor: float = 0.3
    dormant_threshold: float = 0.2
    wake_threshold: float = 0.35
    max_age: int = 8_000  # ticks; mortality probability ramps after this. 0 disables ageing death.

    # movement and perception
    move_speed: float = 1.0  # world units per tick
    perception_radius: float = 24.0  # world units
    edge_mode: Literal["clamp", "wrap"] = "clamp"
    edge_signal: bool = True  # whether an agent perceives that a move was blocked by the edge

    # resources
    gather_rate: float = 0.04
    eat_rate: float = 0.15
    food_energy: float = 0.45
    inventory_cap: float = 3.0
    resource_regen: float = 0.0012
    resource_cap: float = 1.0
    initial_resource: float = 0.6

    # terrain
    water_level: float = 0.26
    void_level: float = 0.86
    fertility_threshold: float = 0.26
    base_fertility: float = 0.54
    base_hazard: float = 0.12
    hazard_amplitude: float = 0.6
    hazard_period: int = 2_400
    temperature: float = 0.5

    # reproduction
    reproduction_threshold: float = 0.7
    reproduction_cost: float = 0.3
    reproduction_cooldown: int = 600
    maturity_age: int = 400
    mutation_rate: float = 0.015
    max_population: int = 200
    reflex_reproduction_probability: float = 0.02

    # construction
    build_cost_food: float = 1.0
    structure_decay: float = 0.0002
    structure_shelter_radius: float = 6.0

    # social
    speak_radius: float = 12.0
    affinity_gain: float = 0.05
    affinity_loss: float = 0.1

    # research
    investigate_rate: float = 1.0
    research_interval: int = 300

    # civilization bookkeeping
    civilization_interval: int = 200

    # recursion
    subworld_cost_food: float = 3.0
    subworld_cost_energy: float = 0.3
    subworld_size_factor: float = 0.5
    subworld_population: int = 3
    subworld_compute_share: float = 0.3
    max_recursion_depth: int = 3


class ReasoningParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    provider_id: str | None = None  # None -> operator default provider
    model: str | None = None  # None -> provider's model
    temperature: float | None = None
    num_ctx: int | None = None
    think_decisions: bool | None = None
    think_reflection: bool | None = None
    prompt_profile: str = "neutral"
    memory_window: int = 24
    reflection_interval: int = 400
    decision_interval: int = 120
    min_decision_gap: int = 20
    need_threshold: float = 0.35


class UniverseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config_version: int = CONFIG_VERSION
    width: int = 256
    height: int = 160
    cell_size: int = 8
    seed: str = "00000000"
    initial_population: int = 5
    tick_rate: int = 24
    mode: Literal["realtime", "lockstep"] = "realtime"
    rules: UniverseRules = Field(default_factory=UniverseRules)
    reasoning: ReasoningParams = Field(default_factory=ReasoningParams)
    technology_tree: list[TechnologySpec] = Field(default_factory=lambda: [t.model_copy() for t in DEFAULT_TECH_TREE])

    @property
    def cols(self) -> int:
        return max(1, self.width // self.cell_size)

    @property
    def rows(self) -> int:
        return max(1, self.height // self.cell_size)


def set_path(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = data
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value


def get_path(data: dict[str, Any], path: str, default: Any = None) -> Any:
    cur: Any = data
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def build_config(base: dict[str, Any] | None = None, overrides: dict[str, Any] | None = None) -> UniverseConfig:
    """Create a validated config from a base dict plus dot-path or nested overrides."""
    data: dict[str, Any] = dict(base or {})
    for k, v in (overrides or {}).items():
        if "." in k:
            set_path(data, k, v)
        elif isinstance(v, dict) and isinstance(data.get(k), dict):
            merged = dict(data[k])
            merged.update(v)
            data[k] = merged
        else:
            data[k] = v
    return UniverseConfig.model_validate(data)
