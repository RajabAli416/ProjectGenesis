"""Short, human-readable identifiers. The frontend displays ids uppercased in dense tables,
so ids are kept short and deterministic rather than UUIDs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_UNIVERSE_RE = re.compile(r"^u-(\d+)$")


def universe_id(n: int) -> str:
    return f"u-{n:04d}"


def universe_code(n: int) -> str:
    return f"U-{n:02d}"


def universe_number(uid: str) -> int:
    m = _UNIVERSE_RE.match(uid)
    if not m:
        raise ValueError(f"not a universe id: {uid}")
    return int(m.group(1))


@dataclass
class LocalIdFactory:
    """Per-universe id counters. Agent ids embed the universe number so they are globally unique
    while remaining deterministic for a given universe."""

    universe_n: int
    counters: dict[str, int] = field(default_factory=dict)

    def next(self, prefix: str) -> str:
        n = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = n
        return f"{prefix}-{self.universe_n:02d}-{n:04d}"

    def agent(self) -> str:
        return self.next("a")

    def structure(self) -> str:
        return self.next("s")

    def memory(self) -> str:
        return self.next("m")

    def belief(self) -> str:
        return self.next("k")

    def hypothesis(self) -> str:
        return self.next("h")

    def evidence(self) -> str:
        return self.next("e")

    def reasoning(self) -> str:
        return self.next("r")

    def institution(self) -> str:
        return self.next("i")

    def era(self) -> str:
        return self.next("era")

    def message(self) -> str:
        return self.next("msg")

    def to_dict(self) -> dict:
        return {"universeN": self.universe_n, "counters": dict(self.counters)}

    @classmethod
    def from_dict(cls, d: dict) -> LocalIdFactory:
        return cls(universe_n=int(d["universeN"]), counters=dict(d.get("counters", {})))
