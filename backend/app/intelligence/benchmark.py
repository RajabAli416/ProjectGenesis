"""Model benchmark: sends N representative decision prompts to a provider and measures JSON validity,
schema validity and latency. Used by the API (POST /api/inference/benchmarks) and the CLI script."""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING, Any

from app.api import schemas as S
from app.core.errors import InvalidCommand, ProviderUnavailable
from app.core.timeutil import now_iso
from app.intelligence.parsing import ParseError, extract_json, parse_as
from app.intelligence.providers.base import InferenceRequest
from app.intelligence.schemas import DecisionResponse, decision_schema
from app.version import PROMPT_VERSION

if TYPE_CHECKING:
    from app.simulation.host import SimulationHost

_ACTIONS = ["move_to", "explore", "gather", "eat", "rest", "speak", "investigate", "build"]

_SYSTEM = (
    "You are an inhabitant of a small world. You have needs (energy) and a memory of what you have seen. "
    "Choose exactly one action from AVAILABLE_ACTIONS and answer only with JSON matching the schema."
)

_SCENARIOS = [
    "Tick 1200. Energy 0.31 (low). You are at (104, 72) on fertile ground. Visible: a food resource 9 units east with 0.6 abundance; agent Tola 15 units north. Inventory: food 0.\nAVAILABLE_ACTIONS: [\"move_to\", \"gather\", \"eat\", \"rest\", \"explore\", \"speak\"]",
    "Tick 3400. Energy 0.82. Hazard is rising (0.55) and you are in the open. A shelter stands 20 units south-west. Recent memory: 'Hazard peaked at tick 2400; two agents died in the open.'\nAVAILABLE_ACTIONS: [\"move_to\", \"rest\", \"explore\", \"speak\", \"investigate\", \"build\"]",
    "Tick 5100. Energy 0.66. Inventory: food 4 (near capacity). Agent Mira is 6 units away and recently told you 'the boundary to the east cannot be crossed'. You have never visited the eastern edge.\nAVAILABLE_ACTIONS: [\"move_to\", \"eat\", \"speak\", \"investigate\", \"explore\", \"trade\"]",
    "Tick 7800. Energy 0.48. You are among four others near the river. No structures exist. Group has 7 food units in total; it is getting cold.\nAVAILABLE_ACTIONS: [\"build\", \"gather\", \"speak\", \"rest\", \"move_to\"]",
    "Tick 9000. Energy 0.74. You remember: 'Plants regrow faster near water.' and 'Vel refused a trade.' Nothing of note nearby.\nAVAILABLE_ACTIONS: [\"explore\", \"investigate\", \"speak\", \"rest\", \"gather\"]",
]


async def run_benchmark(host: SimulationHost, req: S.BenchmarkRequest) -> S.BenchmarkRecord:
    spec = host._active_provider_spec(req.provider_id)  # noqa: SLF001
    if spec is None:
        raise InvalidCommand("no enabled provider to benchmark")
    provider = host.scripted_override or await host.registry.get(spec, replay_lookup=host._replay_lookup)  # noqa: SLF001
    model = req.model or spec.model
    num_ctx = req.num_ctx or host.operator.reasoning.num_ctx
    health = await provider.health()
    if not health.get("reachable"):
        raise ProviderUnavailable(health.get("error") or "provider unreachable")
    model_ref = await host.registry.resolve_model_ref(provider, model)

    schema = decision_schema(_ACTIONS)
    results: list[dict[str, Any]] = []
    n = max(1, min(50, req.requests))
    for i in range(n):
        scenario = _SCENARIOS[i % len(_SCENARIOS)]
        ireq = InferenceRequest(
            universe_id="bench",
            agent_id=None,
            tick=i,
            purpose="benchmark",
            system=_SYSTEM,
            messages=[{"role": "user", "content": scenario}],
            json_schema=schema,
            model=model,
            temperature=host.operator.reasoning.temperature,
            num_ctx=num_ctx,
            seed=1000 + i,
            think=req.think,
            timeout_s=host.operator.reasoning.timeout_s,
            prompt_version=PROMPT_VERSION,
        )
        resp = await provider.generate(ireq)
        json_ok = schema_ok = False
        try:
            extract_json(resp.text)
            json_ok = True
            parse_as(resp.text, DecisionResponse)
            schema_ok = True
        except ParseError:
            pass
        results.append({"json_ok": json_ok, "schema_ok": schema_ok, "latency_ms": resp.timings.get("wall_ms") or 0.0, "prompt_tokens": resp.prompt_tokens or 0, "completion_tokens": resp.completion_tokens or 0, "timings": resp.timings})

    lat = sorted(r["latency_ms"] for r in results)
    p50 = statistics.median(lat)
    p95 = lat[min(len(lat) - 1, int(len(lat) * 0.95))]

    def _rate(key_count: str, key_dur: str) -> float | None:
        vals = [r["timings"] for r in results if r["timings"].get(key_dur)]
        if not vals:
            return None
        toks = sum(r[key_count] for r in results if r["timings"].get(key_dur))
        secs = sum(t[key_dur] for t in vals) / 1e9
        return round(toks / secs, 1) if secs > 0 else None

    loads = [r["timings"]["load_duration"] / 1e6 for r in results if r["timings"].get("load_duration")]
    summary = {
        "json_valid_rate": round(sum(r["json_ok"] for r in results) / n, 3),
        "schema_valid_rate": round(sum(r["schema_ok"] for r in results) / n, 3),
        "latency_p50_ms": round(p50, 1),
        "latency_p95_ms": round(p95, 1),
        "prompt_tokens_mean": round(sum(r["prompt_tokens"] for r in results) / n, 1),
        "completion_tokens_mean": round(sum(r["completion_tokens"] for r in results) / n, 1),
        "prompt_eval_rate_tps": _rate("prompt_tokens", "prompt_eval_duration"),
        "eval_rate_tps": _rate("completion_tokens", "eval_duration"),
        "load_duration_ms": round(max(loads), 1) if loads else None,
    }
    notes = f"adapter={provider.adapter}; provider_version={health.get('version')}; prompt_version={PROMPT_VERSION}"
    row = {"created_at": now_iso(), "provider_id": spec.id, "model": model, "model_ref": model_ref, "num_ctx": num_ctx, "think": req.think, "requests": n, "results_json": summary, "notes": notes}
    bid = host.store.insert_benchmark(row)
    return S.BenchmarkRecord(id=bid, **{k: v for k, v in row.items() if k != "results_json"}, **summary)
