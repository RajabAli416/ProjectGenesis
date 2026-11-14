"""Provider-independent inference interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.hashing import canonical_json, hash_obj, neutralise_ids, sha256_hex


@dataclass
class InferenceRequest:
    universe_id: str
    agent_id: str | None
    tick: int
    purpose: str  # decision | reflection | benchmark
    system: str
    messages: list[dict[str, str]]
    json_schema: dict[str, Any]
    model: str
    temperature: float = 0.7
    num_ctx: int = 4096
    num_predict: int = 400
    seed: int | None = None
    think: bool | None = None
    priority: int = 5  # lower is more urgent
    timeout_s: float = 120.0
    prompt_profile: str = "neutral"
    prompt_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def prompt_hash(self) -> str:
        """Content hash used for replay lookups. Universe-number segments of local ids are
        neutralised so a recording made in u-0001 replays in a same-seed u-0002."""
        payload = canonical_json({"system": self.system, "messages": self.messages, "schema": self.json_schema, "model": self.model, "temperature": self.temperature, "seed": self.seed, "think": self.think})
        return sha256_hex(neutralise_ids(payload))

    def schema_hash(self) -> str:
        return hash_obj(self.json_schema)

    def options(self) -> dict[str, Any]:
        opts: dict[str, Any] = {"temperature": self.temperature, "num_ctx": self.num_ctx, "num_predict": self.num_predict}
        if self.seed is not None:
            opts["seed"] = self.seed
        return opts


@dataclass
class ProviderResponse:
    text: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    timings: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] | None = None
    replayed: bool = False


@dataclass
class ModelInfo:
    model: str
    digest: str | None
    family: str | None
    parameter_size: str | None
    quantization: str | None
    details: dict[str, Any] = field(default_factory=dict)


class Provider(Protocol):
    id: str
    adapter: str

    async def generate(self, req: InferenceRequest) -> ProviderResponse: ...

    async def health(self) -> dict[str, Any]: ...

    async def describe_model(self, model: str) -> ModelInfo | None: ...

    async def close(self) -> None: ...
