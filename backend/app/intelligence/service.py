"""Shared inference service: one priority queue, N workers, per-request timeouts, transport-level
retries, latency statistics. All universes and agents share this service; requests carry their own
context so nothing about one agent leaks into another's call."""

from __future__ import annotations

import asyncio
import itertools
import logging
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from app.core.errors import ProviderError, ProviderUnavailable
from app.intelligence.providers.base import InferenceRequest, Provider, ProviderResponse

log = logging.getLogger(__name__)


@dataclass(order=True)
class _Item:
    priority: int
    seq: int
    req: InferenceRequest = field(compare=False)
    future: asyncio.Future = field(compare=False)


class InferenceService:
    def __init__(self, concurrency: int = 1, transport_retries: int = 1) -> None:
        self.concurrency = max(1, concurrency)
        self.transport_retries = transport_retries
        self.provider: Provider | None = None
        self.queue: asyncio.PriorityQueue[_Item] = asyncio.PriorityQueue()
        self._seq = itertools.count()
        self._workers: list[asyncio.Task] = []
        self.in_flight = 0
        self.completed = 0
        self.failed = 0
        self.latencies: deque[float] = deque(maxlen=200)
        self.last_error: str | None = None
        self._stopping = False

    # ------------------------------------------------------------------ lifecycle

    def set_provider(self, provider: Provider | None) -> None:
        self.provider = provider

    async def start(self) -> None:
        self._stopping = False
        await self.set_concurrency(self.concurrency)

    async def set_concurrency(self, n: int) -> None:
        self.concurrency = max(1, n)
        for w in self._workers:
            w.cancel()
        self._workers = [asyncio.create_task(self._worker(i), name=f"inference-worker-{i}") for i in range(self.concurrency)]

    async def stop(self) -> None:
        self._stopping = True
        for w in self._workers:
            w.cancel()
        for w in self._workers:
            try:
                await w
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._workers = []
        while not self.queue.empty():
            item = self.queue.get_nowait()
            if not item.future.done():
                item.future.set_exception(ProviderUnavailable("inference service stopped"))

    # ------------------------------------------------------------------ API

    def submit(self, req: InferenceRequest) -> asyncio.Future[ProviderResponse]:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[ProviderResponse] = loop.create_future()
        if self.provider is None:
            fut.set_exception(ProviderUnavailable("no inference provider configured"))
            return fut
        self.queue.put_nowait(_Item(req.priority, next(self._seq), req, fut))
        return fut

    @property
    def queue_depth(self) -> int:
        return self.queue.qsize()

    def stats(self) -> dict[str, Any]:
        lat = list(self.latencies)
        p50 = p95 = None
        if lat:
            lat.sort()
            p50 = round(statistics.median(lat), 1)
            p95 = round(lat[min(len(lat) - 1, int(len(lat) * 0.95))], 1)
        return {"queue_depth": self.queue_depth, "in_flight": self.in_flight, "concurrency": self.concurrency, "completed": self.completed, "failed": self.failed, "latency_p50_ms": p50, "latency_p95_ms": p95, "last_error": self.last_error}

    # ------------------------------------------------------------------ worker

    async def _worker(self, idx: int) -> None:
        while not self._stopping:
            item = await self.queue.get()
            if item.future.cancelled():
                continue
            self.in_flight += 1
            try:
                resp = await self._call(item.req)
                if not item.future.done():
                    item.future.set_result(resp)
            except Exception as e:  # noqa: BLE001
                self.failed += 1
                self.last_error = f"{type(e).__name__}: {e}"[:300]
                if not item.future.done():
                    item.future.set_exception(e)
            finally:
                self.in_flight -= 1
                self.queue.task_done()

    async def _call(self, req: InferenceRequest) -> ProviderResponse:
        assert self.provider is not None
        attempt = 0
        while True:
            started = time.perf_counter()
            try:
                resp = await asyncio.wait_for(self.provider.generate(req), timeout=req.timeout_s + 5)
                self.latencies.append((time.perf_counter() - started) * 1000)
                self.completed += 1
                return resp
            except (ProviderUnavailable, TimeoutError) as e:
                attempt += 1
                if attempt > self.transport_retries:
                    raise
                log.warning("inference transport error (%s); retrying %d/%d", e, attempt, self.transport_retries)
                await asyncio.sleep(min(5.0, 0.5 * 2**attempt))
            except ProviderError:
                raise
