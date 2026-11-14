"""SQLAlchemy ORM models. The authoritative state of a running universe lives in memory; these
tables hold (a) append-only logs that must survive restarts and support analysis, (b) compressed
snapshots used for restore, and (c) small operator-owned records (settings, providers, experiments).
Per-agent memory/belief/decision rows are kept so that analysis never needs to decompress snapshots."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CounterRow(Base):
    __tablename__ = "counters"
    name: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)


class UniverseRow(Base):
    __tablename__ = "universes"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    code: Mapped[str] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16))
    parent_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    created_by_kind: Mapped[str] = mapped_column(String(16))
    created_by_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by_label: Mapped[str] = mapped_column(String(128))
    created_at_tick: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(32))
    seed: Mapped[str] = mapped_column(String(16))
    config_json: Mapped[dict] = mapped_column(JSON)
    config_version: Mapped[int] = mapped_column(Integer, default=1)
    tick: Mapped[int] = mapped_column(Integer, default=0)
    speed: Mapped[float] = mapped_column(Float, default=1.0)
    mode: Mapped[str] = mapped_column(String(16), default="realtime")
    engine_version: Mapped[str] = mapped_column(String(32))
    mechanics_version: Mapped[int] = mapped_column(Integer, default=1)
    civilization_stage: Mapped[str | None] = mapped_column(String(16), nullable=True)
    compute_share: Mapped[float] = mapped_column(Float, default=1.0)
    model_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str] = mapped_column(String(32))


class SnapshotRow(Base):
    __tablename__ = "snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    universe_id: Mapped[str] = mapped_column(String(16), index=True)
    tick: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(32))
    engine_version: Mapped[str] = mapped_column(String(32))
    mechanics_version: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    blob: Mapped[bytes] = mapped_column(LargeBinary)


class EventRow(Base):
    __tablename__ = "events"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(32), index=True)
    universe_id: Mapped[str] = mapped_column(String(16), index=True)
    tick: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(Text)
    refs_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32))


Index("ix_events_universe_tick", EventRow.universe_id, EventRow.tick)


class AgentRow(Base):
    """Summary mirror of agents, refreshed at snapshot time and at death; for analysis queries."""

    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    universe_id: Mapped[str] = mapped_column(String(16), index=True)
    name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    generation: Mapped[int] = mapped_column(Integer)
    born_at_tick: Mapped[int] = mapped_column(Integer)
    died_at_tick: Mapped[int | None] = mapped_column(Integer, nullable=True)
    energy: Mapped[float] = mapped_column(Float)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    traits_json: Mapped[dict] = mapped_column(JSON)
    parent_ids_json: Mapped[list] = mapped_column(JSON)
    model_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[str] = mapped_column(String(32))


class MemoryRow(Base):
    __tablename__ = "agent_memories"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(32))
    agent_id: Mapped[str] = mapped_column(String(32), index=True)
    universe_id: Mapped[str] = mapped_column(String(16))
    tick: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(Text)
    salience: Mapped[float] = mapped_column(Float)
    data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class BeliefRow(Base):
    __tablename__ = "agent_beliefs"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(32))
    agent_id: Mapped[str] = mapped_column(String(32), index=True)
    universe_id: Mapped[str] = mapped_column(String(16))
    tick: Mapped[int] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(256))
    statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(16))
    revision: Mapped[int] = mapped_column(Integer, default=1)


class ModelRefRow(Base):
    __tablename__ = "model_refs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(32))
    adapter: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    family: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parameter_size: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quantization: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    first_seen: Mapped[str] = mapped_column(String(32))


class InferenceRequestRow(Base):
    __tablename__ = "inference_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    universe_id: Mapped[str] = mapped_column(String(16), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    tick: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[str] = mapped_column(String(32))
    priority: Mapped[int] = mapped_column(Integer, default=5)
    model_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_hash: Mapped[str] = mapped_column(String(64), index=True)
    prompt_version: Mapped[int] = mapped_column(Integer)
    prompt_profile: Mapped[str] = mapped_column(String(32))
    system_prompt: Mapped[str] = mapped_column(Text)
    messages_json: Mapped[list] = mapped_column(JSON)
    schema_hash: Mapped[str] = mapped_column(String(64))
    options_json: Mapped[dict] = mapped_column(JSON)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16))  # ok | invalid | error | timeout
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    validation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    contamination_terms_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32))


class DecisionRow(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(32), index=True)
    universe_id: Mapped[str] = mapped_column(String(16), index=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("inference_requests.id"), nullable=True)
    tick_requested: Mapped[int] = mapped_column(Integer)
    tick_applied: Mapped[int | None] = mapped_column(Integer, nullable=True)
    policy: Mapped[str] = mapped_column(String(8))  # reflex | model
    purpose: Mapped[str] = mapped_column(String(32))
    action_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    accepted: Mapped[bool] = mapped_column(Boolean)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    outcome_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32))


class HypothesisRow(Base):
    __tablename__ = "hypotheses"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    universe_id: Mapped[str] = mapped_column(String(16), index=True)
    state: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    proposed_at_tick: Mapped[int] = mapped_column(Integer)
    proposed_by_kind: Mapped[str] = mapped_column(String(16))
    proposed_by_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    existential: Mapped[bool] = mapped_column(Boolean, default=False)
    provenance_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_json: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[str] = mapped_column(String(32))


class ExperimentRow(Base):
    __tablename__ = "experiments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[str] = mapped_column(String(32))
    data_json: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[str] = mapped_column(String(32))


class BenchmarkRow(Base):
    __tablename__ = "benchmarks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[str] = mapped_column(String(32))
    provider_id: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    model_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    num_ctx: Mapped[int] = mapped_column(Integer)
    think: Mapped[bool] = mapped_column(Boolean)
    requests: Mapped[int] = mapped_column(Integer)
    results_json: Mapped[dict] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SettingsRow(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    data_json: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[str] = mapped_column(String(32))


class ProviderRow(Base):
    __tablename__ = "providers"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(64))
    adapter: Mapped[str] = mapped_column(String(32))
    base_url: Mapped[str] = mapped_column(String(256))
    model: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Never serialised to the API; only `has_credential` is exposed.
    credential: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


__all__ = [
    "Base",
    "CounterRow",
    "UniverseRow",
    "SnapshotRow",
    "EventRow",
    "AgentRow",
    "MemoryRow",
    "BeliefRow",
    "ModelRefRow",
    "InferenceRequestRow",
    "DecisionRow",
    "HypothesisRow",
    "ExperimentRow",
    "BenchmarkRow",
    "SettingsRow",
    "ProviderRow",
    "datetime",
]
