from __future__ import annotations

import time


def test_health_and_version(client) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["engineVersion"] and "inference" in body
    assert client.get("/api/version").json()["engineVersion"] == body["engineVersion"]


def test_universe_lifecycle(client) -> None:
    r = client.post("/api/universes", json={"name": "Api", "seed": "s1", "start": False, "config": {"width": 96, "height": 64}})
    assert r.status_code == 201
    u = r.json()
    uid = u["id"]
    assert u["code"] == "U-00" and u["status"] == "paused" and u["clock"]["tick"] == 0
    assert client.post(f"/api/universes/{uid}/command", json={"type": "step", "ticks": 50}).json()["accepted"]
    assert client.get(f"/api/universes/{uid}").json()["clock"]["tick"] == 50
    snap = client.get(f"/api/universes/{uid}/snapshot").json()
    assert snap["width"] == 96 and snap["height"] == 64
    # Terrain cells are indices (the viewport multiplies by cellSize); entities are world units.
    assert snap["cellSize"] == 8 and len(snap["terrain"]) == (96 // 8) * (64 // 8)
    assert all(0 <= c["x"] < 12 and 0 <= c["y"] < 8 for c in snap["terrain"])
    assert all(0 <= e["x"] <= 96 and 0 <= e["y"] <= 64 for e in snap["entities"])
    kinds = {e["kind"] for e in snap["entities"]}
    assert "agent" in kinds and kinds <= {"agent", "structure", "resource", "portal"}
    agents = client.get(f"/api/universes/{uid}/agents").json()
    assert agents and agents[0]["universeId"] == uid
    aid = agents[0]["id"]
    assert client.get(f"/api/agents/{aid}").status_code == 200
    assert client.get(f"/api/agents/{aid}/memory").status_code == 200
    assert client.get(f"/api/agents/{aid}/decisions").status_code == 200
    assert client.get(f"/api/universes/{uid}/civilization").json()["universeId"] == uid
    assert client.get(f"/api/universes/{uid}/events").json()
    assert client.get("/api/events?limit=3").status_code == 200
    assert client.get(f"/api/universes/{uid}/config").json()["config"]["seed"] == "s1"
    assert client.post(f"/api/universes/{uid}/archive").json()["status"] == "archived"


def test_not_found_uses_detail(client) -> None:
    r = client.get("/api/universes/u-9999")
    assert r.status_code == 404 and "detail" in r.json()
    assert client.get("/api/agents/a-99-0001").status_code == 404
    assert client.get("/api/experiments/exp-999").status_code == 404
    assert client.get("/api/research/hypotheses/h-99-0001").status_code == 404


def test_invalid_config_is_422(client) -> None:
    r = client.post("/api/universes", json={"name": "bad", "config": {"rules.nonsense": 1}})
    assert r.status_code == 422


def test_settings_roundtrip(client) -> None:
    s = client.get("/api/settings").json()
    assert s["providers"][0]["adapter"] == "ollama"
    s["reasoning"]["temperature"] = 0.42
    assert client.put("/api/settings", json=s).json()["reasoning"]["temperature"] == 0.42
    assert client.get("/api/settings").json()["reasoning"]["temperature"] == 0.42
    pid = s["providers"][0]["id"]
    assert client.put(f"/api/settings/providers/{pid}/credential", json={"credential": "k"}).json()["providers"][0]["hasCredential"]
    assert client.put("/api/settings/providers/nope/credential", json={"credential": "k"}).status_code == 404
    assert client.get("/api/inference/status").json()["reachable"] is True
    assert client.get("/api/inference/models").status_code == 200


def test_research_endpoints(client) -> None:
    uid = client.post("/api/universes", json={"name": "R", "seed": "r", "config": {"width": 96, "height": 64}}).json()["id"]
    h = client.post("/api/research/hypotheses", json={"universeId": uid, "title": "Operator idea", "statement": "Things happen", "confidence": 0.3}).json()
    assert h["proposedBy"]["kind"] == "operator" and h["provenance"]["classification"] == "operator"
    assert client.get(f"/api/research/hypotheses/{h['id']}").json()["id"] == h["id"]
    assert client.post(f"/api/research/hypotheses/{h['id']}/withdraw").json()["state"] == "withdrawn"
    assert any(x["id"] == h["id"] for x in client.get("/api/research/hypotheses").json())


def test_experiment_flow(client) -> None:
    body = {"name": "Hazard", "objective": "test", "variables": [{"key": "rules.hazard_amplitude", "label": "h", "control": 0.2, "treatment": 0.9}], "durationTicks": 40, "mode": "lockstep", "baseConfig": {"width": 96, "height": 64, "initial_population": 3, "reasoning.enabled": False}}
    e = client.post("/api/experiments", json=body).json()
    assert e["status"] == "draft" and e["reproducibility"]["seed"]
    e = client.patch(f"/api/experiments/{e['id']}", json={"replicates": 1, "objective": "updated"}).json()
    assert e["objective"] == "updated"
    e = client.post(f"/api/experiments/{e['id']}/runs").json()
    assert e["status"] == "running" and len(e["runs"]) == 1
    run = e["runs"][0]
    assert run["controlUniverseId"] and run["treatmentUniverseId"] and len(run["universeIds"]) == 2
    deadline = time.time() + 20
    while time.time() < deadline:
        e = client.get(f"/api/experiments/{e['id']}").json()
        if e["status"] == "complete":
            break
        time.sleep(0.1)
    assert e["status"] == "complete"
    m = e["runs"][0]["metrics"]
    assert m["control"]["tick"] >= 40 and m["treatment"]["tick"] >= 40
    assert e["reproducibility"]["deterministic"] is True
    ctrl = client.get(f"/api/universes/{run['controlUniverseId']}").json()
    assert ctrl["lineage"]["createdBy"]["kind"] == "experiment"
    assert client.delete(f"/api/experiments/{e['id']}").status_code == 204


def test_websocket_hello_and_frames(client) -> None:
    uid = client.post("/api/universes", json={"name": "W", "seed": "w", "config": {"width": 96, "height": 64}}).json()["id"]
    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["engineVersion"]
        ws.send_json({"type": "subscribe", "universeIds": [uid]})
        client.post(f"/api/universes/{uid}/command", json={"type": "step", "ticks": 5})
        types = set()
        for _ in range(4):
            m = ws.receive_json()
            types.add(m["type"])
            if m["type"] == "snapshot":
                assert m["snapshot"]["universeId"] == uid
            if m["type"] == "clock":
                assert m["universeId"] == uid and "tick" in m["clock"]
        assert types & {"clock", "snapshot", "event", "universe.changed"}
