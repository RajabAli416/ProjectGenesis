"""In-process event bus. Publishers never block on slow subscribers: each subscriber owns a
bounded queue and frames are dropped (counted) when it falls behind."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Subscriber = Callable[[dict[str, Any]], None]


@dataclass
class Subscription:
    queue: asyncio.Queue
    dropped: int = 0
    universe_filter: set[str] | None = None


@dataclass
class EventBus:
    maxsize: int = 1000
    subscriptions: list[Subscription] = field(default_factory=list)

    def subscribe(self, universe_filter: set[str] | None = None) -> Subscription:
        sub = Subscription(queue=asyncio.Queue(maxsize=self.maxsize), universe_filter=universe_filter)
        self.subscriptions.append(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        if sub in self.subscriptions:
            self.subscriptions.remove(sub)

    def publish(self, message: dict[str, Any]) -> None:
        uid = message.get("universeId")
        if uid is None and isinstance(message.get("snapshot"), dict):
            uid = message["snapshot"].get("universeId")
        if uid is None and isinstance(message.get("event"), dict):
            uid = message["event"].get("universeId")
        for sub in list(self.subscriptions):
            if sub.universe_filter is not None and uid is not None and message.get("type") in ("snapshot",):
                if uid not in sub.universe_filter:
                    continue
            try:
                sub.queue.put_nowait(message)
            except asyncio.QueueFull:
                sub.dropped += 1
