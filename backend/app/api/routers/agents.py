from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api import schemas as S
from app.api.deps import get_host
from app.simulation.host import SimulationHost

router = APIRouter(tags=["agents"])
Host = Annotated[SimulationHost, Depends(get_host)]


def _find(host: SimulationHost, agent_id: str):
    found = host.find_agent(agent_id)
    if found is None:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return found


@router.get("/agents", response_model=list[S.Agent])
def list_agents(host: Host, memory: int = Query(24, ge=0, le=500), universe_id: str | None = Query(None, alias="universeId")) -> list[S.Agent]:
    out: list[S.Agent] = []
    for state in sorted(host.states(), key=lambda s: s.number):
        if universe_id and state.id != universe_id:
            continue
        out.extend(host.agent_dto(state, aid, memory) for aid in sorted(state.agents))
    return out


@router.get("/agents/{agent_id}", response_model=S.Agent)
def get_agent(agent_id: str, host: Host, memory: int = Query(48, ge=0, le=1000)) -> S.Agent:
    state, _ = _find(host, agent_id)
    return host.agent_dto(state, agent_id, memory)


@router.get("/agents/{agent_id}/memory", response_model=list[S.MemoryRecord])
def agent_memory(agent_id: str, host: Host, limit: int = Query(200, ge=1, le=2000), before: int | None = None) -> list[S.MemoryRecord]:
    state, agent = _find(host, agent_id)
    mems = [m for m in agent.memories if before is None or m.tick < before]
    live = [S.MemoryRecord(id=m.id, tick=m.tick, kind=m.kind, summary=m.summary, salience=round(m.salience, 3), source=m.source) for m in reversed(mems)]  # type: ignore[arg-type]
    if len(live) >= limit:
        return live[:limit]
    seen = {m.id for m in live}
    rows = host.store.list_memories(agent_id, limit, before)
    live += [S.MemoryRecord(id=r.id, tick=r.tick, kind=r.kind, summary=r.summary, salience=round(r.salience, 3), source=r.source) for r in rows if r.id not in seen]  # type: ignore[arg-type]
    return live[:limit]


@router.get("/agents/{agent_id}/decisions", response_model=list[S.DecisionRecord])
def agent_decisions(agent_id: str, host: Host, limit: int = Query(50, ge=1, le=500), policy: str | None = None) -> list[S.DecisionRecord]:
    _find(host, agent_id)
    rows = host.store.list_decisions(agent_id=agent_id, limit=limit, policy=policy)
    return [_decision_dto(d, r) for d, r in rows]


def _decision_dto(d, r) -> S.DecisionRecord:  # noqa: ANN001
    return S.DecisionRecord(
        id=d.id,
        agent_id=d.agent_id,
        universe_id=d.universe_id,
        tick_requested=d.tick_requested,
        tick_applied=d.tick_applied,
        policy=d.policy,
        purpose=d.purpose,
        action=d.action_json,
        accepted=d.accepted,
        rejection_reason=d.rejection_reason,
        rationale=d.rationale,
        request_id=d.request_id,
        model_ref=d.model_ref,
        latency_ms=r.latency_ms if r else None,
        valid=r.valid if r else None,
        prompt_tokens=r.prompt_tokens if r else None,
        completion_tokens=r.completion_tokens if r else None,
        created_at=d.created_at,
    )
