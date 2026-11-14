"""FastAPI application factory. The SimulationHost is started in the lifespan and keeps running
regardless of whether any browser is connected."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import agents, events, experiments, health, inference, research, universes, ws
from app.api.routers import settings as settings_router
from app.config import Settings, get_settings
from app.observability.logging import configure_logging
from app.persistence.store import Store, open_store
from app.simulation.host import SimulationHost
from app.version import full_version

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, store: Store | None = None, host: SimulationHost | None = None) -> FastAPI:
    cfg = settings or get_settings()
    configure_logging(cfg.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        st = store or open_store(cfg.db_url)
        h = host or SimulationHost(cfg, st)
        app.state.store = st
        app.state.host = h
        await h.start()
        log.info("RECURSION backend %s started; db=%s; universes=%d", full_version(), cfg.db_path, len(h.runners))
        try:
            yield
        finally:
            await h.stop()
            if store is None:
                st.close()
            log.info("RECURSION backend stopped")

    app = FastAPI(title="RECURSION backend", version=full_version(), lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    api_prefix = "/api"
    for r in (universes.router, agents.router, events.router, research.router, experiments.router, settings_router.router, inference.router, health.router):
        app.include_router(r, prefix=api_prefix)
    app.include_router(ws.router)
    return app


app = create_app()
