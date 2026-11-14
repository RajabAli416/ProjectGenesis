"""Event-driven agent cognition.

The simulation advances with ordinary mechanics; this module decides *when* an agent needs a model
decision, assembles the prompt from mechanics-generated observations and the agent's own memory,
submits it to the shared inference service, validates the structured answer against the agent's
affordances, and installs the accepted intent for the deterministic executors to carry out. Model
output never mutates state directly. Every request/response and every decision is recorded."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.agents.agent import AgentState, Intent, Memory
from app.agents.perception import observe
from app.core.errors import ProviderError, ProviderUnavailable
from app.core.timeutil import now_iso
from app.intelligence import prompts
from app.intelligence.budget import Budget, RatioEstimator
from app.intelligence.parsing import ParseError, parse_as
from app.intelligence.providers.base import InferenceRequest, Provider, ProviderResponse
from app.intelligence.schemas import DecisionResponse, ReflectionResponse, decision_schema, reflection_schema
from app.intelligence.service import InferenceService
from app.persistence.store import Store
from app.research import provenance
from app.research.engine import apply_belief_updates, propose_hypothesis
from app.simulation.actions import REGISTRY, available_actions, validate_action
from app.version import PROMPT_VERSION

if TYPE_CHECKING:
    from app.simulation.state import UniverseState

log = logging.getLogger(__name__)


@dataclass
class ResolvedModel:
    provider: Provider
    model: str
    model_ref: str | None
    temperature: float
    num_ctx: int
    think_decisions: bool
    think_reflection: bool
    timeout_s: float
    prompt_profile: str


Resolver = Callable[["UniverseState"], Awaitable[ResolvedModel | None]]


class CognitionScheduler:
    """Decides which agents need a model decision at the end of a tick."""

    @staticmethod
    def collect(state: UniverseState) -> list[tuple[str, str, int]]:
        r = state.config.reasoning
        if not r.enabled:
            return []
        out: list[tuple[str, str, int]] = []
        for aid in sorted(state.agents):
            a = state.agents[aid]
            if not a.alive or a.pending_request:
                continue
            since = state.tick - a.last_decision_tick
            if since < r.min_decision_gap:
                continue
            if r.reflection_interval > 0 and state.tick - a.last_reflection_tick >= r.reflection_interval and len(a.memories) >= 3:
                out.append((aid, "reflection", 7))
                continue
            reflex_or_idle = a.intent is None or a.intent.policy == "reflex"
            if not reflex_or_idle:
                continue
            needy = a.energy < r.need_threshold and (a.intent is None or a.intent.type not in ("eat", "gather"))
            if needy:
                out.append((aid, "decision", 2))
            elif a.inbox:
                out.append((aid, "decision", 3))
            elif a.salient_since_decision >= 1.0:
                out.append((aid, "decision", 4))
            elif since >= r.decision_interval:
                out.append((aid, "decision", 5))
        return out


class CognitionEngine:
    def __init__(self, service: InferenceService, store: Store, resolver: Resolver, max_repair_attempts: int = 1) -> None:
        self.service = service
        self.store = store
        self.resolver = resolver
        self.max_repair_attempts = max_repair_attempts
        self.ratio = RatioEstimator()
        self.invalid = 0
        self.accepted = 0

    # ------------------------------------------------------------------ main cycle

    async def run(self, state: UniverseState, agent_id: str, purpose: str, priority: int) -> None:
        agent = state.agents.get(agent_id)
        if agent is None or not agent.alive or agent.pending_request:
            return
        resolved = await self.resolver(state)
        if resolved is None:
            return
        agent.pending_request = True
        agent.last_decision_tick = state.tick
        tick_requested = state.tick
        try:
            await self._cycle(state, agent, purpose, priority, resolved, tick_requested)
        except Exception:  # noqa: BLE001
            log.exception("cognition cycle failed for %s", agent_id)
        finally:
            agent.pending_request = False
            agent.salient_since_decision = 0.0
            if purpose == "reflection":
                agent.last_reflection_tick = state.tick

    async def _cycle(self, state: UniverseState, agent: AgentState, purpose: str, priority: int, rm: ResolvedModel, tick_requested: int) -> None:
        r = state.config.reasoning
        obs = observe(state, agent)
        specs = available_actions(state, agent) if purpose == "decision" else []
        num_predict = 600 if purpose == "reflection" else 400
        budget = Budget(rm.num_ctx, num_predict, chars_per_token=self.ratio.value)
        system = prompts.system_prompt(rm.prompt_profile, agent, purpose)
        messages = prompts.build_decision_messages(state, agent, obs, specs, budget, r.memory_window, purpose)
        schema = reflection_schema() if purpose == "reflection" else decision_schema([s.name for s in specs])
        # Exposure: the agent is now exposed to the lexicon terms present in the wording we gave it
        # (system prompt + action descriptions), but not to its own memories.
        provenance.note_exposure(agent, system + " " + " ".join(s.description for s in specs))

        seed = state.rng.inference.getrandbits(31)  # type: ignore[union-attr]
        req = InferenceRequest(
            universe_id=state.id,
            agent_id=agent.id,
            tick=tick_requested,
            purpose=purpose,
            system=system,
            messages=messages,
            json_schema=schema,
            model=rm.model,
            temperature=rm.temperature,
            num_ctx=rm.num_ctx,
            num_predict=num_predict,
            seed=seed,
            think=(rm.think_reflection if purpose == "reflection" else rm.think_decisions),
            priority=priority,
            timeout_s=rm.timeout_s,
            prompt_profile=rm.prompt_profile,
            prompt_version=PROMPT_VERSION,
        )
        agent.model_ref = rm.model_ref
        state.model_ref = state.model_ref or rm.model_ref

        attempt = 0
        request_id: int | None = None
        parsed: DecisionResponse | ReflectionResponse | None = None
        last_error: str | None = None
        raw_text: str | None = None
        resp: ProviderResponse | None = None
        while attempt <= self.max_repair_attempts:
            attempt += 1
            request_id = await asyncio.to_thread(self.store.insert_inference_request, self._request_row(req, rm, attempt, "pending"))
            try:
                resp = await self.service.submit(req)
            except (ProviderUnavailable, ProviderError, TimeoutError) as e:
                status = "timeout" if isinstance(e, (TimeoutError, asyncio.TimeoutError)) else "error"
                await asyncio.to_thread(self.store.update_inference_request, request_id, {"status": status, "validation_error": str(e)[:500]})
                await self._record_decision(state, agent, purpose, tick_requested, None, False, f"provider {status}: {str(e)[:200]}", None, request_id, rm.model_ref)
                return
            raw_text = resp.text
            prompt_chars = len(system) + sum(len(m["content"]) for m in messages)
            self.ratio.observe(prompt_chars, resp.prompt_tokens)
            validation_error: str | None = None
            try:
                parsed = parse_as(resp.text, ReflectionResponse if purpose == "reflection" else DecisionResponse)
                if isinstance(parsed, DecisionResponse):
                    validation_error = validate_action(state, agent, parsed.action.model_dump())
            except ParseError as e:
                validation_error = f"parse: {e}"
            valid = validation_error is None
            await asyncio.to_thread(
                self.store.update_inference_request,
                request_id,
                {
                    "status": "ok" if valid else "invalid",
                    "raw_response": resp.text,
                    "parsed_json": parsed.model_dump(by_alias=True) if (parsed is not None and valid) else None,
                    "valid": valid,
                    "validation_error": validation_error,
                    "prompt_tokens": resp.prompt_tokens,
                    "completion_tokens": resp.completion_tokens,
                    "timings_json": resp.timings,
                    "latency_ms": resp.timings.get("wall_ms"),
                    "model_ref": rm.model_ref,
                },
            )
            if valid:
                break
            self.invalid += 1
            last_error = validation_error
            parsed = None
            # Repair turn: show the model its own output and the validation error.
            req.messages = messages + [{"role": "assistant", "content": resp.text[:1500]}, {"role": "user", "content": f"That response was invalid: {validation_error}. Respond again with one JSON object that satisfies the schema and the action list."}]
            req.seed = state.rng.inference.getrandbits(31)  # type: ignore[union-attr]

        if parsed is None:
            await self._record_decision(state, agent, purpose, tick_requested, None, False, f"invalid after {attempt} attempt(s): {last_error}", None, request_id, rm.model_ref)
            return

        if not agent.alive:
            await self._record_decision(state, agent, purpose, tick_requested, parsed.model_dump(by_alias=True), False, "agent died before the decision arrived", None, request_id, rm.model_ref)
            return

        if isinstance(parsed, DecisionResponse):
            await self._apply_decision(state, agent, parsed, tick_requested, request_id, rm, raw_text or "")
        else:
            await self._apply_reflection(state, agent, parsed, tick_requested, request_id, rm)

    # ------------------------------------------------------------------ apply

    async def _apply_decision(self, state: UniverseState, agent: AgentState, d: DecisionResponse, tick_requested: int, request_id: int | None, rm: ResolvedModel, raw: str) -> None:
        assert state.ids is not None
        spec = REGISTRY[d.action.type]
        intent = Intent(d.action.type, dict(d.action.params), state.tick, "model", ttl=spec.default_ttl)
        agent.intent = intent
        agent.policy = "model"
        agent.decisions_total += 1
        agent.decisions_model += 1
        agent.inbox.clear()
        self.accepted += 1
        if d.rationale:
            agent.remember(Memory(state.ids.memory(), state.tick, "reflection", f"Decided to {d.action.type}: {provenance.squash(d.rationale, 200)}", 0.3, source="inference"))
        if d.belief_updates:
            apply_belief_updates(state, agent, [b.model_dump() for b in d.belief_updates])
        if d.message and d.message.text.strip():
            from app.simulation.actions import _deliver  # noqa: PLC0415

            recipients = []
            if d.message.to in ("nearby", "", None):
                recipients = [o for o in state.agents.values() if o.id != agent.id and o.alive and ((o.x - agent.x) ** 2 + (o.y - agent.y) ** 2) ** 0.5 <= state.config.rules.speak_radius]
            elif d.message.to in state.agents and state.agents[d.message.to].alive:
                o = state.agents[d.message.to]
                if ((o.x - agent.x) ** 2 + (o.y - agent.y) ** 2) ** 0.5 <= state.config.rules.perception_radius:
                    recipients = [o]
            for r_ in sorted(recipients, key=lambda a: a.id):
                _deliver(state, agent, r_, d.message.text, None)
        if d.hypothesis and d.hypothesis.title.strip() and d.hypothesis.statement.strip():
            propose_hypothesis(state, agent, d.hypothesis.title, d.hypothesis.statement, d.hypothesis.confidence)
        decision_id = await self._record_decision(state, agent, "decision", tick_requested, d.model_dump(by_alias=True)["action"], True, None, d.rationale, request_id, rm.model_ref)
        intent.decision_id = decision_id
        state.emit("info", "agent", f"{agent.name} decided to {d.action.type} ({'model'}).", [{"kind": "agent", "id": agent.id}], data={"decisionId": decision_id})

    async def _apply_reflection(self, state: UniverseState, agent: AgentState, r: ReflectionResponse, tick_requested: int, request_id: int | None, rm: ResolvedModel) -> None:
        assert state.ids is not None
        for refl in r.reflections[:3]:
            agent.remember(Memory(state.ids.memory(), state.tick, "reflection", provenance.squash(refl.summary, 240), max(0.1, min(1.0, refl.salience)), source="inference"))
        if r.belief_updates:
            apply_belief_updates(state, agent, [b.model_dump() for b in r.belief_updates])
        if r.hypothesis and r.hypothesis.title.strip() and r.hypothesis.statement.strip():
            propose_hypothesis(state, agent, r.hypothesis.title, r.hypothesis.statement, r.hypothesis.confidence)
        agent.decisions_total += 1
        agent.decisions_model += 1
        await self._record_decision(state, agent, "reflection", tick_requested, None, True, None, "; ".join(x.summary for x in r.reflections)[:600], request_id, rm.model_ref)

    async def _record_decision(self, state: UniverseState, agent: AgentState, purpose: str, tick_requested: int, action: dict[str, Any] | None, accepted: bool, reason: str | None, rationale: str | None, request_id: int | None, model_ref: str | None) -> int:
        row = {
            "agent_id": agent.id,
            "universe_id": state.id,
            "request_id": request_id,
            "tick_requested": tick_requested,
            "tick_applied": state.tick if accepted else None,
            "policy": "model",
            "purpose": purpose,
            "action_json": action,
            "accepted": accepted,
            "rejection_reason": reason,
            "rationale": rationale,
            "model_ref": model_ref,
        }
        if not accepted and purpose == "decision":
            agent.remember(Memory(state.ids.memory(), state.tick, "reflection", "My deliberation produced nothing usable; I fell back on instinct.", 0.2, source="inference"))  # type: ignore[union-attr]
        return await asyncio.to_thread(self.store.insert_decision, row)

    # ------------------------------------------------------------------ rows

    @staticmethod
    def _request_row(req: InferenceRequest, rm: ResolvedModel, attempt: int, status: str) -> dict[str, Any]:
        return {
            "universe_id": req.universe_id,
            "agent_id": req.agent_id,
            "tick": req.tick,
            "purpose": req.purpose,
            "priority": req.priority,
            "model_ref": rm.model_ref,
            "prompt_hash": req.prompt_hash(),
            "prompt_version": req.prompt_version,
            "prompt_profile": req.prompt_profile,
            "system_prompt": req.system,
            "messages_json": req.messages,
            "schema_hash": req.schema_hash(),
            "options_json": {**req.options(), "think": req.think, "model": req.model},
            "seed": req.seed,
            "status": status,
            "attempt": attempt,
            "contamination_terms_json": provenance.find_terms(req.system + " " + " ".join(m["content"] for m in req.messages)),
        }


def created_at() -> str:
    return now_iso()
