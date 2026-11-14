"""Deterministic, model-free providers.

`ScriptedProvider` answers from a Python callable; it exercises the full cognition path in tests and
CI without a GPU. `ReplayProvider` returns previously recorded responses by prompt hash so a run can
be reproduced exactly; it fails loudly when no recording exists."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from app.core.errors import ProviderError
from app.intelligence.providers.base import InferenceRequest, ModelInfo, ProviderResponse

Script = Callable[[InferenceRequest], dict[str, Any]]

_ACTIONS_RE = re.compile(r"AVAILABLE_ACTIONS:\s*(\[.*?\])", re.S)


def available_from_prompt(req: InferenceRequest) -> list[str]:
    for m in req.messages:
        found = _ACTIONS_RE.search(m.get("content", ""))
        if found:
            try:
                return list(json.loads(found.group(1)))
            except json.JSONDecodeError:
                return []
    return []


def default_script(req: InferenceRequest) -> dict[str, Any]:
    """Prefers eating, then gathering, then exploring. Deterministic given the prompt."""
    actions = available_from_prompt(req)
    if req.purpose == "reflection":
        return {"reflections": [{"summary": "Scripted reflection: the days repeat.", "salience": 0.3}], "beliefUpdates": []}
    for a in ("eat", "gather", "explore", "rest"):
        if a in actions:
            params = {"ticks": 10} if a == "rest" else {}
            return {"action": {"type": a, "params": params}, "rationale": f"scripted choice: {a}", "beliefUpdates": []}
    return {"action": {"type": actions[0] if actions else "rest", "params": {}}, "rationale": "scripted fallback", "beliefUpdates": []}


class ScriptedProvider:
    adapter = "scripted"

    def __init__(self, provider_id: str = "scripted", script: Script | None = None, model: str = "scripted") -> None:
        self.id = provider_id
        self.script = script or default_script
        self.model = model
        self.calls = 0

    async def close(self) -> None:
        return None

    async def health(self) -> dict[str, Any]:
        return {"reachable": True, "version": "scripted", "loaded_models": [self.model]}

    async def describe_model(self, model: str) -> ModelInfo | None:
        return ModelInfo(model=model, digest="scripted", family="scripted", parameter_size="0", quantization="none")

    async def generate(self, req: InferenceRequest) -> ProviderResponse:
        self.calls += 1
        out = self.script(req)
        text = out if isinstance(out, str) else json.dumps(out)
        return ProviderResponse(text=text, model=self.model, prompt_tokens=len(req.system) // 4 + sum(len(m["content"]) for m in req.messages) // 4, completion_tokens=len(text) // 4, timings={"wall_ms": 0.0})


class ReplayProvider:
    adapter = "replay"

    def __init__(self, lookup: Callable[[str], str | None], provider_id: str = "replay", model: str = "replay") -> None:
        self.id = provider_id
        self.lookup = lookup
        self.model = model

    async def close(self) -> None:
        return None

    async def health(self) -> dict[str, Any]:
        return {"reachable": True, "version": "replay", "loaded_models": [self.model]}

    async def describe_model(self, model: str) -> ModelInfo | None:
        return ModelInfo(model=model, digest="replay", family="replay", parameter_size=None, quantization=None)

    async def generate(self, req: InferenceRequest) -> ProviderResponse:
        text = self.lookup(req.prompt_hash())
        if text is None:
            raise ProviderError(f"no recorded response for prompt hash {req.prompt_hash()[:12]}")
        return ProviderResponse(text=text, model=self.model, timings={"wall_ms": 0.0}, replayed=True)
