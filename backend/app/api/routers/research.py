from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api import schemas as S
from app.api.deps import get_host
from app.core.errors import NotFound
from app.research.engine import hypothesis_dto, propose_hypothesis
from app.simulation.host import SimulationHost

router = APIRouter(prefix="/research", tags=["research"])
Host = Annotated[SimulationHost, Depends(get_host)]


@router.get("/hypotheses", response_model=list[S.Hypothesis])
def list_hypotheses(host: Host, universe_id: str | None = None) -> list[S.Hypothesis]:
    out: list[S.Hypothesis] = []
    for st in sorted(host.states(), key=lambda s: s.number):
        if universe_id and st.id != universe_id:
            continue
        out.extend(hypothesis_dto(st, h) for h in st.research.hypotheses.values())
    return out


@router.get("/hypotheses/{hid}", response_model=S.Hypothesis)
def get_hypothesis(hid: str, host: Host) -> S.Hypothesis:
    for st in host.states():
        h = st.research.hypotheses.get(hid)
        if h is not None:
            return hypothesis_dto(st, h)
    raise HTTPException(404, f"Hypothesis {hid} not found")


@router.post("/hypotheses", response_model=S.Hypothesis, status_code=201)
def create_hypothesis(req: S.CreateHypothesisRequest, host: Host) -> S.Hypothesis:
    try:
        st = host.get(req.universe_id)
    except NotFound as e:
        raise HTTPException(404, f"Universe {req.universe_id} not found") from e
    h = propose_hypothesis(st, None, req.title, req.statement, req.confidence, label="Operator", experiment_ids=req.experiment_ids)
    if h is None:
        raise HTTPException(422, "title and statement are required")
    return hypothesis_dto(st, h)


@router.post("/hypotheses/{hid}/withdraw", response_model=S.Hypothesis)
def withdraw(hid: str, host: Host) -> S.Hypothesis:
    for st in host.states():
        h = st.research.hypotheses.get(hid)
        if h is not None:
            h.state = "withdrawn"
            st.emit("info", "research", f"Hypothesis {hid.upper()} withdrawn by operator.", [{"kind": "hypothesis", "id": hid}])
            return hypothesis_dto(st, h)
    raise HTTPException(404, f"Hypothesis {hid} not found")
