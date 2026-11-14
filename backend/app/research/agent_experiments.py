"""Agent-run experiments. An agent declares a procedure, a prediction and an expected outcome; the
world executes the procedure over several ticks and measures the outcome itself. The comparison
produces mechanics-verified evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agents.agent import AgentState, Belief, Intent, Memory
from app.research.engine import add_evidence
from app.simulation.actions import move_toward

if TYPE_CHECKING:
    from app.simulation.state import UniverseState

PROCEDURES = {"probe_boundary", "measure_regeneration", "observe_hazard_cycle", "probe_subworld_rules"}


def _finish(state: UniverseState, agent: AgentState, intent: Intent, outcome: str, measurement: str) -> bool:
    assert state.ids is not None
    expected = intent.params.get("expected")
    matched = outcome == expected
    hid = intent.params.get("hypothesisId")
    summary = f"{intent.params['procedure']}: predicted '{expected}', world produced '{outcome}'. {measurement}"
    agent.remember(Memory(state.ids.memory(), state.tick, "reflection", f"Experiment result — {summary}", 0.8, data={"outcome": outcome, "expected": expected}))
    key = f"exp:{intent.params['procedure']}"
    agent.beliefs[key] = Belief(state.ids.belief(), f"Result of {intent.params['procedure'].replace('_', ' ')}", f"The world produced '{outcome}'. {measurement}", 0.75, "observation", state.tick)
    if hid and hid in state.research.hypotheses:
        hyp = state.research.hypotheses[hid]
        add_evidence(state, hyp, "experiment", agent.id.upper(), 0.5 if matched else -0.5, summary, True, ("agent", agent.id, agent.name))
    state.research.active_experiments.pop(intent.state.get("exp_id", ""), None)
    state.emit("notice", "research", f"{agent.name} completed experiment {intent.params['procedure']}: {outcome} (predicted {expected}).", [{"kind": "agent", "id": agent.id}] + ([{"kind": "hypothesis", "id": hid}] if hid else []))
    return True


def experiment_step(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    proc = intent.params["procedure"]
    st = intent.state
    if "exp_id" not in st:
        st["exp_id"] = f"{agent.id}:{state.tick}"
        state.research.active_experiments[st["exp_id"]] = {"agentId": agent.id, "procedure": proc, "hypothesisId": intent.params.get("hypothesisId"), "startedTick": state.tick}
    rules = state.config.rules

    if proc == "probe_boundary":
        # Walk to the nearest vertical edge, then try to push beyond it for 12 ticks.
        if "edge_x" not in st:
            st["edge_x"] = 0.0 if agent.x < state.config.width / 2 else float(state.config.width - 0.001)
            st["phase"] = "approach"
        if st["phase"] == "approach":
            arrived, blocked = move_toward(state, agent, st["edge_x"], agent.y)
            if arrived or blocked or abs(agent.x - st["edge_x"]) < 1.0:
                st["phase"] = "push"
                st["push_ticks"] = 0
                st["start_x"] = agent.x
            return False
        st["push_ticks"] += 1
        beyond = -5.0 if st["edge_x"] < 1 else state.config.width + 5.0
        _, blocked = move_toward(state, agent, beyond, agent.y)
        if st["push_ticks"] < 12:
            return False
        displacement = abs(agent.x - st["start_x"])
        if rules.edge_mode == "wrap" and displacement > state.config.width / 2:
            return _finish(state, agent, intent, "passed", f"Displacement {displacement:.1f} units: I reappeared on the far side.")
        if displacement < 1.5:
            return _finish(state, agent, intent, "blocked", f"Displacement {displacement:.2f} units over 12 attempts.")
        return _finish(state, agent, intent, "passed", f"Displacement {displacement:.1f} units.")

    if proc == "measure_regeneration":
        cx, cy = state.cell_of(agent.x, agent.y)
        level = float(state.grid["resource"][cy, cx])
        if "start_level" not in st:
            st["start_level"] = level
            st["cx"], st["cy"] = cx, cy
        st["resting"] = True
        intent.progress += 1
        if intent.progress < 120:
            return False
        level = float(state.grid["resource"][st["cy"], st["cx"]])
        delta = level - st["start_level"]
        outcome = "increase" if delta > 0.01 else "decrease" if delta < -0.01 else "unchanged"
        return _finish(state, agent, intent, outcome, f"Resource at ({st['cx']},{st['cy']}) went {st['start_level']:.3f} → {level:.3f} over 120 ticks.")

    if proc == "observe_hazard_cycle":
        cx, cy = state.cell_of(agent.x, agent.y)
        samples = st.setdefault("samples", [])
        if intent.progress % 10 == 0:
            samples.append(round(float(state.grid["hazard"][cy, cx]), 4))
        st["resting"] = True
        intent.progress += 1
        if intent.progress < 360:
            return False
        rng_ = (max(samples) - min(samples)) if samples else 0.0
        # Periodicity test: the series must rise and fall (sign changes in its first difference).
        diffs = [b - a for a, b in zip(samples, samples[1:], strict=False)]
        changes = sum(1 for a, b in zip(diffs, diffs[1:], strict=False) if a * b < 0)
        outcome = "periodic" if rng_ > 0.03 and changes >= 1 else "aperiodic"
        return _finish(state, agent, intent, outcome, f"{len(samples)} samples, range {rng_:.3f}, {changes} turning points.")

    if proc == "probe_subworld_rules":
        if not state.portals:
            return _finish(state, agent, intent, "different_rules", "No sub-world exists to compare against; the probe found nothing.")
        portal = min(state.portals, key=lambda p: (p.x - agent.x) ** 2 + (p.y - agent.y) ** 2)
        arrived, _ = move_toward(state, agent, portal.x, portal.y)
        if not arrived:
            return False
        overrides = portal.rule_overrides or {}
        outcome = "same_rules" if not overrides else "different_rules"
        return _finish(state, agent, intent, outcome, f"Sub-world {portal.child_id} was instantiated with {len(overrides)} rule change(s): {', '.join(overrides) or 'none'}.")

    return True
