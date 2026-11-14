from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api import schemas as S
from app.api.deps import get_host
from app.simulation.host import SimulationHost

router = APIRouter(prefix="/inference", tags=["inference"])
Host = Annotated[SimulationHost, Depends(get_host)]


@router.get("/status", response_model=S.InferenceStatus)
async def status(host: Host, refresh: bool = False) -> S.InferenceStatus:
    if refresh:
        await host.refresh_provider(health_only=True)
    return host.inference_status()


@router.get("/models", response_model=list[S.ModelRef])
def models(host: Host) -> list[S.ModelRef]:
    return [S.ModelRef(**{k: r.get(k) for k in ("id", "provider_id", "adapter", "model", "digest", "family", "parameter_size", "quantization", "first_seen")}) for r in host.registry.model_refs.values()]


@router.get("/available")
async def available_models(host: Host) -> list[dict[str, Any]]:
    """Models the active provider can serve (Ollama: /api/tags)."""
    prov = host.inference.provider
    if prov is None:
        return []
    lister = getattr(prov, "list_models", None)
    if lister is None:
        return []
    try:
        models = await lister()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"provider error: {e}") from e
    return [{"name": m.get("name"), "size": m.get("size"), "digest": m.get("digest"), "details": m.get("details")} for m in models]


@router.get("/requests", response_model=list[S.InferenceRequestRecord])
def requests(host: Host, limit: int = Query(50, ge=1, le=500), universe_id: str | None = Query(None, alias="universeId"), agent_id: str | None = Query(None, alias="agentId")) -> list[S.InferenceRequestRecord]:
    rows = host.store.list_inference_requests(universe_id, agent_id, limit)
    return [_req_dto(r) for r in rows]


@router.get("/requests/{request_id}", response_model=S.InferenceRequestRecord)
def request_detail(request_id: int, host: Host) -> S.InferenceRequestRecord:
    r = host.store.get_inference_request(request_id)
    if r is None:
        raise HTTPException(404, "request not found")
    return _req_dto(r)


def _req_dto(r) -> S.InferenceRequestRecord:  # noqa: ANN001
    return S.InferenceRequestRecord(
        id=r.id,
        universe_id=r.universe_id,
        agent_id=r.agent_id,
        tick=r.tick,
        purpose=r.purpose,
        model_ref=r.model_ref,
        prompt_hash=r.prompt_hash,
        system_prompt=r.system_prompt,
        messages=r.messages_json,
        options=r.options_json,
        seed=r.seed,
        status=r.status,
        attempt=r.attempt,
        raw_response=r.raw_response,
        parsed=r.parsed_json,
        valid=r.valid,
        validation_error=r.validation_error,
        prompt_tokens=r.prompt_tokens,
        completion_tokens=r.completion_tokens,
        latency_ms=r.latency_ms,
        created_at=r.created_at,
    )


@router.get("/decisions", response_model=list[S.DecisionRecord])
def decisions(host: Host, limit: int = Query(100, ge=1, le=1000), universe_id: str | None = Query(None, alias="universeId"), policy: str | None = None) -> list[S.DecisionRecord]:
    from app.api.routers.agents import _decision_dto  # noqa: PLC0415

    return [_decision_dto(d, r) for d, r in host.store.list_decisions(universe_id=universe_id, limit=limit, policy=policy)]


@router.get("/benchmarks", response_model=list[S.BenchmarkRecord])
def benchmarks(host: Host, limit: int = Query(50, ge=1, le=200)) -> list[S.BenchmarkRecord]:
    out = []
    for r in host.store.list_benchmarks(limit):
        res = r.results_json
        out.append(S.BenchmarkRecord(id=r.id, created_at=r.created_at, provider_id=r.provider_id, model=r.model, model_ref=r.model_ref, num_ctx=r.num_ctx, think=r.think, requests=r.requests, notes=r.notes, **{k: res.get(k) for k in ("json_valid_rate", "schema_valid_rate", "latency_p50_ms", "latency_p95_ms", "prompt_tokens_mean", "completion_tokens_mean", "prompt_eval_rate_tps", "eval_rate_tps", "load_duration_ms")}))
    return out


@router.post("/benchmarks", response_model=S.BenchmarkRecord)
async def run_benchmark(req: S.BenchmarkRequest, host: Host) -> S.BenchmarkRecord:
    from app.intelligence.benchmark import run_benchmark as _run  # noqa: PLC0415

    try:
        return await _run(host, req)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"benchmark failed: {e}") from e
