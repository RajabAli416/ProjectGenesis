from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api import schemas as S
from app.api.deps import get_host
from app.simulation.host import SimulationHost
from app.version import ENGINE_VERSION, MECHANICS_VERSION, PROMPT_VERSION, full_version

router = APIRouter(tags=["health"])
Host = Annotated[SimulationHost, Depends(get_host)]


@router.get("/health", response_model=S.HostStatus)
def health(host: Host) -> S.HostStatus:
    return host.host_status()


@router.get("/version")
def version() -> dict[str, Any]:
    return {"engineVersion": ENGINE_VERSION, "fullVersion": full_version(), "mechanicsVersion": MECHANICS_VERSION, "promptVersion": PROMPT_VERSION}
