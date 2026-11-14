from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api import schemas as S
from app.api.deps import get_host
from app.simulation.host import SimulationHost

router = APIRouter(prefix="/settings", tags=["settings"])
Host = Annotated[SimulationHost, Depends(get_host)]


@router.get("", response_model=S.OperatorSettings)
def get_settings(host: Host) -> S.OperatorSettings:
    return host.operator


@router.put("", response_model=S.OperatorSettings)
async def put_settings(settings: S.OperatorSettings, host: Host) -> S.OperatorSettings:
    if settings.reasoning.provider_id and not any(p.id == settings.reasoning.provider_id for p in settings.providers):
        raise HTTPException(422, "reasoning.providerId does not match any provider")
    return await host.apply_settings(settings)


@router.put("/providers/{provider_id}/credential", response_model=S.OperatorSettings)
def set_credential(provider_id: str, req: S.CredentialRequest, host: Host) -> S.OperatorSettings:
    if not host.set_credential(provider_id, req.credential):
        raise HTTPException(404, f"Provider {provider_id} not found (apply settings first)")
    return host.operator
