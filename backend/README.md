# RECURSION — backend

Simulation engine, agent cognition, civilization/research mechanics and the REST + WebSocket API for the RECURSION artificial-life research platform. Python 3.12, FastAPI, SQLAlchemy 2 + Alembic on SQLite, Ollama-first inference.

The backend is a single asyncio process (a modular monolith): a `SimulationHost` owns every universe, advances their clocks independently of connected browsers, schedules agent deliberation through a prioritised inference queue, and persists snapshots, events, decisions and inference records. The frontend is a pure observer plus operator controls; it never mutates simulation state itself.

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1            # or: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env                  # optional; every value has a default
```

### Ollama prerequisites

Inference is optional: with no reachable provider agents run on their reflex policy and every page still works. For model-driven agents:

1. Install or update Ollama. Qwen3 models need **Ollama ≥ 0.6.6**; per-request thinking control (`think` on/off) needs **≥ 0.9**. `ollama --version` shows what is installed.
2. Pull the default model: `ollama pull qwen3:4b` (≈2.6 GB, Q4_K_M; fits a 4 GB GPU with `num_ctx 4096`).
3. Recommended server environment for a single small GPU: `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1`.
4. Settings → Inference in the UI shows what the engine actually sees (reachable, server version, model resident, queue, latency). If the model is not pulled it says so; nothing is attributed to a model until the provider answers.

Other providers: any OpenAI-compatible endpoint can be added in Settings → Model providers (adapter `openai-compatible`, credential stored server-side only). `scripted` and `replay` adapters exist for deterministic tests and reproduction.

## Run

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- Migrations run automatically on start against `data/recursion.sqlite3` (configurable with `RECURSION_DATA_DIR` / `RECURSION_DB_FILENAME`).
- Universes that existed at shutdown are restored from their last snapshot and come back **paused** (set `RECURSION_AUTOSTART_RESTORED=true` to resume them).
- Interactive API docs: <http://127.0.0.1:8000/api/docs>.
- Frontend: in `frontend/`, `npm run dev` with `VITE_DATA_SOURCE=http` (the default in `.env.development`); Vite proxies `/api` and `/ws` to port 8000.

### Tests and lint

```powershell
python -m pytest -q          # 67 tests: contract vs types.ts, determinism, cognition, civilization, research, recursion, API/WS
ruff check app tests scripts
```

## Configuration

Process-level settings come from `RECURSION_*` environment variables or `backend/.env` (see `.env.example`; defaults in `app/config.py`). Operator settings (providers, reasoning cadence, simulation defaults, persistence) live in the database and are edited from the Settings page (`PUT /api/settings`); they override the process defaults for new universes. Every universe carries its own immutable `UniverseConfig` (seed, rules, reasoning parameters, technology tree, `config_version`) which is persisted with each snapshot and returned by `GET /api/universes/{id}/config`.

## API and WebSocket contract

All routes are under `/api`; DTOs are camelCase and mirror `frontend/src/domain/types.ts` (enforced by `tests/test_contract_types.py`). Errors are `{"detail": "..."}` with 404/409/422/502 as appropriate.

| Area | Routes |
| --- | --- |
| Health | `GET /health` (host status incl. inference), `GET /version` |
| Universes | `GET /universes`, `POST /universes` (201), `GET /universes/{id}`, `/snapshot`, `/agents`, `/civilization`, `/events`, `/config`, `/snapshots`, `/hypotheses`, `POST /universes/{id}/command` (`pause`, `resume`, `step`, `setSpeed`), `POST /universes/{id}/archive` |
| Agents | `GET /agents`, `GET /agents/{id}`, `/memory`, `/decisions` |
| Events | `GET /events` |
| Research | `GET /research/hypotheses`, `GET /research/hypotheses/{id}`, `POST /research/hypotheses` (operator), `POST /research/hypotheses/{id}/withdraw` |
| Experiments | `GET/POST /experiments`, `GET/PATCH/DELETE /experiments/{id}`, `POST /experiments/{id}/runs`, `POST /experiments/{id}/abort` |
| Settings | `GET/PUT /settings`, `PUT /settings/providers/{id}/credential` |
| Inference | `GET /inference/status`, `/models`, `/available`, `/requests`, `/requests/{id}`, `/decisions`, `GET/POST /inference/benchmarks` |

WebSocket `/ws`: the server sends `hello{engineVersion}` first, then `clock{universeId, clock}` for every universe, `event{event}` as events flush, `universe.changed{universeId}` when the catalogue or a universe's status changes, and `snapshot{snapshot}` frames (≈1 Hz) only for universes the client subscribed to with `{"type": "subscribe", "universeIds": [...]}`.

## How the engine works

- **Clock.** Each `UniverseRunner` advances its universe at `tickRate × speed`, sharing the host tick budget (`RECURSION_HOST_TICK_BUDGET`) according to `computeShare`. Mechanics (`app/simulation`, `app/agents`, `app/civilization`, `app/research`) are pure Python per tick, driven by a per-universe seeded RNG. Clocks never wait for browsers.
- **Cognition is event-driven.** `CognitionScheduler` raises triggers (scheduled interval, low energy, incoming message, reflection) → `InferenceService` priority queue (concurrency 1 by default) → prompt built from the agent's *own* memories, beliefs and affordances → JSON-schema-constrained output → Pydantic + affordance validation → one repair turn → reflex fallback. The model never mutates state directly; it only proposes an action that mechanics may reject. In `realtime` mode the clock runs on and decisions apply when they arrive; in `lockstep` mode the clock waits for every decision.
- **Per-agent memory.** Memories carry a `source` (`observation`, `inference`, `taught`, `inherited`), are isolated per agent, and are persisted incrementally.
- **Recursion.** Agents whose civilization has established the `subworld` technology can pay food/energy to `instantiate_subworld`; the child universe gets a derived seed, a compute share, and only the rule overrides in `ALLOWED_RULE_OVERRIDES`.

## Scientific-integrity notes

- **Provenance is recorded, not inferred.** Every inference request stores the model reference (name, digest, quantisation), prompt version, prompt hash, seed, `num_ctx`, `think` flag, raw response, validity and timings. Every decision stores policy (`model`/`reflex`), acceptance and rejection reason. Agent and universe DTOs expose `modelRef`, `engineVersion`, `mechanicsVersion`, `configVersion`.
- **Contamination tracking.** The engine records every existential-lexicon term an agent has been exposed to through prompts or messages. A hypothesis whose claim reuses exposed vocabulary is classified `prompt-exposed`; one tied to mechanics-verified measurements is `evidence-linked`; everything else from a model is `model-originated` and carries a caveat. The UI never presents an exposed claim as an independent discovery.
- **Mechanics-verified evidence.** Evidence rows produced by probes/measurements are flagged `verifiedByMechanics`; model assertions are not.
- **Determinism claims are narrow.** Mechanics are deterministic per seed and the state hash (`state_hash`) is identity-neutral, so same-seed universes compare equal regardless of id or snapshot timing. An experiment is marked `deterministic` **only** when it runs in lockstep with no live model in the loop (reasoning disabled, or the `scripted`/`replay` adapter). Anything involving a live model is reported as non-deterministic.
- **Controls are built in.** `POST /experiments/{id}/runs` instantiates a paired control and treatment universe per replicate with seeds derived from the experiment seed, pauses both at `durationTicks`, and records mechanics-only metrics for each arm.
- **Benchmarks are measured, not assumed.** `scripts/bench_inference.py` and the Settings → Inference button send the real decision schema to the provider and record JSON/schema validity, p50/p95 latency and token rates per model/`num_ctx`/`think` cell.

## Scripts

Run from `backend/` with the venv active. The scripts open the database directly, so they refuse to run while a server is answering on the configured port (override with `--db other.sqlite3` or `--force`).

| Script | Purpose |
| --- | --- |
| `scripts/bench_inference.py` | Benchmark grid over `--num-ctx` × `--think`; persists rows shown in Settings unless `--no-store` |
| `scripts/seed_demo.py` | Create a universe, run N ticks in lockstep, print the state hash; `--expect-hash` turns it into a reproduction check |
| `scripts/replay_run.py <universe>` | Re-run a universe from its recorded inference responses via the `replay` adapter and assert the state hash |

## Layout

```
app/
  api/            schemas.py (camelCase DTOs), routers/ (REST + ws), deps.py
  core/           errors, hashing (canonical JSON, id-neutral hashing), rng, time
  simulation/     config (UniverseConfig/rules), state, terrain, environment, tick, engine, runner, host, snapshot
  agents/         agent state, perception, memory, affordances, reflex policy, actions
  intelligence/   providers/ (ollama, openai_compat, scripted, replay), prompts, schemas, parsing, cognition, scheduler, service, registry, benchmark
  civilization/   messaging, relationships, trade, reproduction, construction, technology, institutions, stage
  research/       hypotheses, evidence, provenance classifier, agent experiments
  experiments/    operator experiments (control/treatment runs, metrics)
  recursion/      subworld instantiation and lineage
  persistence/    models, store (single-writer SQLite), migrations (Alembic)
  observability/  logging
scripts/          bench_inference.py, seed_demo.py, replay_run.py
tests/            pytest suite (asyncio mode auto)
```
