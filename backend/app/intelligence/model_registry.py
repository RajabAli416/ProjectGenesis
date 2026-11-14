"""Resolves operator provider configs into Provider instances and tracks model identities
(digest, family, parameter size, quantization) so every inference row can point at an exact model."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.intelligence.providers.base import ModelInfo, Provider
from app.intelligence.providers.ollama import OllamaProvider
from app.intelligence.providers.openai_compat import OpenAICompatProvider
from app.intelligence.providers.scripted import ReplayProvider, ScriptedProvider
from app.persistence.store import Store

log = logging.getLogger(__name__)


@dataclass
class ProviderSpec:
    id: str
    label: str
    adapter: str
    base_url: str
    model: str
    enabled: bool
    credential: str | None = None


def model_ref_id(provider_id: str, model: str, digest: str | None) -> str:
    short = (digest or "nodigest").split(":")[-1][:12]
    return f"{provider_id}:{model}@{short}"


class ModelRegistry:
    def __init__(self, store: Store, keep_alive: str = "-1") -> None:
        self.store = store
        self.keep_alive = keep_alive
        self.providers: dict[str, Provider] = {}
        self.model_refs: dict[str, dict[str, Any]] = {}
        for row in store.list_model_refs():
            self.model_refs[row.id] = {"id": row.id, "provider_id": row.provider_id, "adapter": row.adapter, "model": row.model, "digest": row.digest, "family": row.family, "parameter_size": row.parameter_size, "quantization": row.quantization, "first_seen": row.first_seen}

    async def close(self) -> None:
        for p in self.providers.values():
            await p.close()
        self.providers.clear()

    def build(self, spec: ProviderSpec, replay_lookup=None) -> Provider:
        if spec.adapter == "ollama":
            return OllamaProvider(spec.id, spec.base_url, keep_alive=self.keep_alive, default_model=spec.model)
        if spec.adapter in ("openai-compatible", "anthropic-messages", "custom-http"):
            # anthropic-messages and custom-http are accepted identifiers; both are served through the
            # OpenAI-compatible adapter until dedicated adapters exist.
            return OpenAICompatProvider(spec.id, spec.base_url, credential=spec.credential, default_model=spec.model)
        if spec.adapter == "scripted":
            return ScriptedProvider(spec.id, model=spec.model or "scripted")
        if spec.adapter == "replay":
            return ReplayProvider(replay_lookup or (lambda h: None), spec.id, model=spec.model or "replay")
        raise ValueError(f"unknown adapter {spec.adapter!r}")

    async def get(self, spec: ProviderSpec, replay_lookup=None) -> Provider:
        existing = self.providers.get(spec.id)
        if existing is not None and existing.adapter == spec.adapter and getattr(existing, "base_url", None) in (None, spec.base_url.rstrip("/"), spec.base_url.rstrip("/").removesuffix("/v1")):
            return existing
        if existing is not None:
            await existing.close()
        prov = self.build(spec, replay_lookup)
        self.providers[spec.id] = prov
        return prov

    async def resolve_model_ref(self, provider: Provider, model: str) -> str | None:
        try:
            info: ModelInfo | None = await provider.describe_model(model)
        except Exception as e:  # noqa: BLE001
            log.warning("describe_model failed for %s: %s", model, e)
            return None
        if info is None:
            return None
        ref = model_ref_id(provider.id, model, info.digest)
        data = {"id": ref, "provider_id": provider.id, "adapter": provider.adapter, "model": model, "digest": info.digest, "family": info.family, "parameter_size": info.parameter_size, "quantization": info.quantization, "details_json": info.details}
        if ref not in self.model_refs:
            self.store.upsert_model_ref(data)
            row = next((r for r in self.store.list_model_refs() if r.id == ref), None)
            data["first_seen"] = row.first_seen if row else ""
            data.pop("details_json", None)
            self.model_refs[ref] = data
        return ref
