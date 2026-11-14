"""Contract test: every field the frontend's domain types declare must be present (camelCase) on
the corresponding backend DTO. Additive backend fields are allowed; missing ones are not."""

from __future__ import annotations

import re

import pytest

from app.api import schemas as S
from tests.conftest import REPO_ROOT

TYPES_TS = REPO_ROOT / "frontend" / "src" / "domain" / "types.ts"

PAIRS = {
    "SimulationClock": S.SimulationClock,
    "UniverseLineage": S.UniverseLineage,
    "WorldConditions": S.WorldConditions,
    "PopulationStats": S.PopulationStats,
    "Universe": S.Universe,
    "AgentRelationship": S.AgentRelationship,
    "KnowledgeItem": S.KnowledgeItem,
    "MemoryRecord": S.MemoryRecord,
    "Agent": S.Agent,
    "PopulationEra": S.PopulationEra,
    "Technology": S.Technology,
    "Institution": S.Institution,
    "Infrastructure": S.Infrastructure,
    "Civilization": S.Civilization,
    "Evidence": S.Evidence,
    "ReasoningStep": S.ReasoningStep,
    "Hypothesis": S.Hypothesis,
    "ExperimentVariable": S.ExperimentVariable,
    "ExperimentRun": S.ExperimentRun,
    "Experiment": S.Experiment,
    "WorldEvent": S.WorldEvent,
    "ProviderConfig": S.ProviderConfig,
    "ReasoningConfig": S.ReasoningConfig,
    "SimulationParams": S.SimulationParams,
    "PerformanceConfig": S.PerformanceConfig,
    "PersistenceConfig": S.PersistenceConfig,
    "OperatorSettings": S.OperatorSettings,
}

_IFACE_RE = re.compile(r"export interface (\w+)\s*\{(.*?)\n\}", re.S)
_FIELD_RE = re.compile(r"^\s*(\w+)\??:\s", re.M)


def ts_interfaces() -> dict[str, set[str]]:
    src = TYPES_TS.read_text(encoding="utf-8")
    out: dict[str, set[str]] = {}
    for name, body in _IFACE_RE.findall(src):
        # Top-level fields only: strip nested object literals before matching field names.
        depth = 0
        flat = []
        for ch in body:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            elif depth == 0:
                flat.append(ch)
        out[name] = set(_FIELD_RE.findall("".join(flat)))
    return out


def dto_aliases(model: type[S.DTO]) -> set[str]:
    return {f.alias or n for n, f in model.model_fields.items()}


@pytest.mark.parametrize("ts_name", sorted(PAIRS))
def test_dto_covers_ts_interface(ts_name: str) -> None:
    ifaces = ts_interfaces()
    assert ts_name in ifaces, f"{ts_name} missing from types.ts"
    missing = ifaces[ts_name] - dto_aliases(PAIRS[ts_name])
    assert not missing, f"{ts_name}: backend DTO lacks {sorted(missing)}"


def test_dtos_serialise_camel_case() -> None:
    clock = S.SimulationClock(tick=1, rate=24.0, speed=1.0, observed_at="2026-01-01T00:00:00Z")
    assert clock.model_dump(by_alias=True) == {"tick": 1, "rate": 24.0, "speed": 1.0, "observedAt": "2026-01-01T00:00:00Z"}


def test_ws_message_types_match_frontend() -> None:
    ws_ts = (REPO_ROOT / "frontend" / "src" / "api" / "ws.ts").read_text(encoding="utf-8")
    for t in ("hello", "clock", "snapshot", "event", "universe.changed"):
        assert f"'{t}'" in ws_ts
