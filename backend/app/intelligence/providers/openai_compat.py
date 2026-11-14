"""OpenAI-compatible chat completions adapter (works with vLLM, llama.cpp server, LM Studio, remote
APIs). JSON mode only; schema enforcement is done by our validator."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.errors import ProviderError, ProviderUnavailable
from app.intelligence.providers.base import InferenceRequest, ModelInfo, ProviderResponse


class OpenAICompatProvider:
    adapter = "openai-compatible"

    def __init__(self, provider_id: str, base_url: str, credential: str | None = None, default_model: str = "") -> None:
        self.id = provider_id
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        headers = {"Authorization": f"Bearer {credential}"} if credential else {}
        self._client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=httpx.Timeout(10.0, read=600.0))

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        try:
            r = await self._client.get("/models", timeout=5.0)
            return {"reachable": r.status_code < 500, "version": None, "loaded_models": [m.get("id") for m in r.json().get("data", [])] if r.status_code == 200 else []}
        except (httpx.HTTPError, ValueError) as e:
            return {"reachable": False, "version": None, "loaded_models": [], "error": str(e)}

    async def describe_model(self, model: str) -> ModelInfo | None:
        return ModelInfo(model=model, digest=None, family=None, parameter_size=None, quantization=None)

    async def generate(self, req: InferenceRequest) -> ProviderResponse:
        payload: dict[str, Any] = {
            "model": req.model or self.default_model,
            "messages": [{"role": "system", "content": req.system}] + req.messages,
            "temperature": req.temperature,
            "max_tokens": req.num_predict,
            "response_format": {"type": "json_object"},
        }
        if req.seed is not None:
            payload["seed"] = req.seed
        started = time.perf_counter()
        try:
            r = await self._client.post("/chat/completions", json=payload, timeout=httpx.Timeout(10.0, read=req.timeout_s))
        except httpx.TimeoutException as e:
            raise TimeoutError(str(e)) from e
        except httpx.HTTPError as e:
            raise ProviderUnavailable(str(e)) from e
        if r.status_code >= 400:
            raise ProviderError(f"openai-compatible {r.status_code}: {r.text[:400]}")
        data = r.json()
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content", "") or ""
        usage = data.get("usage") or {}
        return ProviderResponse(text=text, model=data.get("model", payload["model"]), prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"), timings={"wall_ms": round((time.perf_counter() - started) * 1000, 1)}, raw={"id": data.get("id")})
