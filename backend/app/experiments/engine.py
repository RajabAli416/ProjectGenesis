"""Operator experiments: a design (variables with control/treatment values, replicates, seed,
duration) that is executed as paired control/treatment universes per replicate. Metrics are
computed from mechanics at completion. `deterministic` is only true when it actually is."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from app.api import schemas as S
from app.core.errors import InvalidCommand, NotFound
from app.core.rng import derive_seed, random_seed_hex
from app.core.timeutil import now_iso
from app.simulation.engine import state_hash
from app.version import ENGINE_VERSION

if TYPE_CHECKING:
    from app.simulation.host import SimulationHost
    from app.simulation.state import UniverseState

log = logging.getLogger(__name__)

DETERMINISTIC_ADAPTERS = {"scripted", "replay"}


@dataclass
class RunRecord:
    id: str
    index: int
    started_at: str
    finished_at: str | None
    seed: str
    status: str
    universe_ids: list[str] = field(default_factory=list)
    control_universe_id: str | None = None
    treatment_universe_id: str | None = None
    metrics: dict[str, Any] | None = None


@dataclass
class ExperimentRecord:
    id: str
    name: str
    objective: str
    status: str
    control_universe_id: str | None
    variables: list[dict[str, Any]]
    replicates: int
    seed: str
    engine_version: str | None
    snapshot_hash: str | None
    deterministic: bool
    runs: list[RunRecord]
    hypothesis_ids: list[str]
    created_at: str
    duration_ticks: int = 2_000
    mode: str = "lockstep"
    base_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExperimentRecord:
        d = dict(d)
        d["runs"] = [RunRecord(**r) for r in d.get("runs", [])]
        return cls(**d)

    def dto(self) -> S.Experiment:
        return S.Experiment(
            id=self.id,
            name=self.name,
            objective=self.objective,
            status=self.status,  # type: ignore[arg-type]
            control_universe_id=self.control_universe_id,
            variables=[S.ExperimentVariable(**v) for v in self.variables],
            replicates=self.replicates,
            reproducibility=S.Reproducibility(seed=self.seed, engine_version=self.engine_version, snapshot_hash=self.snapshot_hash, deterministic=self.deterministic),
            runs=[S.ExperimentRun(id=r.id, index=r.index, started_at=r.started_at, finished_at=r.finished_at, seed=r.seed, status=r.status, universe_ids=list(r.universe_ids), control_universe_id=r.control_universe_id, treatment_universe_id=r.treatment_universe_id, metrics=r.metrics) for r in self.runs],  # type: ignore[arg-type]
            hypothesis_ids=list(self.hypothesis_ids),
            created_at=self.created_at,
            duration_ticks=self.duration_ticks,
            mode=self.mode,  # type: ignore[arg-type]
            base_config=self.base_config,
        )


class ExperimentsEngine:
    def __init__(self, host: SimulationHost) -> None:
        self.host = host
        self.experiments: dict[str, ExperimentRecord] = {}

    # ------------------------------------------------------------------ persistence

    def load(self) -> None:
        for row in self.host.store.list_experiments():
            try:
                self.experiments[row.id] = ExperimentRecord.from_dict(row.data_json)
            except Exception:  # noqa: BLE001
                log.exception("failed to load experiment %s", row.id)
        # Runs that were running when the process stopped are resumed as paused universes;
        # keep their status so the operator can see them and resume manually.

    def _save(self, exp: ExperimentRecord) -> None:
        self.host.store.upsert_experiment(exp.id, exp.status, exp.created_at, exp.to_dict())

    # ------------------------------------------------------------------ CRUD

    def list(self) -> list[ExperimentRecord]:
        return sorted(self.experiments.values(), key=lambda e: e.created_at)

    def get(self, exp_id: str) -> ExperimentRecord:
        e = self.experiments.get(exp_id)
        if e is None:
            raise NotFound(exp_id)
        return e

    def create(self, req: S.CreateExperimentRequest) -> ExperimentRecord:
        n = self.host.store.next_counter("experiment")
        exp = ExperimentRecord(
            id=f"exp-{n:03d}",
            name=req.name.strip() or f"Experiment {n}",
            objective=req.objective,
            status="draft",
            control_universe_id=req.control_universe_id,
            variables=[v.model_dump(by_alias=True) for v in req.variables],
            replicates=max(1, req.replicates),
            seed=req.seed or random_seed_hex(),
            engine_version=None,
            snapshot_hash=None,
            deterministic=False,
            runs=[],
            hypothesis_ids=list(req.hypothesis_ids),
            created_at=now_iso(),
            duration_ticks=max(10, req.duration_ticks),
            mode=req.mode,
            base_config=req.base_config,
        )
        self.experiments[exp.id] = exp
        self._save(exp)
        for hid in exp.hypothesis_ids:
            self._link_hypothesis(hid, exp.id)
        return exp

    def patch(self, exp_id: str, req: S.PatchExperimentRequest) -> ExperimentRecord:
        exp = self.get(exp_id)
        if exp.status == "running" and any(getattr(req, f) is not None for f in ("variables", "replicates", "seed", "duration_ticks", "mode")):
            raise InvalidCommand("design cannot change while runs are in progress")
        for f in ("name", "objective", "replicates", "seed", "duration_ticks", "mode", "status"):
            v = getattr(req, f)
            if v is not None:
                setattr(exp, f, v)
        if req.variables is not None:
            exp.variables = [v.model_dump(by_alias=True) for v in req.variables]
        if req.hypothesis_ids is not None:
            exp.hypothesis_ids = list(req.hypothesis_ids)
            for hid in exp.hypothesis_ids:
                self._link_hypothesis(hid, exp.id)
        self._save(exp)
        return exp

    def delete(self, exp_id: str) -> None:
        exp = self.get(exp_id)
        if exp.status == "running":
            raise InvalidCommand("abort the experiment before deleting it")
        del self.experiments[exp_id]
        self.host.store.delete_experiment(exp_id)

    def _link_hypothesis(self, hid: str, exp_id: str) -> None:
        for st in self.host.states():
            h = st.research.hypotheses.get(hid)
            if h and exp_id not in h.experiment_ids:
                h.experiment_ids.append(exp_id)
                h.dirty = True

    # ------------------------------------------------------------------ runs

    def _apply_variables(self, base: dict[str, Any], arm: str, exp: ExperimentRecord) -> dict[str, Any]:
        out = dict(base)
        for v in exp.variables:
            out[v["key"]] = v[arm]
        return out

    async def start_run(self, exp_id: str) -> ExperimentRecord:
        exp = self.get(exp_id)
        if exp.status == "running":
            raise InvalidCommand("a run is already in progress")
        if not exp.variables:
            raise InvalidCommand("add at least one variable before running")
        provider_spec = self.host._active_provider_spec()  # noqa: SLF001
        adapter = provider_spec.adapter if provider_spec else None
        try:
            probe = self.host.base_config(self._apply_variables(exp.base_config, "control", exp), seed=exp.seed, mode=exp.mode)
        except Exception as e:  # noqa: BLE001
            raise InvalidCommand(f"invalid configuration: {e}") from e
        reasoning_enabled = probe.reasoning.enabled and provider_spec is not None
        # Mechanics are deterministic per seed. A run is only *claimed* deterministic when model
        # output cannot vary: lockstep mode and either no model in the loop or a replayable provider.
        exp.deterministic = exp.mode == "lockstep" and (not reasoning_enabled or adapter in DETERMINISTIC_ADAPTERS)
        exp.engine_version = exp.engine_version or ENGINE_VERSION
        exp.status = "running"
        idx_base = len(exp.runs)
        for i in range(exp.replicates):
            index = idx_base + i + 1
            seed = derive_seed(exp.seed, f"replicate:{index}")
            run = RunRecord(id=f"run-{exp.id[4:]}-{index}", index=index, started_at=now_iso(), finished_at=None, seed=seed, status="running")
            for arm in ("control", "treatment"):
                overrides = self._apply_variables(exp.base_config, arm, exp)
                try:
                    cfg = self.host.base_config(overrides, seed=seed, mode=exp.mode)
                except Exception as e:  # noqa: BLE001
                    exp.status = "draft"
                    self._save(exp)
                    raise InvalidCommand(f"invalid {arm} configuration: {e}") from e
                st = await self.host.create_universe(
                    S.CreateUniverseRequest(name=f"{exp.name} · {arm} #{index}", start=True, mode=exp.mode),
                    created_by=("experiment", exp.id, f"{exp.id.upper()} {exp.name}"),
                    config=cfg,
                )
                run.universe_ids.append(st.id)
                if arm == "control":
                    run.control_universe_id = st.id
                    if exp.snapshot_hash is None:
                        exp.snapshot_hash = "sha256:" + state_hash(st)[:16]
                else:
                    run.treatment_universe_id = st.id
            exp.runs.append(run)
        self._save(exp)
        return exp

    async def abort(self, exp_id: str) -> ExperimentRecord:
        exp = self.get(exp_id)
        for run in exp.runs:
            if run.status in ("running", "queued"):
                run.status = "aborted"
                run.finished_at = now_iso()
                for uid in run.universe_ids:
                    if uid in self.host.runners:
                        st = self.host.get(uid)
                        if st.status == "running":
                            await self.host.command(uid, {"type": "pause"})
        exp.status = "aborted"
        self._save(exp)
        return exp

    async def observe(self, state: UniverseState) -> None:
        """Called by the host after each batch of ticks for every universe."""
        if state.created_by_kind != "experiment" or state.created_by_id not in self.experiments:
            return
        exp = self.experiments[state.created_by_id]
        run = next((r for r in exp.runs if state.id in r.universe_ids), None)
        if run is None or run.status != "running":
            return
        if state.tick >= exp.duration_ticks and state.status == "running":
            state.status = "paused"
            state.emit("notice", "system", f"Run {run.id} reached {exp.duration_ticks:,} ticks; universe paused.", [{"kind": "experiment", "id": exp.id}])
            self.host.store.set_universe_status(state.id, "paused", state.tick)
        def _finished(uid: str) -> bool:
            if uid not in self.host.runners:
                return False
            st = self.host.get(uid)
            return st.status == "terminated" or (st.status == "paused" and st.tick >= exp.duration_ticks)

        if all(_finished(uid) for uid in run.universe_ids):
            run.status = "complete"
            run.finished_at = now_iso()
            run.metrics = {arm: self.metrics(self.host.get(uid)) for arm, uid in (("control", run.control_universe_id), ("treatment", run.treatment_universe_id)) if uid}
            if all(r.status in ("complete", "aborted") for r in exp.runs):
                exp.status = "complete"
            self._save(exp)
            self.host.bus.publish({"type": "universe.changed", "universeId": state.id})

    # ------------------------------------------------------------------ metrics

    @staticmethod
    def metrics(state: UniverseState) -> dict[str, Any]:
        alive = state.alive_agents()
        hyps = list(state.research.hypotheses.values())
        prov: dict[str, int] = {}
        for h in hyps:
            prov[h.provenance_class] = prov.get(h.provenance_class, 0) + 1
        decisions_model = sum(a.decisions_model for a in state.agents.values())
        decisions_total = sum(a.decisions_total for a in state.agents.values())
        return {
            "tick": state.tick,
            "alive": len(alive),
            "born": state.born,
            "died": state.died,
            "generations": state.max_generation,
            "meanEnergy": round(sum(a.energy for a in alive) / len(alive), 4) if alive else 0.0,
            "structures": len(state.structures),
            "firstStructureTick": state.civilization.first_structure_tick,
            "technologiesEstablished": sorted(t.id for t in state.civilization.technologies.values() if t.state == "established"),
            "institutions": len(state.civilization.institutions),
            "stage": state.civilization.stage,
            "hypotheses": len(hyps),
            "hypothesesByProvenance": prov,
            "existentialHypotheses": sum(1 for h in hyps if h.existential),
            "decisionsTotal": decisions_total,
            "decisionsModel": decisions_model,
            "decisionsReflex": decisions_total - decisions_model,
            "trades": state.civilization.trades,
            "messages": state.civilization.messages,
            "children": len(state.child_ids),
            "stateHash": state_hash(state)[:16],
        }
