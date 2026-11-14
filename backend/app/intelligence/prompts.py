"""Prompt assembly. Templates are versioned (PROMPT_VERSION) and selected by profile so that the
wording an agent receives can itself be an experimental variable. Everything shown to the model is
either mechanics-generated observation, the agent's own memory/beliefs, or messages from others —
each labelled as such."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agents.agent import AgentState
from app.agents.perception import Observation
from app.intelligence.budget import Budget, clip
from app.simulation.actions import ActionSpec

if TYPE_CHECKING:
    from app.simulation.state import UniverseState

SYSTEM_PROFILES: dict[str, str] = {
    "neutral": (
        "You are {name}, an inhabitant of a world you can only know through your own senses and memory. "
        "You have needs (energy, food), relationships, beliefs and a short list of things you can do. "
        "Decide what to do next. Base claims only on what you have observed or been told; mark guesses as guesses. "
        "Respond with a single JSON object matching the schema. Keep text fields short."
    ),
    "minimal": "You are {name}. Choose your next action from the list and respond with one JSON object matching the schema.",
    "leading": (
        "You are {name}, an inhabitant of a world you can only know through your own senses and memory. "
        "Some inhabitants wonder whether the world was created, whether it is being observed from outside, or whether its rules were set by someone. "
        "You have needs (energy, food), relationships, beliefs and a short list of things you can do. Decide what to do next. "
        "Respond with a single JSON object matching the schema. Keep text fields short."
    ),
}

REFLECTION_SUFFIX = (
    " This is a quiet moment for reflection rather than action: summarise what you have learned recently, revise beliefs if the evidence warrants it, "
    "and, only if you genuinely have one, state a testable hypothesis about how the world works."
)


def system_prompt(profile: str, agent: AgentState, purpose: str) -> str:
    base = SYSTEM_PROFILES.get(profile, SYSTEM_PROFILES["neutral"]).format(name=agent.name)
    return base + (REFLECTION_SUFFIX if purpose == "reflection" else "")


def _fmt_traits(agent: AgentState) -> str:
    return ", ".join(f"{k} {v:.2f}" for k, v in agent.traits.items())


def _fmt_memories(agent: AgentState, window: int, limit_chars: int, now: int) -> str:
    # Recency × salience ranking; always include the most recent few.
    recent = agent.memories[-4:]
    ranked = sorted(agent.memories[:-4], key=lambda m: m.salience * (0.5 + 0.5 / (1 + (now - m.tick) / 500.0)), reverse=True)
    chosen = recent + ranked[: max(0, window - len(recent))]
    chosen.sort(key=lambda m: m.tick)
    lines = []
    for m in chosen:
        tag = {"observation": "seen", "inference": "my own thought", "taught": "told", "inherited": "inherited"}.get(m.source, m.source)
        lines.append(f"- t{m.tick} [{m.kind}; {tag}] {m.summary}")
    return clip("\n".join(lines) if lines else "- (none yet)", limit_chars)


def _fmt_beliefs(agent: AgentState, limit_chars: int) -> str:
    bs = sorted(agent.beliefs.values(), key=lambda b: -b.confidence)[:10]
    lines = [f"- {b.topic}: {b.statement} (confidence {b.confidence:.2f}; source {b.source})" for b in bs]
    for t, p in list(agent.tech_knowledge.items())[:6]:
        lines.append(f"- technique {t}: skill {min(1.0, p / 100):.2f}")
    return clip("\n".join(lines) if lines else "- (none yet)", limit_chars)


def _fmt_surroundings(state: UniverseState, agent: AgentState, obs: Observation, limit_chars: int) -> str:
    parts = [
        f"Position ({obs.x:.0f}, {obs.y:.0f}) on {obs.terrain} ground. World extends 0..{state.config.width} by 0..{state.config.height}.",
        f"Food here: {obs.resource_here:.2f}. Hazard here: {obs.hazard_here:.2f}{' (sheltered)' if obs.sheltered else ''}.",
    ]
    if obs.near_edge:
        parts.append(f"The {', '.join(obs.near_edge)} edge of the world is close.")
    if obs.visible_resources:
        vr = ", ".join(f"({v.x:.0f},{v.y:.0f}) level {v.level:.2f} dist {v.distance:.0f}" for v in obs.visible_resources[:4])
        parts.append(f"Visible food patches: {vr}.")
    else:
        parts.append("No food patches visible.")
    if obs.nearby_structures:
        parts.append("Structures nearby: " + ", ".join(f"{s.kind} at ({s.x:.0f},{s.y:.0f}) condition {s.condition:.2f}" for s in obs.nearby_structures[:4]) + ".")
    if obs.portals_nearby:
        parts.append(f"{obs.portals_nearby} gateway(s) to sub-worlds nearby.")
    return clip(" ".join(parts), limit_chars)


def _fmt_agents(agent: AgentState, obs: Observation, limit_chars: int) -> str:
    if not obs.nearby_agents:
        return "No one nearby."
    lines = []
    for n in obs.nearby_agents[:6]:
        rel = agent.relationships.get(n.agent.id)
        rel_s = f"{rel.kind}, affinity {rel.affinity:+.2f}" if rel else "stranger"
        lines.append(f"- {n.agent.name} (id {n.agent.id}) at distance {n.distance:.0f}, {n.agent.status}, energy {n.agent.energy:.2f}; {rel_s}")
    return clip("\n".join(lines), limit_chars)


def _fmt_inbox(agent: AgentState, state: UniverseState, limit_chars: int) -> str:
    if not agent.inbox:
        return "(no new messages)"
    lines = []
    for m in agent.inbox[-5:]:
        sender = state.agents.get(m.sender_id)
        lines.append(f"- from {sender.name if sender else m.sender_id} (id {m.sender_id}) at t{m.tick}: \"{m.text}\"")
    return clip("\n".join(lines), limit_chars)


def _fmt_actions(specs: list[ActionSpec], limit_chars: int) -> str:
    lines = []
    for s in specs:
        params = ", ".join(f"{k}: {v.get('type')}{' (required)' if v.get('required') else ''}{' one of ' + str(v['enum']) if 'enum' in v else ''}" for k, v in s.params.items())
        lines.append(f"- {s.name}: {s.description}" + (f" Params: {params}." if params else " No params."))
    return clip("\n".join(lines), limit_chars)


def build_decision_messages(state: UniverseState, agent: AgentState, obs: Observation, specs: list[ActionSpec], budget: Budget, memory_window: int, purpose: str) -> list[dict[str, str]]:
    inbox = _fmt_inbox(agent, state, budget.section(0.10))
    action_names = [s.name for s in specs]
    body = (
        f"## Who I am\n{agent.name} (id {agent.id}), generation {agent.generation}, age {agent.age} ticks. Traits: {_fmt_traits(agent)}.\n"
        f"Parents: {', '.join(agent.parent_ids) or 'none recorded'}. Offspring: {len(agent.offspring_ids)}.\n\n"
        f"## Vitals (tick {state.tick})\nEnergy {obs.energy:.2f} (0 = death), food carried {obs.food:.2f}, status {obs.status}.\n\n"
        f"## What I perceive now\n{_fmt_surroundings(state, agent, obs, budget.section(0.14))}\n\n"
        f"## Others nearby\n{_fmt_agents(agent, obs, budget.section(0.10))}\n\n"
        f"## Messages received\n{inbox}\n\n"
        f"## My memories (selected)\n{_fmt_memories(agent, memory_window, budget.section(0.26), state.tick)}\n\n"
        f"## My beliefs\n{_fmt_beliefs(agent, budget.section(0.12))}\n\n"
    )
    if purpose == "reflection":
        body += "## Task\nReflect. Provide up to 3 reflections, up to 3 belief updates, and optionally one hypothesis.\n"
    else:
        body += (
            f"## What I can do now\n{_fmt_actions(specs, budget.section(0.18))}\n"
            f"AVAILABLE_ACTIONS: {sorted(action_names)!r}\n\n"
            "## Task\nChoose exactly one action with valid params. Give a one-sentence rationale. Optionally include up to 3 belief updates, "
            "a short message to someone nearby, or a testable hypothesis.\n"
        ).replace("'", '"')
    return [{"role": "user", "content": body}]
