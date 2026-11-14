"""Per-universe asyncio runner: an accumulator-based tick clock that targets tick_rate × speed
(bounded by the host's compute budget), never waits for browsers, and hands cognition triggers to
the host after every tick. In lockstep mode the clock waits for pending decisions."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import TYPE_CHECKING

from app.simulation.state import UniverseState
from app.simulation.tick import step as tick_step

if TYPE_CHECKING:
    from app.simulation.host import SimulationHost

log = logging.getLogger(__name__)


class UniverseRunner:
    def __init__(self, state: UniverseState, host: SimulationHost) -> None:
        self.state = state
        self.host = host
        self.task: asyncio.Task | None = None
        self.cognition_tasks: set[asyncio.Task] = set()
        self._tick_times: deque[float] = deque(maxlen=512)
        self._acc = 0.0
        self._stepping = False

    # ------------------------------------------------------------------ rate

    @property
    def achieved_rate(self) -> float:
        if self.state.status != "running" or len(self._tick_times) < 2:
            return 0.0
        now = time.perf_counter()
        recent = [t for t in self._tick_times if now - t <= 2.0]
        if len(recent) < 2:
            return 0.0
        span = recent[-1] - recent[0]
        return (len(recent) - 1) / span if span > 0 else 0.0

    def target_rate(self) -> float:
        base = self.state.config.tick_rate * self.state.speed
        budget = self.host.budget_for(self.state)
        return max(0.1, min(base, budget))

    # ------------------------------------------------------------------ lifecycle

    def start(self) -> None:
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._loop(), name=f"runner-{self.state.id}")

    async def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self.task = None
        await self.drain_cognition()

    async def drain_cognition(self) -> None:
        if self.cognition_tasks:
            await asyncio.gather(*list(self.cognition_tasks), return_exceptions=True)

    # ------------------------------------------------------------------ loop

    async def _loop(self) -> None:
        last = time.perf_counter()
        while True:
            st = self.state
            if st.status != "running" or self._stepping:
                last = time.perf_counter()
                self._acc = 0.0
                await asyncio.sleep(0.05)
                continue
            now = time.perf_counter()
            dt, last = now - last, now
            target = self.target_rate()
            self._acc += dt * target
            n = min(int(self._acc), self.host.settings.max_ticks_per_loop)
            if n <= 0:
                await asyncio.sleep(min(0.05, max(0.001, (1.0 - self._acc) / target)))
                continue
            self._acc -= n
            try:
                await self._advance(n)
            except Exception:  # noqa: BLE001
                log.exception("universe %s failed while ticking; pausing", st.id)
                st.status = "paused"
                st.emit("critical", "system", "Engine error while ticking; universe paused. See server log.")
            await self.host.after_batch(self)
            await asyncio.sleep(0)

    async def _advance(self, n: int) -> None:
        st = self.state
        for _ in range(n):
            tick_step(st)
            self._tick_times.append(time.perf_counter())
            await self.host.after_tick(self)
            if st.status != "running":
                break

    async def step(self, ticks: int) -> None:
        """Operator single-step while paused."""
        self._stepping = True
        try:
            st = self.state
            prev = st.status
            st.status = "running"
            try:
                await self._advance(max(1, min(ticks, 10_000)))
            finally:
                if st.status == "running":
                    st.status = prev if prev != "running" else "paused"
            await self.host.after_batch(self, force=True)
        finally:
            self._stepping = False
