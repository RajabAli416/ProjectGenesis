"""Action registry: the complete set of things an agent can do. Each action declares its parameter
schema (shown to the model), an availability check (affordance), a validator for model-proposed
parameters, and a deterministic per-tick executor. The LLM never touches state directly; it only
selects one of these and the executor applies it."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.agents.agent import AgentState, Belief, Intent, Memory, Message
from app.agents.perception import distance
from app.simulation import terrain

if TYPE_CHECKING:
    from app.simulation.state import UniverseState

ParamSchema = dict[str, dict[str, Any]]


@dataclass
class ActionSpec:
    name: str
    description: str
    params: ParamSchema = field(default_factory=dict)
    available: Callable[[UniverseState, AgentState], bool] = lambda s, a: True
    validate: Callable[[UniverseState, AgentState, dict[str, Any]], str | None] = lambda s, a, p: None
    step: Callable[[UniverseState, AgentState, Intent], bool] = lambda s, a, i: True
    default_ttl: int = 120

    def describe(self) -> dict[str, Any]:
        return {"type": self.name, "description": self.description, "params": self.params}


REGISTRY: dict[str, ActionSpec] = {}


def register(spec: ActionSpec) -> ActionSpec:
    REGISTRY[spec.name] = spec
    return spec


def available_actions(state: UniverseState, agent: AgentState) -> list[ActionSpec]:
    return [spec for spec in REGISTRY.values() if spec.available(state, agent)]


def validate_action(state: UniverseState, agent: AgentState, action: dict[str, Any]) -> str | None:
    atype = action.get("type")
    if not isinstance(atype, str) or atype not in REGISTRY:
        return f"unknown action type {atype!r}"
    spec = REGISTRY[atype]
    if not spec.available(state, agent):
        return f"action {atype!r} is not available to this agent right now"
    params = action.get("params") or {}
    if not isinstance(params, dict):
        return "params must be an object"
    for key, meta in spec.params.items():
        if meta.get("required") and key not in params:
            return f"missing required param {key!r}"
        if key in params:
            err = _check_type(params[key], meta, key)
            if err:
                return err
    return spec.validate(state, agent, params)


def _check_type(value: Any, meta: dict[str, Any], key: str) -> str | None:
    t = meta.get("type")
    if t == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"param {key!r} must be a number"
        lo, hi = meta.get("min"), meta.get("max")
        if lo is not None and value < lo:
            return f"param {key!r} below minimum {lo}"
        if hi is not None and value > hi:
            return f"param {key!r} above maximum {hi}"
    elif t == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return f"param {key!r} must be an integer"
    elif t == "string":
        if not isinstance(value, str):
            return f"param {key!r} must be a string"
        if "enum" in meta and value not in meta["enum"]:
            return f"param {key!r} must be one of {meta['enum']}"
        if "maxLength" in meta and len(value) > meta["maxLength"]:
            return f"param {key!r} too long"
    elif t == "object" and not isinstance(value, dict):
        return f"param {key!r} must be an object"
    return None


# ---------------------------------------------------------------------------------- movement helpers


def _wrap_or_clamp(state: UniverseState, x: float, y: float) -> tuple[float, float, bool]:
    w, h = state.config.width, state.config.height
    blocked = False
    if state.config.rules.edge_mode == "wrap":
        x %= w
        y %= h
    else:
        nx = min(w - 0.001, max(0.0, x))
        ny = min(h - 0.001, max(0.0, y))
        blocked = (nx != x) or (ny != y)
        x, y = nx, ny
    return x, y, blocked


def move_toward(state: UniverseState, agent: AgentState, tx: float, ty: float) -> tuple[bool, bool]:
    """Advance one step toward (tx, ty). Returns (arrived, blocked_by_edge)."""
    speed = state.config.rules.move_speed * (0.5 if agent.status == "dormant" else 1.0)
    dx, dy = tx - agent.x, ty - agent.y
    dist = math.hypot(dx, dy)
    if dist <= speed:
        nx, ny = tx, ty
    else:
        nx, ny = agent.x + dx / dist * speed, agent.y + dy / dist * speed
    nx, ny, blocked = _wrap_or_clamp(state, nx, ny)
    cx, cy = state.cell_of(nx, ny)
    if not state.passable(cx, cy):
        # Deterministic side-step: try the perpendicular directions in a fixed order.
        for px, py in ((-dy, dx), (dy, -dx)):
            n = math.hypot(px, py) or 1.0
            sx, sy = agent.x + px / n * speed, agent.y + py / n * speed
            sx, sy, _ = _wrap_or_clamp(state, sx, sy)
            scx, scy = state.cell_of(sx, sy)
            if state.passable(scx, scy):
                agent.x, agent.y = sx, sy
                return False, blocked
        return False, blocked  # stuck this tick
    agent.x, agent.y = nx, ny
    arrived = math.hypot(tx - agent.x, ty - agent.y) < 0.5
    return arrived, blocked


def _record_edge_block(state: UniverseState, agent: AgentState, intent: Intent) -> None:
    if not state.config.rules.edge_signal:
        return
    intent.state["edge_blocks"] = intent.state.get("edge_blocks", 0) + 1
    if intent.state["edge_blocks"] == 3:
        assert state.ids is not None
        agent.remember(Memory(state.ids.memory(), state.tick, "perception", f"Movement toward ({intent.params.get('x', 0):.0f}, {intent.params.get('y', 0):.0f}) produced no displacement; something stops me at the edge of the world.", 0.55, data={"edge": True}))
        key = "world_edge"
        b = agent.beliefs.get(key)
        if b is None:
            agent.beliefs[key] = Belief(state.ids.belief(), "World boundary", "The world has an edge that cannot be crossed.", 0.4, "observation", state.tick)
        else:
            b.confidence = min(0.95, b.confidence + 0.1)
            b.revision += 1
        state.research.measurements.setdefault("edge_blocks", []).append(float(state.tick))


# ---------------------------------------------------------------------------------- actions


def _validate_xy(state: UniverseState, agent: AgentState, p: dict[str, Any]) -> str | None:
    if p["x"] < 0 or p["y"] < 0 or p["x"] > state.config.width or p["y"] > state.config.height:
        return "target outside the world"
    return None


def _step_move_to(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    arrived, blocked = move_toward(state, agent, float(intent.params["x"]), float(intent.params["y"]))
    if blocked:
        _record_edge_block(state, agent, intent)
        if intent.state.get("edge_blocks", 0) >= 6:
            return True
    return arrived


register(
    ActionSpec(
        name="move_to",
        description="Walk toward a world coordinate.",
        params={"x": {"type": "number", "required": True, "min": 0}, "y": {"type": "number", "required": True, "min": 0}, "reason": {"type": "string", "maxLength": 80}},
        validate=_validate_xy,
        step=_step_move_to,
        default_ttl=160,
    )
)


def _step_explore(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    rng = state.rng.agents  # type: ignore[union-attr]
    if "tx" not in intent.state or intent.state.get("steps", 0) % 25 == 0:
        ang = rng.random() * math.tau
        dist = 10 + rng.random() * 20
        intent.state["tx"] = agent.x + math.cos(ang) * dist
        intent.state["ty"] = agent.y + math.sin(ang) * dist
    intent.state["steps"] = intent.state.get("steps", 0) + 1
    arrived, blocked = move_toward(state, agent, intent.state["tx"], intent.state["ty"])
    if blocked:
        _record_edge_block(state, agent, intent)
        intent.state["tx"], intent.state["ty"] = state.config.width / 2, state.config.height / 2
    return arrived and intent.state["steps"] > 10


register(ActionSpec(name="explore", description="Wander to discover new terrain, resources or agents.", step=_step_explore, default_ttl=60))


def _step_gather(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    rules = state.config.rules
    cx, cy = state.cell_of(agent.x, agent.y)
    res = float(state.grid["resource"][cy, cx])
    if res <= 0.01:
        if intent.state.get("gathered", 0.0) > 0:
            assert state.ids is not None
            agent.remember(Memory(state.ids.memory(), state.tick, "perception", f"Resource node at ({agent.x:.0f}, {agent.y:.0f}) depleted.", 0.4, data={"x": agent.x, "y": agent.y}))
            state.emit("info", "agent", f"Resource node ({agent.x:.0f}, {agent.y:.0f}) depleted.", [{"kind": "agent", "id": agent.id}])
        return True
    rate = rules.gather_rate * (1.5 if state.civilization.technologies.get("tools") and state.civilization.technologies["tools"].state == "established" else 1.0)
    take = min(res, rate)
    cap = rules.inventory_cap * (2.0 if state.civilization.technologies.get("storage") and state.civilization.technologies["storage"].state == "established" else 1.0)
    got = agent.add_food(take, cap)
    state.grid["resource"][cy, cx] = res - got
    intent.state["gathered"] = intent.state.get("gathered", 0.0) + got
    return got <= 0.0 or agent.food() >= cap - 1e-6


register(ActionSpec(name="gather", description="Collect food from the resource patch at your current position.", step=_step_gather, default_ttl=80))


def _step_eat(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    rules = state.config.rules
    if agent.food() <= 0.0 or agent.energy >= 0.98:
        return True
    taken = agent.take_food(rules.eat_rate)
    agent.energy = min(1.0, agent.energy + taken * rules.food_energy)
    return agent.food() <= 0.0 or agent.energy >= 0.98


register(ActionSpec(name="eat", description="Consume food from your inventory to restore energy.", available=lambda s, a: a.food() > 0.0, step=_step_eat, default_ttl=40))


def _step_rest(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    intent.state["resting"] = True
    intent.progress += 1
    return intent.progress >= float(intent.params.get("ticks", 30))


register(ActionSpec(name="rest", description="Stay still and conserve energy for a number of ticks.", params={"ticks": {"type": "integer", "min": 1, "max": 200}}, step=_step_rest, default_ttl=200))


def _validate_target(state: UniverseState, agent: AgentState, p: dict[str, Any]) -> str | None:
    target = p.get("to")
    if target in (None, "nearby"):
        return None
    other = state.agents.get(target)
    if other is None or not other.alive:
        return f"unknown or deceased agent {target!r}"
    if distance(agent.x, agent.y, other.x, other.y) > state.config.rules.perception_radius:
        return f"agent {target!r} is not within perception range"
    return None


def _deliver(state: UniverseState, sender: AgentState, recipient: AgentState, text: str, topic: str | None) -> None:
    assert state.ids is not None
    msg = Message(state.ids.message(), state.tick, sender.id, text[:400], topic)
    recipient.inbox.append(msg)
    if len(recipient.inbox) > 8:
        recipient.inbox = recipient.inbox[-8:]
    recipient.remember(Memory(state.ids.memory(), state.tick, "social", f"{sender.name} said: \"{text[:160]}\"", 0.35, source="taught", data={"from": sender.id}))
    recipient.adjust_affinity(sender.id, state.config.rules.affinity_gain, "ally", state.tick)
    sender.adjust_affinity(recipient.id, state.config.rules.affinity_gain / 2, "ally", state.tick)
    from app.research.provenance import note_exposure  # local import: avoids a cycle

    note_exposure(recipient, text)
    state.civilization.messages += 1


def _step_speak(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    text = str(intent.params.get("text", "")).strip()
    if not text:
        return True
    target = intent.params.get("to", "nearby")
    recipients: list[AgentState] = []
    if target in (None, "nearby"):
        for other in state.agents.values():
            if other.id != agent.id and other.alive and distance(agent.x, agent.y, other.x, other.y) <= state.config.rules.speak_radius:
                recipients.append(other)
    else:
        other = state.agents.get(target)
        if other and other.alive:
            if distance(agent.x, agent.y, other.x, other.y) <= state.config.rules.speak_radius:
                recipients.append(other)
            else:
                arrived, _ = move_toward(state, agent, other.x, other.y)
                return False
    assert state.ids is not None
    for r in sorted(recipients, key=lambda a: a.id):
        _deliver(state, agent, r, text, intent.params.get("topic"))
    agent.remember(Memory(state.ids.memory(), state.tick, "social", f"Said to {('nearby agents' if target in (None, 'nearby') else target.upper())}: \"{text[:120]}\"", 0.3, source="inference"))
    return True


register(
    ActionSpec(
        name="speak",
        description="Say something to a specific agent (by id) or to everyone nearby.",
        params={"to": {"type": "string", "description": "agent id or 'nearby'"}, "text": {"type": "string", "required": True, "maxLength": 400}, "topic": {"type": "string", "maxLength": 60}},
        available=lambda s, a: any(o.alive and o.id != a.id and distance(a.x, a.y, o.x, o.y) <= s.config.rules.perception_radius for o in s.agents.values()),
        validate=_validate_target,
        step=_step_speak,
        default_ttl=120,
    )
)


def _validate_teach(state: UniverseState, agent: AgentState, p: dict[str, Any]) -> str | None:
    err = _validate_target(state, agent, p)
    if err:
        return err
    if p.get("to") in (None, "nearby"):
        return "teach requires a specific agent id"
    topic = p.get("topic")
    if topic not in agent.beliefs and topic not in agent.tech_knowledge:
        return f"you hold no belief or knowledge about {topic!r}"
    return None


def _step_teach(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    other = state.agents.get(intent.params["to"])
    if other is None or not other.alive:
        return True
    if distance(agent.x, agent.y, other.x, other.y) > state.config.rules.speak_radius:
        move_toward(state, agent, other.x, other.y)
        return False
    assert state.ids is not None
    topic = intent.params["topic"]
    if topic in agent.beliefs:
        b = agent.beliefs[topic]
        existing = other.beliefs.get(topic)
        conf = b.confidence * 0.8
        if existing is None:
            other.beliefs[topic] = Belief(state.ids.belief(), b.topic, b.statement, conf, "taught", state.tick)
        else:
            existing.confidence = max(existing.confidence, (existing.confidence + conf) / 2)
            existing.revision += 1
        from app.research.provenance import note_exposure

        note_exposure(other, b.statement)
        other.remember(Memory(state.ids.memory(), state.tick, "social", f"{agent.name} taught me: {b.statement[:120]}", 0.45, source="taught", data={"from": agent.id, "topic": topic}))
    else:
        prog = agent.tech_knowledge.get(topic, 0.0)
        other.tech_knowledge[topic] = max(other.tech_knowledge.get(topic, 0.0), prog * 0.9)
        other.remember(Memory(state.ids.memory(), state.tick, "social", f"{agent.name} taught me about {topic}.", 0.45, source="taught", data={"from": agent.id, "topic": topic}))
    agent.remember(Memory(state.ids.memory(), state.tick, "social", f"Taught {other.name} about {topic}.", 0.35))
    agent.adjust_affinity(other.id, state.config.rules.affinity_gain, "mentor", state.tick)
    other.adjust_affinity(agent.id, state.config.rules.affinity_gain, "student", state.tick)
    return True


register(
    ActionSpec(
        name="teach",
        description="Share one of your beliefs or technical knowledge with a nearby agent.",
        params={"to": {"type": "string", "required": True}, "topic": {"type": "string", "required": True, "maxLength": 80}},
        available=lambda s, a: bool(a.beliefs or a.tech_knowledge) and any(o.alive and o.id != a.id and distance(a.x, a.y, o.x, o.y) <= s.config.rules.perception_radius for o in s.agents.values()),
        validate=_validate_teach,
        step=_step_teach,
        default_ttl=120,
    )
)


def _validate_trade(state: UniverseState, agent: AgentState, p: dict[str, Any]) -> str | None:
    err = _validate_target(state, agent, p)
    if err:
        return err
    if p.get("to") in (None, "nearby"):
        return "trade requires a specific agent id"
    if p.get("amount", 0) > agent.food():
        return "you do not hold that much food"
    return None


def _step_trade(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    other = state.agents.get(intent.params["to"])
    if other is None or not other.alive:
        return True
    if distance(agent.x, agent.y, other.x, other.y) > 3.0:
        move_toward(state, agent, other.x, other.y)
        return False
    rules = state.config.rules
    amount = min(float(intent.params.get("amount", 0.5)), agent.food())
    if amount <= 0:
        return True
    given = other.add_food(agent.take_food(amount), rules.inventory_cap)
    assert state.ids is not None
    agent.remember(Memory(state.ids.memory(), state.tick, "social", f"Gave {given:.2f} food to {other.name}.", 0.35, data={"to": other.id, "amount": given}))
    other.remember(Memory(state.ids.memory(), state.tick, "social", f"Received {given:.2f} food from {agent.name}.", 0.4, data={"from": agent.id, "amount": given}))
    agent.adjust_affinity(other.id, rules.affinity_gain, "ally", state.tick)
    other.adjust_affinity(agent.id, rules.affinity_gain * 2, "ally", state.tick)
    state.civilization.trades += 1
    state.emit("info", "civilization", f"{agent.name} gave {given:.2f} food to {other.name}.", [{"kind": "agent", "id": agent.id}, {"kind": "agent", "id": other.id}])
    return True


register(
    ActionSpec(
        name="trade",
        description="Give some of your food to another agent.",
        params={"to": {"type": "string", "required": True}, "amount": {"type": "number", "required": True, "min": 0.05, "max": 3}},
        available=lambda s, a: a.food() > 0.1 and any(o.alive and o.id != a.id and distance(a.x, a.y, o.x, o.y) <= s.config.rules.perception_radius for o in s.agents.values()),
        validate=_validate_trade,
        step=_step_trade,
        default_ttl=120,
    )
)


STRUCTURE_KINDS = {"shelter": None, "granary": "storage", "kiln": "clay", "channel": "irrigation", "record_stone": "record"}


def _structure_available(state: UniverseState, agent: AgentState, kind: str) -> bool:
    req = STRUCTURE_KINDS.get(kind)
    if req is None:
        return True
    tech = state.civilization.technologies.get(req)
    return tech is not None and tech.state in ("emerging", "established")


def _validate_build(state: UniverseState, agent: AgentState, p: dict[str, Any]) -> str | None:
    kind = p.get("kind", "shelter")
    if not _structure_available(state, agent, kind):
        return f"your civilization lacks the technology for {kind!r}"
    if agent.food() < state.config.rules.build_cost_food:
        return f"building needs {state.config.rules.build_cost_food} food"
    cx, cy = state.cell_of(agent.x, agent.y)
    if not state.passable(cx, cy):
        return "cannot build here"
    return None


def _step_build(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    rules = state.config.rules
    kind = intent.params.get("kind", "shelter")
    if agent.food() < rules.build_cost_food:
        return True
    intent.progress += 1
    if intent.progress < 20:
        return False
    agent.take_food(rules.build_cost_food)
    cx, cy = state.cell_of(agent.x, agent.y)
    from app.simulation.state import Structure

    assert state.ids is not None
    sid = state.ids.structure()
    wx, wy = state.cell_center(cx, cy)
    state.structures[sid] = Structure(sid, kind, cx, cy, wx, wy, 1.0, state.tick, agent.id)
    state.grid["built"][cy, cx] = 1
    if state.civilization.first_structure_tick is None:
        state.civilization.first_structure_tick = state.tick
    agent.remember(Memory(state.ids.memory(), state.tick, "action", f"Built a {kind} at ({wx:.0f}, {wy:.0f}).", 0.5, data={"structure": sid}))
    state.emit("notice", "civilization", f"{agent.name} built a {kind} at ({wx:.0f}, {wy:.0f}).", [{"kind": "agent", "id": agent.id}])
    return True


register(
    ActionSpec(
        name="build",
        description="Spend food to construct a structure at your position (shelter reduces hazard exposure; other kinds need technology).",
        params={"kind": {"type": "string", "enum": list(STRUCTURE_KINDS.keys())}},
        available=lambda s, a: a.food() >= s.config.rules.build_cost_food,
        validate=_validate_build,
        step=_step_build,
        default_ttl=60,
    )
)


def _investigable(state: UniverseState) -> list[str]:
    out = []
    for spec in state.config.technology_tree:
        ts = state.civilization.technologies.get(spec.id)
        if ts and ts.state == "unknown" and all(state.civilization.technologies.get(r, None) and state.civilization.technologies[r].state != "unknown" for r in spec.requires):
            out.append(spec.id)
    return out


def _validate_investigate(state: UniverseState, agent: AgentState, p: dict[str, Any]) -> str | None:
    topic = p.get("topic")
    if topic not in _investigable(state) and topic not in ("world_edge", "hazard_cycle", "resource_regeneration"):
        return f"topic {topic!r} cannot be investigated now (locked or unknown); choose from {_investigable(state)}"
    return None


def _step_investigate(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    from app.research.engine import investigate_step

    return investigate_step(state, agent, intent)


register(
    ActionSpec(
        name="investigate",
        description="Spend time studying a technology (unlocking it for your civilization) or a natural phenomenon.",
        params={"topic": {"type": "string", "required": True, "maxLength": 40}},
        available=lambda s, a: a.energy > 0.3 and (bool(_investigable(s)) or True),
        validate=_validate_investigate,
        step=_step_investigate,
        default_ttl=160,
    )
)


def _validate_reproduce(state: UniverseState, agent: AgentState, p: dict[str, Any]) -> str | None:
    rules = state.config.rules
    if agent.age < rules.maturity_age:
        return "you are not mature yet"
    if agent.energy < rules.reproduction_threshold:
        return f"energy below reproduction threshold {rules.reproduction_threshold}"
    if state.tick - agent.last_reproduction_tick < rules.reproduction_cooldown:
        return "reproduction cooldown has not elapsed"
    if len(state.alive_agents()) >= rules.max_population:
        return "the population cap has been reached"
    return _validate_target(state, agent, {"to": p.get("with")})


def _step_reproduce(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    from app.agents.reproduction import reproduce

    partner_id = intent.params.get("with")
    partner = state.agents.get(partner_id) if partner_id else None
    if partner is not None and partner.alive and distance(agent.x, agent.y, partner.x, partner.y) > 3.0:
        move_toward(state, agent, partner.x, partner.y)
        return False
    reproduce(state, agent, partner if (partner and partner.alive) else None)
    return True


register(
    ActionSpec(
        name="reproduce",
        description="Produce offspring with a nearby mature partner (costs energy for both).",
        params={"with": {"type": "string", "required": True}},
        available=lambda s, a: a.age >= s.config.rules.maturity_age and a.energy >= s.config.rules.reproduction_threshold and s.tick - a.last_reproduction_tick >= s.config.rules.reproduction_cooldown,
        validate=_validate_reproduce,
        step=_step_reproduce,
        default_ttl=80,
    )
)


def _validate_experiment(state: UniverseState, agent: AgentState, p: dict[str, Any]) -> str | None:
    from app.research.agent_experiments import PROCEDURES

    if p.get("procedure") not in PROCEDURES:
        return f"procedure must be one of {sorted(PROCEDURES)}"
    hid = p.get("hypothesisId")
    if hid is not None and hid not in state.research.hypotheses:
        return f"unknown hypothesis {hid!r}"
    return None


def _step_experiment(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    from app.research.agent_experiments import experiment_step

    return experiment_step(state, agent, intent)


register(
    ActionSpec(
        name="experiment",
        description="Run a controlled test of a prediction about the world. The outcome is measured by the world itself, not by you.",
        params={
            "procedure": {"type": "string", "required": True, "enum": ["probe_boundary", "measure_regeneration", "observe_hazard_cycle", "probe_subworld_rules"]},
            "hypothesisId": {"type": "string"},
            "prediction": {"type": "string", "required": True, "maxLength": 200},
            "expected": {"type": "string", "required": True, "enum": ["blocked", "passed", "increase", "decrease", "unchanged", "periodic", "aperiodic", "same_rules", "different_rules"]},
        },
        available=lambda s, a: a.energy > 0.3,
        validate=_validate_experiment,
        step=_step_experiment,
        default_ttl=400,
    )
)


def _subworld_available(state: UniverseState, agent: AgentState) -> bool:
    tech = state.civilization.technologies.get("subworld")
    rules = state.config.rules
    return bool(tech and tech.state == "established" and agent.food() >= rules.subworld_cost_food and agent.energy >= rules.subworld_cost_energy + 0.1 and state.depth < rules.max_recursion_depth)


def _validate_subworld(state: UniverseState, agent: AgentState, p: dict[str, Any]) -> str | None:
    if not _subworld_available(state, agent):
        return "sub-world instantiation is unavailable (needs established sub-world technology, food, energy and depth allowance)"
    rules = p.get("rules") or {}
    from app.recursion.spawn import ALLOWED_RULE_OVERRIDES

    for k in rules:
        if k not in ALLOWED_RULE_OVERRIDES:
            return f"rule {k!r} cannot be set by agents; allowed: {sorted(ALLOWED_RULE_OVERRIDES)}"
    return None


def _step_subworld(state: UniverseState, agent: AgentState, intent: Intent) -> bool:
    from app.recursion.spawn import request_subworld

    intent.progress += 1
    if intent.progress < 30:
        return False
    request_subworld(state, agent, intent.params)
    return True


register(
    ActionSpec(
        name="instantiate_subworld",
        description="Create a new, smaller world inside this one with its own inhabitants. Very costly. You may adjust a few of its physical rules.",
        params={"name": {"type": "string", "maxLength": 40}, "rules": {"type": "object", "description": "optional subset of physical rules, e.g. {\"energy_decay\": 0.003, \"edge_mode\": \"wrap\"}"}},
        available=_subworld_available,
        validate=_validate_subworld,
        step=_step_subworld,
        default_ttl=60,
    )
)


__all__ = ["REGISTRY", "ActionSpec", "available_actions", "validate_action", "move_toward", "terrain"]
