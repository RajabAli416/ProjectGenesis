from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api import schemas as S
from app.api.deps import get_host
from app.simulation.host import SimulationHost

router = APIRouter(tags=["events"])
Host = Annotated[SimulationHost, Depends(get_host)]


@router.get("/events", response_model=list[S.WorldEvent])
def list_events(host: Host, limit: int = Query(100, ge=1, le=1000), since: int | None = None, universe_id: str | None = Query(None, alias="universeId")) -> list[S.WorldEvent]:
    pending = []
    for st in host.states():
        if universe_id and st.id != universe_id:
            continue
        pending.extend(st.outbox_events)
    pending.sort(key=lambda e: e["tick"], reverse=True)
    out = [S.WorldEvent(id=e["id"], universe_id=e["universeId"], tick=e["tick"], severity=e["severity"], category=e["category"], summary=e["summary"], refs=e.get("refs")) for e in pending]
    rows = host.store.list_events(universe_id, limit, since)
    out += [S.WorldEvent(id=r.id, universe_id=r.universe_id, tick=r.tick, severity=r.severity, category=r.category, summary=r.summary, refs=r.refs_json) for r in rows]  # type: ignore[arg-type]
    return out[:limit]
