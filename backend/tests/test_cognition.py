"""Event-driven cognition with the scripted provider: no GPU required."""

from __future__ import annotations

import json

from app.intelligence.providers.base import InferenceRequest
from app.intelligence.providers.scripted import ReplayProvider, ScriptedProvider, available_from_prompt
from app.simulation.host import SimulationHost
from tests.conftest import create_and_step


async def test_scripted_decisions_are_recorded_and_applied(host: SimulationHost, store) -> None:
    uid = await create_and_step(host, 400, seed="cog", **{"reasoning.enabled": True})
    st = host.get(uid)
    decisions = store.list_decisions(universe_id=uid, limit=500)
    assert decisions, "no decisions recorded"
    model_decisions = [d for d, _ in decisions if d.policy == "model" and d.purpose == "decision"]
    assert model_decisions
    assert all(d.accepted for d in model_decisions)
    assert all(d.action_json and d.action_json["type"] in ("eat", "gather", "explore", "rest") for d in model_decisions)
    reqs = store.list_inference_requests(uid, None, 500)
    assert reqs and all(r.status == "ok" and r.valid for r in reqs)
    assert all(r.system_prompt and r.messages_json and r.prompt_hash and r.seed is not None for r in reqs)
    assert any(a.decisions_model > 0 for a in st.agents.values())
    # Model never touches state directly: every applied decision became an intent processed by mechanics.
    assert all(d.tick_applied is not None for d in model_decisions)


async def test_invalid_output_falls_back_to_reflex(host: SimulationHost, store) -> None:
    host.scripted_override = ScriptedProvider(script=lambda req: "this is not json at all")
    await host.refresh_provider()
    uid = await create_and_step(host, 300, seed="bad", **{"reasoning.enabled": True})
    st = host.get(uid)
    reqs = store.list_inference_requests(uid, None, 500)
    assert reqs and all(r.status == "invalid" for r in reqs)
    decisions = [d for d, _ in store.list_decisions(universe_id=uid, limit=500) if d.policy == "model"]
    assert decisions and all(not d.accepted for d in decisions)
    assert all(a.decisions_model == 0 for a in st.agents.values())
    assert st.tick == 300  # universe kept running on reflexes


async def test_unavailable_action_is_rejected(host: SimulationHost, store) -> None:
    host.scripted_override = ScriptedProvider(script=lambda req: {"action": {"type": "instantiate_subworld", "params": {"name": "x"}}, "rationale": "cheat", "beliefUpdates": []})
    await host.refresh_provider()
    uid = await create_and_step(host, 200, seed="cheat", **{"reasoning.enabled": True})
    reqs = store.list_inference_requests(uid, None, 500)
    assert reqs and all(r.status == "invalid" and "instantiate_subworld" in (r.validation_error or "") for r in reqs)


async def test_replay_reproduces_run(host: SimulationHost, store) -> None:
    uid_a = await create_and_step(host, 500, seed="replay", **{"reasoning.enabled": True})
    hash_a = host.state_hash(uid_a)
    n_reqs = len(store.list_inference_requests(uid_a, None, 10_000))
    assert n_reqs > 0

    scripted = host.scripted_override
    scripted.calls = 0
    host.scripted_override = ReplayProvider(host._replay_lookup)  # noqa: SLF001
    await host.refresh_provider()
    uid_b = await create_and_step(host, 500, seed="replay", **{"reasoning.enabled": True})
    assert scripted.calls == 0
    assert host.state_hash(uid_b) == hash_a
    reqs_b = store.list_inference_requests(uid_b, None, 10_000)
    assert len(reqs_b) == n_reqs and all(r.status == "ok" for r in reqs_b)


async def test_lockstep_waits_for_decisions(host: SimulationHost, store) -> None:
    uid = await create_and_step(host, 300, seed="lock", **{"reasoning.enabled": True})
    for d, _ in store.list_decisions(universe_id=uid, limit=500):
        if d.policy == "model" and d.accepted and d.purpose == "decision":
            assert d.tick_applied == d.tick_requested


async def test_per_agent_memory_isolation(host: SimulationHost) -> None:
    uid = await create_and_step(host, 400, seed="mem", **{"reasoning.enabled": True})
    st = host.get(uid)
    agents = list(st.agents.values())
    ids = [{m.id for m in a.memories} for a in agents]
    for i, a in enumerate(ids):
        for j, b in enumerate(ids):
            if i != j:
                assert not (a & b)


def test_available_actions_parsed_from_prompt() -> None:
    req = InferenceRequest("u", "a", 0, "decision", "sys", [{"role": "user", "content": 'blah\nAVAILABLE_ACTIONS: ["eat", "rest"]\n'}], {}, "m")
    assert available_from_prompt(req) == ["eat", "rest"]


async def test_reflection_records_memories(host: SimulationHost, store) -> None:
    uid = await create_and_step(host, 900, seed="refl", **{"reasoning.enabled": True, "reasoning.reflection_interval": 300})
    st = host.get(uid)
    refl = [d for d, _ in store.list_decisions(universe_id=uid, limit=1000) if d.purpose == "reflection"]
    assert refl, "no reflections"
    assert any(m.source == "inference" and "Scripted reflection" in m.summary for a in st.agents.values() for m in a.memories)
    dto = host.agent_dto(st, sorted(st.agents)[0], 10)
    assert json.dumps(dto.model_dump(by_alias=True))  # serialisable
