# RECURSION — frontend

Observation interface for an artificial-life research environment. React 19, TypeScript, Vite, PixiJS 8.

This package contains no simulation engine, no agent reasoning and no fabricated results. It displays state published by the Python FastAPI backend in `../backend` over REST and WebSocket, and sends operator commands (create/archive universes, run experiments, apply settings, record benchmarks) to it. Without a backend it renders clearly-labelled static fixtures.

## Run

```sh
npm install
npm run dev        # http://localhost:5173
npm run build      # typecheck + production bundle
npm run typecheck
npm run lint
```

`.env.development` sets `VITE_DATA_SOURCE=http` so `npm run dev` talks to the backend on `127.0.0.1:8000` (start it first; see `../backend/README.md`). Copy `.env.example` to `.env.local` to override, e.g. `VITE_DATA_SOURCE=static` to browse fixtures without a backend.

## Data boundary

```
features/*  ──►  api/hooks  ──►  api/dataSource (interface)
                                   ├── staticDataSource  → sample/*.sample.ts
                                   └── httpDataSource    → api/http + api/endpoints → FastAPI
                 api/commands (SimulationCommands)        → POST /universes/:id/command
                 api/mutations (Mutations)                → create/archive universes, experiments, hypotheses, settings, benchmarks
                 api/ws (LiveClient)                      → WebSocket, typed ServerMessage union; `subscribe` for snapshot frames
```

- `VITE_DATA_SOURCE=static` (default) serves `src/sample/`. The status bar shows a persistent **Sample presentation data** tag and the Overview shows a notice. Transport commands are declined with "No simulation engine connected."
- `VITE_DATA_SOURCE=http` switches both reads and commands to the backend at `VITE_API_BASE_URL` and opens the WebSocket at `VITE_WS_URL` (or `/ws` on the page origin). The Vite dev server proxies `/api` and `/ws` to `127.0.0.1:8000`.

The frontend never advances simulation time or mutates population state. Every clock value is a snapshot received from the backend; live `clock` messages are merged in `app/UniverseProvider.tsx`, `snapshot` frames for the subscribed universe feed the viewport (`features/universe/UniversePage.tsx`), and `universe.changed` triggers catalogue reloads.

### Backend contract

- Domain types: `src/domain/types.ts` — expected to mirror the backend's Pydantic models.
- Render-facing snapshot: `src/viewport/types.ts` (`WorldSnapshot`, `EntityMarker`, `TerrainCell`).
- Routes: `src/api/endpoints.ts`.
- WebSocket messages: `ServerMessage` in `src/api/ws.ts`.

## Structure

| Path | Purpose |
| --- | --- |
| `src/design/` | Tokens (`tokens.css`), reset, global styles, self-hosted IBM Plex |
| `src/components/ui/` | Primitives: Button, Segmented, Panel, DataList/Readouts, Table, Tabs, Meter, StatusDot, Tag, form controls, EmptyState, Disclosure, Icon |
| `src/components/shell/` | AppShell grid, NavRail, InstrumentBar, StatusBar, Inspector drawer |
| `src/features/` | One folder per section: overview, universe, agents, civilization, realities, observatory, experiments, settings |
| `src/viewport/` | `PixiStage` (framework-agnostic renderer and camera), `UniverseViewport` (React mount), camera math, hit testing, palette |
| `src/store/` | Zustand: UI preferences, viewport selection/camera, connection state, settings draft, route chrome |
| `src/sample/` | Static fixtures, each file headed `SAMPLE PRESENTATION DATA` |

## Keyboard

`1`–`8` switch sections. In the Universe viewport: `V` select, `H` pan, `+`/`-` zoom, `F` fit, `Esc` clear selection, `I` toggle inspector. Drag pans, wheel zooms toward the cursor.
