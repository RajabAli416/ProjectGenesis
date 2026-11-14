"""Ollama native API adapter (/api/chat). Uses the native endpoint rather than the OpenAI shim so
that `format` (JSON schema), `options.num_ctx`, `keep_alive` and `think` are all controllable."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.core.errors import ProviderError, ProviderUnavailable
from app.intelligence.providers.base import InferenceRequest, ModelInfo, ProviderResponse

log = logging.getLogger(__name__)

MIN_VERSION_FOR_QWEN3 = (0, 6, 6)
MIN_VERSION_FOR_THINK = (0, 9, 0)


def parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in v.split("-", maxsplit=1)[0].split("."))
    except ValueError:
        return (0,)


class OllamaProvider:
    adapter = "ollama"

    def __init__(self, provider_id: str, base_url: str, keep_alive: str = "-1", default_model: str = "") -> None:
        self.id = provider_id
        self.base_url = base_url.rstrip("/")
        if self.base_url.endswith("/v1"):
            self.base_url = self.base_url[:-3]
        self.keep_alive: str | int = keep_alive
        self.default_model = default_model
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(10.0, read=600.0))
        self.version: str | None = None
        self.supports_think: bool | None = None

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        try:
            r = await self._client.get("/api/version", timeout=3.0)
            r.raise_for_status()
            self.version = r.json().get("version")
            self.supports_think = parse_version(self.version or "0") >= MIN_VERSION_FOR_THINK
            loaded: list[str] = []
            try:
                ps = await self._client.get("/api/ps", timeout=3.0)
                if ps.status_code == 200:
                    loaded = [m.get("name") or m.get("model") for m in ps.json().get("models", [])]
            except httpx.HTTPError:
                pass
            return {"reachable": True, "version": self.version, "loaded_models": loaded, "supports_think": self.supports_think}
        except (httpx.HTTPError, ValueError) as e:
            return {"reachable": False, "version": None, "loaded_models": [], "error": str(e)}

    async def list_models(self) -> list[dict[str, Any]]:
        r = await self._client.get("/api/tags", timeout=5.0)
        r.raise_for_status()
        return r.json().get("models", [])

    async def describe_model(self, model: str) -> ModelInfo | None:
        try:
            digest = None
            for m in await self.list_models():
                if m.get("name") == model or m.get("model") == model:
                    digest = m.get("digest")
                    break
            r = await self._client.post("/api/show", json={"model": model}, timeout=10.0)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data = r.json()
            det = data.get("details", {})
            return ModelInfo(model=model, digest=digest, family=det.get("family"), parameter_size=det.get("parameter_size"), quantization=det.get("quantization_level"), details={"modelfile_hash": None, "parameters": data.get("parameters"), "template_present": bool(data.get("template"))})
        except httpx.HTTPError as e:
            raise ProviderUnavailable(str(e)) from e

    async def generate(self, req: InferenceRequest) -> ProviderResponse:
        payload: dict[str, Any] = {
            "model": req.model or self.default_model,
            "messages": [{"role": "system", "content": req.system}] + req.messages,
            "stream": False,
            "format": req.json_schema,
            "options": req.options(),
            "keep_alive": _keep_alive(self.keep_alive),
        }
        if req.think is not None and (self.supports_think is None or self.supports_think):
            payload["think"] = req.think
        started = time.perf_counter()
        try:
            r = await self._client.post("/api/chat", json=payload, timeout=httpx.Timeout(10.0, read=req.timeout_s))
        except httpx.TimeoutException as e:
            raise TimeoutError(str(e)) from e
        except httpx.HTTPError as e:
            raise ProviderUnavailable(str(e)) from e
        if r.status_code >= 400:
            detail = r.text[:400]
            if "think" in detail and "think" in payload:
                # Older server: retry once without the think flag and remember.
                self.supports_think = False
                payload.pop("think", None)
                r = await self._client.post("/api/chat", json=payload, timeout=httpx.Timeout(10.0, read=req.timeout_s))
                if r.status_code >= 400:
                    raise ProviderError(f"ollama {r.status_code}: {r.text[:400]}")
            else:
                raise ProviderError(f"ollama {r.status_code}: {detail}")
        data = r.json()
        msg = data.get("message", {})
        text = msg.get("content", "") or ""
        timings = {k: data.get(k) for k in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration") if k in data}
        timings["wall_ms"] = round((time.perf_counter() - started) * 1000, 1)
        if msg.get("thinking"):
            timings["thinking_chars"] = len(msg["thinking"])
        return ProviderResponse(text=text, model=data.get("model", payload["model"]), prompt_tokens=data.get("prompt_eval_count"), completion_tokens=data.get("eval_count"), timings=timings, raw={k: v for k, v in data.items() if k != "message"})


def _keep_alive(v: str | int) -> str | int:
    if isinstance(v, int):
        return v
    try:
        return int(v)
    except ValueError:
        return v
