"""SimulationHost: the single owner of every universe in the process. It creates, restores, runs,
persists and broadcasts universes; fulfils agents' sub-world requests; and routes cognition requests
to the shared inference service. The API layer only ever talks to the host."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from app.api import schemas as S
from app.config import Settings
from app.core.errors import InvalidCommand, NotFound
from app.core.events import EventBus
from app.core.ids import universe_code, universe_id
from app.core.rng import derive_seed, random_seed_hex
from app.core.timeutil import now_iso
from app.intelligence.cognition import CognitionEngine, CognitionScheduler, ResolvedModel
from app.intelligence.model_registry import ModelRegistry, ProviderSpec
from app.intelligence.service import InferenceService
from app.operator_settings import default_settings, merge_settings, universe_config_overrides
from app.persistence.store import Store
from app.recursion.spawn import attach_child, child_config, child_seed_for
from app.simulation.config import UniverseConfig, build_config
from app.simulation.engine import new_universe, state_hash
from app.simulation.runner import UniverseRunner
from app.simulation.snapshot import agent_dto, universe_dto, world_snapshot
from app.simulation.state import UniverseState
from app.version import ENGINE_VERSION, MECHANICS_VERSION, PROMPT_VERSION

if TYPE_CHECKING:
    from app.experiments.engine import ExperimentsEngine

log = logging.getLogger(__name__)


class SimulationHost:
    def __init__(self, settings: Settings, store: Store, bus: EventBus | None = None) -> None:
        self.settings = settings
        self.store = store
        self.bus = bus or EventBus()
        self.started_at = time.time()
        self.runners: dict[str, UniverseRunner] = {}
        self.operator: S.OperatorSettings = merge_settings(default_settings(settings), store.get_settings())
        self.inference = InferenceService(concurrency=self.operator.reasoning.concurrency)
        self.registry = ModelRegistry(store, keep_alive=settings.inference_keep_alive)
        self.cognition = CognitionEngine(self.inference, store, self.resolve_model, max_repair_attempts=max(0, self.operator.reasoning.max_steps - 1))
        self.experiments: ExperimentsEngine | None = None
        self._provider_health: dict[str, Any] = {"reachable": False}
        self._last_clock_broadcast: dict[str, float] = {}
        self._last_snapshot_broadcast: dict[str, float] = {}
        self._last_flush_tick: dict[str, int] = {}
        self._last_snapshot_tick: dict[str, int] = {}
        self._resolved_cache: dict[str, tuple[float, ResolvedModel | None]] = {}
        self._health_task: asyncio.Task | None = None
        self.ws_clients = 0
        self.scripted_override: Any = None  # tests inject a provider here

    # ------------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        await self.inference.start()
        await self.refresh_provider()
        from app.experiments.engine import ExperimentsEngine  # noqa: PLC0415

        self.experiments = ExperimentsEngine(self)
        self.experiments.load()
        await self.restore_all()
        self._health_task = asyncio.create_task(self._health_loop(), name="provider-health")

    async def stop(self) -> None:
        if self._health_task:
            self._health_task.cancel()
        for runner in list(self.runners.values()):
            st = runner.state
            if st.status == "running":
                st.status = "paused"
                st.emit("info", "system", "Universe paused by shutdown.")
            await runner.stop()
            await self.flush(st)
            if st.status != "archived":
                await self.snapshot(st)
        await self.inference.stop()
        await self.registry.close()

    async def _health_loop(self) -> None:
        while True:
            await asyncio.sleep(15)
            try:
                await self.refresh_provider(health_only=True)
            except Exception:  # noqa: BLE001
                log.exception("provider health refresh failed")

    # ------------------------------------------------------------------ providers / settings

    def _active_provider_spec(self, provider_id: str | None = None) -> ProviderSpec | None:
        pid = provider_id or self.operator.reasoning.provider_id
        p = next((p for p in self.operator.providers if p.id == pid), None)
        if p is None or not p.enabled:
            return None
        return ProviderSpec(id=p.id, label=p.label, adapter=p.adapter, base_url=p.base_url, model=p.model, enabled=p.enabled, credential=self.store.get_provider_credential(p.id))

    async def refresh_provider(self, health_only: bool = False) -> None:
        spec = self._active_provider_spec()
        if spec is None:
            self.inference.set_provider(None)
            self._provider_health = {"reachable": False, "error": "no enabled default provider"}
            return
        provider = self.scripted_override or await self.registry.get(spec, replay_lookup=self._replay_lookup)
        self.inference.set_provider(provider)
        self._provider_health = await provider.health()
        self._provider_health["provider_id"] = spec.id
        self._provider_health["adapter"] = provider.adapter
        self._provider_health["model"] = spec.model
        if not health_only:
            self._resolved_cache.clear()

    def _replay_lookup(self, prompt_hash: str) -> str | None:
        row = self.store.find_replay_response(prompt_hash)
        return row.raw_response if row else None

    async def resolve_model(self, state: UniverseState) -> ResolvedModel | None:
        rp = state.config.reasoning
        rs = self.operator.reasoning
        key = f"{rp.provider_id or ''}|{rp.model or ''}|{rp.prompt_profile}"
        cached = self._resolved_cache.get(key)
        if cached and time.time() - cached[0] < 30:
            rm = cached[1]
        else:
            spec = self._active_provider_spec(rp.provider_id)
            if spec is None:
                rm = None
            else:
                provider = self.scripted_override or await self.registry.get(spec, replay_lookup=self._replay_lookup)
                model = rp.model or spec.model
                model_ref = await self.registry.resolve_model_ref(provider, model)
                rm = ResolvedModel(
                    provider=provider,
                    model=model,
                    model_ref=model_ref,
                    temperature=rp.temperature if rp.temperature is not None else rs.temperature,
                    num_ctx=rp.num_ctx or rs.num_ctx,
                    think_decisions=rp.think_decisions if rp.think_decisions is not None else rs.think_decisions,
                    think_reflection=rp.think_reflection if rp.think_reflection is not None else rs.think_reflection,
                    timeout_s=rs.timeout_s,
                    prompt_profile=rp.prompt_profile,
                )
            self._resolved_cache[key] = (time.time(), rm)
        if rm is not None and rm.provider is not self.inference.provider and rp.provider_id is None:
            rm.provider = self.inference.provider or rm.provider
        return rm

    async def apply_settings(self, new: S.OperatorSettings) -> S.OperatorSettings:
        stored = new.model_dump(by_alias=True)
        self.store.put_settings(stored)
        self.store.replace_providers([{"id": p.id, "label": p.label, "adapter": p.adapter, "base_url": p.base_url, "model": p.model, "enabled": p.enabled} for p in new.providers])
        creds = {p.id: self.store.get_provider_credential(p.id) is not None for p in new.providers}
        for p in new.providers:
            p.has_credential = creds.get(p.id, False)
        self.operator = new
        self.cognition.max_repair_attempts = max(0, new.reasoning.max_steps - 1)
        if new.reasoning.concurrency != self.inference.concurrency:
            await self.inference.set_concurrency(new.reasoning.concurrency)
        self._resolved_cache.clear()
        await self.refresh_provider()
        return self.operator

    def set_credential(self, provider_id: str, credential: str | None) -> bool:
        ok = self.store.set_provider_credential(provider_id, credential)
        for p in self.operator.providers:
            if p.id == provider_id:
                p.has_credential = credential is not None
        self._resolved_cache.clear()
        return ok

    def inference_status(self) -> S.InferenceStatus:
        h = self._provider_health
        st = self.inference.stats()
        ok, failed, invalid = self.store.inference_latency_stats()
        model = h.get("model")
        ref = None
        for r in self.registry.model_refs.values():
            if r["model"] == model and r["provider_id"] == h.get("provider_id"):
                ref = S.ModelRef(**{k: r.get(k) for k in ("id", "provider_id", "adapter", "model", "digest", "family", "parameter_size", "quantization", "first_seen")})
        loaded = h.get("loaded_models") or []
        return S.InferenceStatus(
            provider_id=h.get("provider_id"),
            adapter=h.get("adapter"),
            reachable=bool(h.get("reachable")),
            provider_version=h.get("version"),
            model=model,
            model_ref=ref,
            model_loaded=any(model and (m == model or (m or "").startswith(model + ":")) for m in loaded),
            queue_depth=st["queue_depth"],
            in_flight=st["in_flight"],
            concurrency=st["concurrency"],
            completed=ok,
            failed=failed,
            invalid=invalid,
            latency_p50_ms=st["latency_p50_ms"],
            latency_p95_ms=st["latency_p95_ms"],
            last_error=st["last_error"] or h.get("error"),
        )

    # ------------------------------------------------------------------ universes

    def get(self, uid: str) -> UniverseState:
        r = self.runners.get(uid)
        if r is None:
            raise NotFound(f"universe {uid} not found")
        return r.state

    def states(self) -> list[UniverseState]:
        return [r.state for r in self.runners.values()]

    def rate_of(self, uid: str) -> float:
        r = self.runners.get(uid)
        return r.achieved_rate if r else 0.0

    def budget_for(self, state: UniverseState) -> float:
        return max(1.0, self.settings.host_tick_budget * state.compute_share)

    def base_config(self, overrides: dict[str, Any] | None = None, seed: str | None = None, population: int | None = None, mode: str = "realtime") -> UniverseConfig:
        base = universe_config_overrides(self.operator)
        base["seed"] = seed or random_seed_hex()
        base["mode"] = mode
        if population is not None:
            base["initial_population"] = population
        return build_config({}, {**base, **(overrides or {})})

    async def create_universe(self, req: S.CreateUniverseRequest, created_by: tuple[str, str | None, str] = ("operator", None, "Operator"), parent: UniverseState | None = None, config: UniverseConfig | None = None, compute_share: float = 1.0) -> UniverseState:
        n = self.store.next_counter("universe")
        cfg = config or self.base_config(req.config, req.seed, req.initial_population, req.mode)
        state = new_universe(
            id=universe_id(n),
            number=n,
            code=universe_code(n - 1),
            name=req.name or f"Universe {n}",
            config=cfg,
            parent_id=parent.id if parent else None,
            depth=parent.depth + 1 if parent else 0,
            created_by=created_by,
            created_at_tick=parent.tick if parent else 0,
            compute_share=compute_share,
        )
        runner = UniverseRunner(state, self)
        self.runners[state.id] = runner
        self.store.upsert_universe(self._universe_row(state))
        await self.flush(state)
        await self.snapshot(state)
        if req.start:
            state.status = "running"
            self.store.set_universe_status(state.id, "running", state.tick)
        runner.start()
        self.bus.publish({"type": "universe.changed", "universeId": state.id})
        return state

    async def archive(self, uid: str) -> UniverseState:
        state = self.get(uid)
        runner = self.runners[uid]
        if state.status == "running":
            state.status = "paused"
        await runner.stop()
        state.status = "archived"
        state.emit("info", "system", "Universe archived by operator.")
        await self.flush(state)
        await self.snapshot(state)
        self.store.set_universe_status(uid, "archived", state.tick)
        self.bus.publish({"type": "universe.changed", "universeId": uid})
        return state

    async def command(self, uid: str, cmd: dict[str, Any]) -> S.CommandResult:
        try:
            state = self.get(uid)
        except NotFound:
            return S.CommandResult(accepted=False, reason=f"Universe {uid} not found.")
        runner = self.runners[uid]
        if state.status in ("terminated", "archived"):
            return S.CommandResult(accepted=False, reason=f"Universe is {state.status}; no commands accepted.")
        ctype = cmd.get("type")
        try:
            if ctype == "pause":
                if state.status != "running":
                    return S.CommandResult(accepted=False, reason="Universe is not running.")
                state.status = "paused"
                state.emit("warning", "system", "Universe paused by operator.", [{"kind": "universe", "id": uid}])
                await runner.drain_cognition()
                await self.after_batch(runner, force=True)
                await self.snapshot(state)
            elif ctype == "resume":
                if state.status == "running":
                    return S.CommandResult(accepted=False, reason="Universe is already running.")
                state.status = "running"
                state.emit("info", "system", "Universe resumed by operator.", [{"kind": "universe", "id": uid}])
                runner.start()
            elif ctype == "step":
                if state.status == "running":
                    return S.CommandResult(accepted=False, reason="Pause the universe before stepping.")
                ticks = int(cmd.get("ticks", 1))
                if ticks < 1 or ticks > 10_000:
                    raise InvalidCommand("ticks must be between 1 and 10000")
                await runner.step(ticks)
            elif ctype == "setSpeed":
                speed = float(cmd.get("speed", 1.0))
                if not (0.05 <= speed <= 64):
                    raise InvalidCommand("speed must be between 0.05 and 64")
                state.speed = speed
            else:
                raise InvalidCommand(f"unknown command type {ctype!r}")
        except (InvalidCommand, ValueError) as e:
            return S.CommandResult(accepted=False, reason=str(e))
        self.store.set_universe_status(uid, state.status, state.tick)
        self.bus.publish({"type": "clock", "universeId": uid, "clock": self.clock_dto(state).model_dump(by_alias=True)})
        self.bus.publish({"type": "universe.changed", "universeId": uid})
        return S.CommandResult(accepted=True)

    def clock_dto(self, state: UniverseState) -> S.SimulationClock:
        return S.SimulationClock(tick=state.tick, rate=round(self.rate_of(state.id), 2), speed=state.speed, observed_at=now_iso())

    def universe_dto(self, state: UniverseState) -> S.Universe:
        return universe_dto(state, self.rate_of(state.id))

    # ------------------------------------------------------------------ restore

    async def restore_all(self) -> None:
        for row in self.store.list_universes():
            if row.status == "archived":
                continue
            found = self.store.latest_snapshot(row.id)
            if found is None:
                log.warning("universe %s has no snapshot; skipping", row.id)
                continue
            data, snap = found
            try:
                state = UniverseState.from_dict(data)
            except Exception:  # noqa: BLE001
                log.exception("failed to restore %s from snapshot at tick %s", row.id, snap.tick)
                continue
            for a in state.agents.values():
                a.pending_request = False
            if state.status == "running":
                state.status = "running" if self.settings.autostart_restored else "paused"
            if state.tick != row.tick:
                state.emit("warning", "system", f"Restored from snapshot at tick {state.tick:,}; {max(0, row.tick - state.tick):,} ticks after it were not persisted.")
            else:
                state.emit("info", "system", f"Restored from snapshot at tick {state.tick:,}.")
            runner = UniverseRunner(state, self)
            self.runners[state.id] = runner
            self._last_snapshot_tick[state.id] = state.tick
            self._last_flush_tick[state.id] = state.tick
            self.store.set_universe_status(state.id, state.status, state.tick)
            runner.start()
            log.info("restored universe %s at tick %d (%s)", state.id, state.tick, state.status)

    # ------------------------------------------------------------------ tick hooks

    async def after_tick(self, runner: UniverseRunner) -> None:
        state = runner.state
        triggers = CognitionScheduler.collect(state)
        if triggers and self.inference.provider is not None:
            for aid, purpose, priority in triggers:
                t = asyncio.create_task(self.cognition.run(state, aid, purpose, priority), name=f"cog-{aid}-{state.tick}")
                runner.cognition_tasks.add(t)
                t.add_done_callback(runner.cognition_tasks.discard)
            if state.config.mode == "lockstep":
                await runner.drain_cognition()
        if state.pending_subworlds:
            reqs, state.pending_subworlds = list(state.pending_subworlds), []
            for req in reqs:
                await self._fulfil_subworld(state, req)
        if state.status == "terminated":
            self.store.set_universe_status(state.id, "terminated", state.tick)
            self.bus.publish({"type": "universe.changed", "universeId": state.id})

    async def after_batch(self, runner: UniverseRunner, force: bool = False) -> None:
        state = runner.state
        now = time.time()
        cfg = self.settings
        if force or state.tick - self._last_flush_tick.get(state.id, 0) >= cfg.event_flush_ticks:
            await self.flush(state)
        if self.operator.persistence.autosave and state.tick - self._last_snapshot_tick.get(state.id, 0) >= self.operator.persistence.snapshot_interval_ticks:
            await self.snapshot(state)
        if force or now - self._last_clock_broadcast.get(state.id, 0) >= 1.0 / cfg.clock_broadcast_hz:
            self._last_clock_broadcast[state.id] = now
            self.bus.publish({"type": "clock", "universeId": state.id, "clock": self.clock_dto(state).model_dump(by_alias=True)})
        if (force or now - self._last_snapshot_broadcast.get(state.id, 0) >= 1.0 / cfg.snapshot_broadcast_hz) and self._anyone_watching(state.id):
            self._last_snapshot_broadcast[state.id] = now
            self.bus.publish({"type": "snapshot", "snapshot": world_snapshot(state).model_dump(by_alias=True)})
        if self.experiments is not None:
            await self.experiments.observe(state)

    def _anyone_watching(self, uid: str) -> bool:
        return any(sub.universe_filter is None or uid in sub.universe_filter for sub in self.bus.subscriptions)

    # ------------------------------------------------------------------ persistence

    async def flush(self, state: UniverseState) -> None:
        events, state.outbox_events = state.outbox_events, []
        decisions, state.outbox_decisions = state.outbox_decisions, []
        beliefs, state.outbox_beliefs = state.outbox_beliefs, []
        for ev in events:
            self.bus.publish({"type": "event", "event": {k: v for k, v in ev.items() if k != "data"}})
        self._last_flush_tick[state.id] = state.tick

        def _write() -> None:
            self.store.append_events(events)
            self.store.append_beliefs(beliefs)
            for d in decisions:
                if "_update" in d:
                    self.store.update_decision(d["_update"], {k: v for k, v in d.items() if k != "_update"})
            self.store.upsert_universe(self._universe_row(state))

        await asyncio.to_thread(_write)

    async def snapshot(self, state: UniverseState) -> str:
        self._last_snapshot_tick[state.id] = state.tick
        payload = state.to_dict()
        agents = [
            {"id": a.id, "universe_id": state.id, "name": a.name, "status": a.status, "generation": a.generation, "born_at_tick": a.born_at_tick, "died_at_tick": a.died_at_tick, "energy": a.energy, "x": a.x, "y": a.y, "traits_json": a.traits, "parent_ids_json": a.parent_ids, "model_ref": a.model_ref}
            for a in state.agents.values()
        ]
        # Persist memories created since the last snapshot. The agent's memory list may have been
        # pruned, so persist by id rather than by position.
        new_mem_rows = []
        for a in state.agents.values():
            seen = a.memory_counter  # number of memories already persisted (by creation order)
            fresh = [m for m in a.memories if _mem_seq(m.id) > seen]
            for m in fresh:
                new_mem_rows.append({"id": m.id, "agent_id": a.id, "universe_id": state.id, "tick": m.tick, "kind": m.kind, "source": m.source, "summary": m.summary, "salience": m.salience, "data_json": m.data})
            if a.memories:
                a.memory_counter = max(seen, max(_mem_seq(m.id) for m in a.memories))
        hyps = [
            {"id": h.id, "universe_id": state.id, "state": h.state, "confidence": h.confidence, "proposed_at_tick": h.proposed_at_tick, "proposed_by_kind": h.proposed_by_kind, "proposed_by_id": h.proposed_by_id, "existential": h.existential, "provenance_class": h.provenance_class, "data_json": {"title": h.title, "statement": h.statement, "evidence": len(h.evidence), "reasoning": len(h.reasoning)}}
            for h in state.research.hypotheses.values()
        ]
        retain = self.operator.persistence.retain_snapshots

        def _write() -> str:
            self.store.upsert_agents(agents)
            self.store.append_memories(new_mem_rows)
            self.store.upsert_hypotheses(hyps)
            return self.store.save_snapshot(state.id, state.tick, payload, ENGINE_VERSION, MECHANICS_VERSION, retain)

        return await asyncio.to_thread(_write)

    def _universe_row(self, state: UniverseState) -> dict[str, Any]:
        return {
            "id": state.id,
            "code": state.code,
            "name": state.name,
            "status": state.status,
            "parent_id": state.parent_id,
            "depth": state.depth,
            "created_by_kind": state.created_by_kind,
            "created_by_id": state.created_by_id,
            "created_by_label": state.created_by_label,
            "created_at_tick": state.created_at_tick,
            "created_at": state.created_at,
            "seed": state.seed,
            "config_json": state.config.model_dump(mode="json"),
            "config_version": state.config.config_version,
            "tick": state.tick,
            "speed": state.speed,
            "mode": state.config.mode,
            "engine_version": ENGINE_VERSION,
            "mechanics_version": MECHANICS_VERSION,
            "civilization_stage": state.civilization.stage,
            "compute_share": state.compute_share,
            "model_ref": state.model_ref,
        }

    # ------------------------------------------------------------------ recursion

    async def _fulfil_subworld(self, parent: UniverseState, req: dict[str, Any]) -> None:
        rules = parent.config.rules
        if parent.depth >= rules.max_recursion_depth:
            parent.emit("warning", "universe", "Sub-world request refused: maximum recursion depth reached.")
            return
        child_share = parent.compute_share * rules.subworld_compute_share
        seed = child_seed_for(parent.seed, len(parent.child_ids) + 1)
        cfg = child_config(parent.config, seed, req.get("rule_overrides") or {})
        child = await self.create_universe(
            S.CreateUniverseRequest(name=req["name"], start=True, mode=parent.config.mode),
            created_by=("agent", req.get("creator_id"), req.get("creator_label", "agent")),
            parent=parent,
            config=cfg,
            compute_share=child_share,
        )
        attach_child(parent, child.id, req, child_share)
        self.store.upsert_universe(self._universe_row(parent))
        self.bus.publish({"type": "universe.changed", "universeId": parent.id})

    # ------------------------------------------------------------------ misc

    def agent_dto(self, state: UniverseState, agent_id: str, memory_limit: int | None = None) -> S.Agent:
        a = state.agents.get(agent_id)
        if a is None:
            raise NotFound(agent_id)
        return agent_dto(state, a, memory_limit)

    def find_agent(self, agent_id: str) -> tuple[UniverseState, Any] | None:
        for st in self.states():
            if agent_id in st.agents:
                return st, st.agents[agent_id]
        return None

    def state_hash(self, uid: str) -> str:
        return state_hash(self.get(uid))

    def host_status(self) -> S.HostStatus:
        running = [s for s in self.states() if s.status == "running"]
        return S.HostStatus(
            engine_version=ENGINE_VERSION,
            mechanics_version=MECHANICS_VERSION,
            prompt_version=PROMPT_VERSION,
            uptime_s=round(time.time() - self.started_at, 1),
            universes=len(self.runners),
            running=len(running),
            total_rate=round(sum(self.rate_of(s.id) for s in running), 1),
            host_tick_budget=self.settings.host_tick_budget,
            ws_clients=self.ws_clients,
            db_path=str(self.settings.db_path),
            inference=self.inference_status(),
        )


def derived_seed(seed: str, salt: str) -> str:
    return derive_seed(seed, salt)


def _mem_seq(mem_id: str) -> int:
    """Memory ids are 'm-<universe>-<n>'; n is the universe-wide creation sequence."""
    try:
        return int(mem_id.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return 0
