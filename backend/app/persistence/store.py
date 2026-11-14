"""Repository facade over the ORM. All methods are synchronous and short; the host calls the
batch-write methods through asyncio.to_thread so the event loop never waits on disk."""

from __future__ import annotations

import threading
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import orjson
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.hashing import sha256_hex
from app.core.timeutil import now_iso
from app.persistence import models as m
from app.persistence.db import make_engine, make_session_factory, run_migrations


class Store:
    def __init__(self, url: str, migrate: bool = True) -> None:
        self.url = url
        if migrate:
            run_migrations(url)
        self.engine: Engine = make_engine(url)
        self.sessions = make_session_factory(self.engine)
        # SQLite allows a single writer; the host writes from worker threads while the event loop
        # reads, so every session holds this lock for its (short) duration.
        self._lock = threading.RLock()

    def close(self) -> None:
        self.engine.dispose()

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._lock, self.sessions() as s:
            yield s

    # ------------------------------------------------------------ counters

    def next_counter(self, name: str) -> int:
        with self.session() as s, s.begin():
            row = s.get(m.CounterRow, name, with_for_update=False)
            if row is None:
                row = m.CounterRow(name=name, value=0)
                s.add(row)
            row.value += 1
            return row.value

    # ------------------------------------------------------------ universes

    def upsert_universe(self, data: dict[str, Any]) -> None:
        with self.session() as s, s.begin():
            row = s.get(m.UniverseRow, data["id"])
            if row is None:
                row = m.UniverseRow(id=data["id"])
                s.add(row)
            for k, v in data.items():
                setattr(row, k, v)
            row.updated_at = now_iso()

    def list_universes(self) -> list[m.UniverseRow]:
        with self.session() as s:
            return list(s.scalars(select(m.UniverseRow).order_by(m.UniverseRow.id)))

    def set_universe_status(self, uid: str, status: str, tick: int | None = None) -> None:
        with self.session() as s, s.begin():
            values: dict[str, Any] = {"status": status, "updated_at": now_iso()}
            if tick is not None:
                values["tick"] = tick
            s.execute(update(m.UniverseRow).where(m.UniverseRow.id == uid).values(**values))

    # ------------------------------------------------------------ snapshots

    def save_snapshot(self, universe_id: str, tick: int, state: dict[str, Any], engine_version: str, mechanics_version: int, retain: int) -> str:
        raw = orjson.dumps(state, option=orjson.OPT_SERIALIZE_NUMPY)
        blob = zlib.compress(raw, 6)
        digest = sha256_hex(raw)
        with self.session() as s, s.begin():
            s.add(
                m.SnapshotRow(
                    universe_id=universe_id,
                    tick=tick,
                    created_at=now_iso(),
                    engine_version=engine_version,
                    mechanics_version=mechanics_version,
                    sha256=digest,
                    size_bytes=len(blob),
                    blob=blob,
                )
            )
            if retain > 0:
                ids = list(
                    s.scalars(
                        select(m.SnapshotRow.id).where(m.SnapshotRow.universe_id == universe_id).order_by(m.SnapshotRow.tick.desc(), m.SnapshotRow.id.desc()).offset(retain)
                    )
                )
                if ids:
                    s.execute(delete(m.SnapshotRow).where(m.SnapshotRow.id.in_(ids)))
        return digest

    def latest_snapshot(self, universe_id: str) -> tuple[dict[str, Any], m.SnapshotRow] | None:
        with self.session() as s:
            row = s.scalars(select(m.SnapshotRow).where(m.SnapshotRow.universe_id == universe_id).order_by(m.SnapshotRow.tick.desc(), m.SnapshotRow.id.desc()).limit(1)).first()
            if row is None:
                return None
            return orjson.loads(zlib.decompress(row.blob)), row

    def list_snapshots(self, universe_id: str) -> list[m.SnapshotRow]:
        with self.session() as s:
            rows = s.scalars(select(m.SnapshotRow).where(m.SnapshotRow.universe_id == universe_id).order_by(m.SnapshotRow.tick.desc())).all()
            for r in rows:
                r.blob = b""  # do not ship blobs out of the store
            return list(rows)

    # ------------------------------------------------------------ events

    def append_events(self, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        ts = now_iso()
        with self.session() as s, s.begin():
            s.add_all(
                [
                    m.EventRow(
                        id=e["id"],
                        universe_id=e["universeId"],
                        tick=e["tick"],
                        severity=e["severity"],
                        category=e["category"],
                        summary=e["summary"],
                        refs_json=e.get("refs"),
                        data_json=e.get("data"),
                        created_at=ts,
                    )
                    for e in events
                ]
            )

    def list_events(self, universe_id: str | None = None, limit: int = 100, since_seq: int | None = None) -> list[m.EventRow]:
        with self.session() as s:
            q = select(m.EventRow)
            if universe_id:
                q = q.where(m.EventRow.universe_id == universe_id)
            if since_seq is not None:
                q = q.where(m.EventRow.seq > since_seq)
            q = q.order_by(m.EventRow.seq.desc()).limit(max(1, min(limit, 1000)))
            return list(s.scalars(q))

    # ------------------------------------------------------------ agents / memories / beliefs

    def upsert_agents(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        ts = now_iso()
        with self.session() as s, s.begin():
            for data in rows:
                row = s.get(m.AgentRow, data["id"])
                if row is None:
                    row = m.AgentRow(id=data["id"])
                    s.add(row)
                for k, v in data.items():
                    setattr(row, k, v)
                row.updated_at = ts

    def append_memories(self, rows: list[dict[str, Any]]) -> None:
        if rows:
            with self.session() as s, s.begin():
                s.add_all([m.MemoryRow(**r) for r in rows])

    def append_beliefs(self, rows: list[dict[str, Any]]) -> None:
        if rows:
            with self.session() as s, s.begin():
                s.add_all([m.BeliefRow(**r) for r in rows])

    def list_memories(self, agent_id: str, limit: int = 200, before_tick: int | None = None) -> list[m.MemoryRow]:
        with self.session() as s:
            q = select(m.MemoryRow).where(m.MemoryRow.agent_id == agent_id)
            if before_tick is not None:
                q = q.where(m.MemoryRow.tick < before_tick)
            q = q.order_by(m.MemoryRow.tick.desc(), m.MemoryRow.seq.desc()).limit(max(1, min(limit, 2000)))
            return list(s.scalars(q))

    # ------------------------------------------------------------ models / inference / decisions

    def upsert_model_ref(self, data: dict[str, Any]) -> None:
        with self.session() as s, s.begin():
            row = s.get(m.ModelRefRow, data["id"])
            if row is None:
                row = m.ModelRefRow(id=data["id"], first_seen=now_iso())
                s.add(row)
            for k, v in data.items():
                if k != "first_seen":
                    setattr(row, k, v)

    def list_model_refs(self) -> list[m.ModelRefRow]:
        with self.session() as s:
            return list(s.scalars(select(m.ModelRefRow).order_by(m.ModelRefRow.first_seen)))

    def insert_inference_request(self, data: dict[str, Any]) -> int:
        with self.session() as s, s.begin():
            row = m.InferenceRequestRow(**data, created_at=now_iso())
            s.add(row)
            s.flush()
            return row.id

    def update_inference_request(self, request_id: int, data: dict[str, Any]) -> None:
        with self.session() as s, s.begin():
            s.execute(update(m.InferenceRequestRow).where(m.InferenceRequestRow.id == request_id).values(**data))

    def find_replay_response(self, prompt_hash: str) -> m.InferenceRequestRow | None:
        with self.session() as s:
            return s.scalars(
                select(m.InferenceRequestRow)
                .where(m.InferenceRequestRow.prompt_hash == prompt_hash, m.InferenceRequestRow.status == "ok")
                .order_by(m.InferenceRequestRow.id.asc())
                .limit(1)
            ).first()

    def list_inference_requests(self, universe_id: str | None = None, agent_id: str | None = None, limit: int = 50) -> list[m.InferenceRequestRow]:
        with self.session() as s:
            q = select(m.InferenceRequestRow)
            if universe_id:
                q = q.where(m.InferenceRequestRow.universe_id == universe_id)
            if agent_id:
                q = q.where(m.InferenceRequestRow.agent_id == agent_id)
            q = q.order_by(m.InferenceRequestRow.id.desc()).limit(max(1, min(limit, 500)))
            return list(s.scalars(q))

    def get_inference_request(self, request_id: int) -> m.InferenceRequestRow | None:
        with self.session() as s:
            return s.get(m.InferenceRequestRow, request_id)

    def insert_decision(self, data: dict[str, Any]) -> int:
        with self.session() as s, s.begin():
            row = m.DecisionRow(**data, created_at=now_iso())
            s.add(row)
            s.flush()
            return row.id

    def insert_decisions(self, rows: list[dict[str, Any]]) -> None:
        if rows:
            ts = now_iso()
            with self.session() as s, s.begin():
                s.add_all([m.DecisionRow(**r, created_at=ts) for r in rows])

    def update_decision(self, decision_id: int, data: dict[str, Any]) -> None:
        with self.session() as s, s.begin():
            s.execute(update(m.DecisionRow).where(m.DecisionRow.id == decision_id).values(**data))

    def list_decisions(self, agent_id: str | None = None, universe_id: str | None = None, limit: int = 100, policy: str | None = None) -> list[tuple[m.DecisionRow, m.InferenceRequestRow | None]]:
        with self.session() as s:
            q = select(m.DecisionRow, m.InferenceRequestRow).outerjoin(m.InferenceRequestRow, m.DecisionRow.request_id == m.InferenceRequestRow.id)
            if agent_id:
                q = q.where(m.DecisionRow.agent_id == agent_id)
            if universe_id:
                q = q.where(m.DecisionRow.universe_id == universe_id)
            if policy:
                q = q.where(m.DecisionRow.policy == policy)
            q = q.order_by(m.DecisionRow.id.desc()).limit(max(1, min(limit, 1000)))
            return [(d, r) for d, r in s.execute(q).all()]

    def inference_latency_stats(self) -> tuple[int, int, int]:
        with self.session() as s:
            ok = s.scalar(select(func.count()).select_from(m.InferenceRequestRow).where(m.InferenceRequestRow.status == "ok")) or 0
            failed = s.scalar(select(func.count()).select_from(m.InferenceRequestRow).where(m.InferenceRequestRow.status.in_(("error", "timeout")))) or 0
            invalid = s.scalar(select(func.count()).select_from(m.InferenceRequestRow).where(m.InferenceRequestRow.valid.is_(False))) or 0
            return int(ok), int(failed), int(invalid)

    # ------------------------------------------------------------ hypotheses

    def upsert_hypotheses(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        ts = now_iso()
        with self.session() as s, s.begin():
            for data in rows:
                row = s.get(m.HypothesisRow, data["id"])
                if row is None:
                    row = m.HypothesisRow(id=data["id"])
                    s.add(row)
                for k, v in data.items():
                    setattr(row, k, v)
                row.updated_at = ts

    # ------------------------------------------------------------ experiments

    def upsert_experiment(self, exp_id: str, status: str, created_at: str, data: dict[str, Any]) -> None:
        with self.session() as s, s.begin():
            row = s.get(m.ExperimentRow, exp_id)
            if row is None:
                row = m.ExperimentRow(id=exp_id, created_at=created_at)
                s.add(row)
            row.status = status
            row.data_json = data
            row.updated_at = now_iso()

    def list_experiments(self) -> list[m.ExperimentRow]:
        with self.session() as s:
            return list(s.scalars(select(m.ExperimentRow).order_by(m.ExperimentRow.created_at)))

    def delete_experiment(self, exp_id: str) -> None:
        with self.session() as s, s.begin():
            s.execute(delete(m.ExperimentRow).where(m.ExperimentRow.id == exp_id))

    # ------------------------------------------------------------ benchmarks

    def insert_benchmark(self, data: dict[str, Any]) -> int:
        with self.session() as s, s.begin():
            row = m.BenchmarkRow(**{"created_at": now_iso(), **data})
            s.add(row)
            s.flush()
            return row.id

    def list_benchmarks(self, limit: int = 50) -> list[m.BenchmarkRow]:
        with self.session() as s:
            return list(s.scalars(select(m.BenchmarkRow).order_by(m.BenchmarkRow.id.desc()).limit(limit)))

    # ------------------------------------------------------------ settings / providers

    def get_settings(self) -> dict[str, Any] | None:
        with self.session() as s:
            row = s.get(m.SettingsRow, 1)
            return row.data_json if row else None

    def put_settings(self, data: dict[str, Any]) -> None:
        with self.session() as s, s.begin():
            row = s.get(m.SettingsRow, 1)
            if row is None:
                row = m.SettingsRow(id=1, data_json=data, updated_at=now_iso())
                s.add(row)
            else:
                row.data_json = data
                row.updated_at = now_iso()

    def list_providers(self) -> list[m.ProviderRow]:
        with self.session() as s:
            return list(s.scalars(select(m.ProviderRow).order_by(m.ProviderRow.position, m.ProviderRow.id)))

    def replace_providers(self, providers: list[dict[str, Any]]) -> None:
        """Replace provider rows while preserving stored credentials for ids that still exist."""
        with self.session() as s, s.begin():
            existing = {p.id: p for p in s.scalars(select(m.ProviderRow))}
            keep = {p["id"] for p in providers}
            for pid, row in existing.items():
                if pid not in keep:
                    s.delete(row)
            for i, p in enumerate(providers):
                row = existing.get(p["id"])
                if row is None:
                    row = m.ProviderRow(id=p["id"])
                    s.add(row)
                row.label = p["label"]
                row.adapter = p["adapter"]
                row.base_url = p["base_url"]
                row.model = p["model"]
                row.enabled = bool(p["enabled"])
                row.position = i

    def set_provider_credential(self, provider_id: str, credential: str | None) -> bool:
        with self.session() as s, s.begin():
            row = s.get(m.ProviderRow, provider_id)
            if row is None:
                return False
            row.credential = credential
            return True

    def get_provider_credential(self, provider_id: str) -> str | None:
        with self.session() as s:
            row = s.get(m.ProviderRow, provider_id)
            return row.credential if row else None


def open_store(url: str) -> Store:
    return Store(url, migrate=True)


def make_memory_store() -> Store:
    """In-memory SQLite for tests (schema created directly; no alembic)."""
    store = Store("sqlite://", migrate=False)
    m.Base.metadata.create_all(store.engine)
    return store
