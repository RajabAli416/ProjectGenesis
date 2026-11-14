from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api import schemas as S
from app.api.deps import get_host
from app.core.errors import InvalidCommand, NotFound
from app.simulation.host import SimulationHost

router = APIRouter(prefix="/experiments", tags=["experiments"])
Host = Annotated[SimulationHost, Depends(get_host)]


def _engine(host: SimulationHost):
    assert host.experiments is not None
    return host.experiments


@router.get("", response_model=list[S.Experiment])
def list_experiments(host: Host) -> list[S.Experiment]:
    return [e.dto() for e in _engine(host).list()]


@router.post("", response_model=S.Experiment, status_code=201)
def create_experiment(req: S.CreateExperimentRequest, host: Host) -> S.Experiment:
    return _engine(host).create(req).dto()


@router.get("/{exp_id}", response_model=S.Experiment)
def get_experiment(exp_id: str, host: Host) -> S.Experiment:
    try:
        return _engine(host).get(exp_id).dto()
    except NotFound as e:
        raise HTTPException(404, f"Experiment {exp_id} not found") from e


@router.patch("/{exp_id}", response_model=S.Experiment)
def patch_experiment(exp_id: str, req: S.PatchExperimentRequest, host: Host) -> S.Experiment:
    try:
        return _engine(host).patch(exp_id, req).dto()
    except NotFound as e:
        raise HTTPException(404, f"Experiment {exp_id} not found") from e
    except InvalidCommand as e:
        raise HTTPException(409, str(e)) from e


@router.delete("/{exp_id}", status_code=204)
def delete_experiment(exp_id: str, host: Host) -> None:
    try:
        _engine(host).delete(exp_id)
    except NotFound as e:
        raise HTTPException(404, f"Experiment {exp_id} not found") from e
    except InvalidCommand as e:
        raise HTTPException(409, str(e)) from e


@router.post("/{exp_id}/runs", response_model=S.Experiment)
async def start_run(exp_id: str, host: Host) -> S.Experiment:
    try:
        return (await _engine(host).start_run(exp_id)).dto()
    except NotFound as e:
        raise HTTPException(404, f"Experiment {exp_id} not found") from e
    except InvalidCommand as e:
        raise HTTPException(409, str(e)) from e


@router.post("/{exp_id}/abort", response_model=S.Experiment)
async def abort(exp_id: str, host: Host) -> S.Experiment:
    try:
        return (await _engine(host).abort(exp_id)).dto()
    except NotFound as e:
        raise HTTPException(404, f"Experiment {exp_id} not found") from e
