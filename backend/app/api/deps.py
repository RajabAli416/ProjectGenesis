from __future__ import annotations

from fastapi import Request

from app.simulation.host import SimulationHost


def get_host(request: Request) -> SimulationHost:
    return request.app.state.host
