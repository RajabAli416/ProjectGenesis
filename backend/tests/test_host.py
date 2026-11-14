from __future__ import annotations

import pytest

from app.api import schemas as S
from app.intelligence.providers.scripted import ScriptedProvider
from app.simulation.host import SimulationHost
from tests.conftest import create_and_step, wait_until


async def test_create_step_persist_and_restore(host: SimulationHost, settings, store) -> None:
    uid = await create_and_step(host, 250, seed="restore-me", **{"reasoning.enabled": False})
    st = host.get(uid)
    assert st.tick == 250
    h1 = host.state_hash(uid)
    digest = await host.snapshot(st)
    assert digest
    assert store.list_events(uid, 5)
    await host.stop()

    # New host on the same store restores the universe at the snapshot tick, paused.
    h2 = SimulationHost(settings, store)
    h2.scripted_override = ScriptedProvider()
    await h2.start()
    try:
        r = h2.get(uid)
        assert r.tick == 250 and r.status == "paused"
        assert h2.state_hash(uid) == h1
        # ...and keeps stepping.
        assert (await h2.command(uid, {"type": "step", "ticks": 100})).accepted
        assert r.tick == 350
    finally:
        await h2.stop()


async def test_commands(host: SimulationHost) -> None:
    st = await host.create_universe(S.CreateUniverseRequest(name="C", seed="c", start=False, config={"width": 96, "height": 64}))
    assert (await host.command(st.id, {"type": "resume"})).accepted
    assert not (await host.command(st.id, {"type": "step", "ticks": 1})).accepted  # must pause first
    assert (await host.command(st.id, {"type": "setSpeed", "speed": 2.0})).accepted and st.speed == 2.0
    assert not (await host.command(st.id, {"type": "setSpeed", "speed": 999})).accepted
    assert (await host.command(st.id, {"type": "pause"})).accepted
    assert not (await host.command(st.id, {"type": "bogus"})).accepted
    assert not (await host.command("u-9999", {"type": "pause"})).accepted
    await host.archive(st.id)
    assert st.status == "archived"
    assert not (await host.command(st.id, {"type": "resume"})).accepted


async def test_runner_advances_without_clients(host: SimulationHost) -> None:
    st = await host.create_universe(S.CreateUniverseRequest(name="R", seed="r", start=True, config={"width": 96, "height": 64, "reasoning.enabled": False}))
    await wait_until(lambda: st.tick >= 10, timeout=10)
    assert st.status == "running"
    assert host.rate_of(st.id) >= 0


async def test_settings_apply_and_credentials(host: SimulationHost) -> None:
    s = host.operator.model_copy(deep=True)
    s.reasoning.temperature = 0.33
    s.simulation.initial_population = 7
    out = await host.apply_settings(s)
    assert out.reasoning.temperature == 0.33
    assert host.base_config().initial_population == 7
    assert host.set_credential(s.providers[0].id, "sk-test")
    assert host.operator.providers[0].has_credential
    assert not host.set_credential("nope", "x")


async def test_bad_config_rejected(host: SimulationHost) -> None:
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError
        await host.create_universe(S.CreateUniverseRequest(name="bad", config={"rules.not_a_rule": 1}))
