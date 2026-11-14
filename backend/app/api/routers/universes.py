from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api import schemas as S
from app.api.deps import get_host
from app.civilization.engine import civilization_dto
from app.core.errors import NotFound
from app.simulation.host import SimulationHost
from app.simulation.snapshot import world_snapshot

router = APIRouter(prefix="/universes", tags=["universes"])
Host = Annotated[SimulationHost, Depends(get_host)]


def _state(host: SimulationHost, uid: str):
    try:
        return host.get(uid)
    except NotFound as e:
        raise HTTPException(404, f"Universe {uid} not found") from e


@router.get("", response_model=list[S.Universe])
def list_universes(host: Host) -> list[S.Universe]:
    return [host.universe_dto(s) for s in sorted(host.states(), key=lambda s: s.number)]


@router.post("", response_model=S.Universe, status_code=201)
async def create_universe(req: S.CreateUniverseRequest, host: Host) -> S.Universe:
    try:
        state = await host.create_universe(req)
    except Exception as e:  # noqa: BLE001 - configuration validation errors
        raise HTTPException(422, str(e)) from e
    return host.universe_dto(state)


@router.get("/{uid}", response_model=S.Universe)
def get_universe(uid: str, host: Host) -> S.Universe:
    return host.universe_dto(_state(host, uid))


@router.get("/{uid}/snapshot", response_model=S.WorldSnapshot)
def get_snapshot(uid: str, host: Host) -> S.WorldSnapshot:
    state = _state(host, uid)
    if state.status == "initialising":
        raise HTTPException(404, "No snapshot has been published yet")
    return world_snapshot(state)


@router.get("/{uid}/agents", response_model=list[S.Agent])
def list_universe_agents(uid: str, host: Host, memory: int = Query(24, ge=0, le=500)) -> list[S.Agent]:
    state = _state(host, uid)
    return [host.agent_dto(state, aid, memory) for aid in sorted(state.agents)]


@router.get("/{uid}/civilization", response_model=S.Civilization)
def get_civilization(uid: str, host: Host) -> S.Civilization:
    return civilization_dto(_state(host, uid))


@router.get("/{uid}/events", response_model=list[S.WorldEvent])
def list_universe_events(uid: str, host: Host, limit: int = Query(100, ge=1, le=1000), since: int | None = None) -> list[S.WorldEvent]:
    state = _state(host, uid)
    rows = host.store.list_events(state.id, limit, since)
    pending = [e for e in state.outbox_events if e["universeId"] == state.id]
    out = [S.WorldEvent(id=e["id"], universe_id=e["universeId"], tick=e["tick"], severity=e["severity"], category=e["category"], summary=e["summary"], refs=e.get("refs")) for e in reversed(pending)]
    out += [S.WorldEvent(id=r.id, universe_id=r.universe_id, tick=r.tick, severity=r.severity, category=r.category, summary=r.summary, refs=r.refs_json) for r in rows]  # type: ignore[arg-type]
    return out[:limit]


@router.post("/{uid}/command", response_model=S.CommandResult)
async def command(uid: str, cmd: dict[str, Any], host: Host) -> S.CommandResult:
    return await host.command(uid, cmd)


@router.post("/{uid}/archive", response_model=S.Universe)
async def archive(uid: str, host: Host) -> S.Universe:
    _state(host, uid)
    return host.universe_dto(await host.archive(uid))


@router.get("/{uid}/config")
def get_config(uid: str, host: Host) -> dict[str, Any]:
    state = _state(host, uid)
    return {"config": state.config.model_dump(mode="json"), "stateHash": host.state_hash(uid), "engineVersion": state.engine_version, "mechanicsVersion": state.mechanics_version}


@router.get("/{uid}/snapshots")
def list_snapshots(uid: str, host: Host) -> list[dict[str, Any]]:
    _state(host, uid)
    return [{"id": r.id, "tick": r.tick, "createdAt": r.created_at, "sha256": r.sha256, "sizeBytes": r.size_bytes, "engineVersion": r.engine_version} for r in host.store.list_snapshots(uid)]


@router.get("/{uid}/hypotheses", response_model=list[S.Hypothesis])
def universe_hypotheses(uid: str, host: Host) -> list[S.Hypothesis]:
    from app.research.engine import hypothesis_dto  # noqa: PLC0415

    state = _state(host, uid)
    return [hypothesis_dto(state, h) for h in state.research.hypotheses.values()]
