"""Deterministic random streams. Every universe owns named streams derived from its seed so that
terrain generation, environment drift, agent mechanics and inference seeds never interfere."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field


def seed_to_int(seed: str, salt: str = "") -> int:
    h = hashlib.sha256(f"{seed}:{salt}".encode()).digest()
    return int.from_bytes(h[:8], "big")


def derive_seed(seed: str, salt: str) -> str:
    return hashlib.sha256(f"{seed}:{salt}".encode()).hexdigest()[:8]


def random_seed_hex(rng: random.Random | None = None) -> str:
    r = rng or random.SystemRandom()
    return f"{r.getrandbits(32):08x}"


STREAMS = ("terrain", "environment", "agents", "social", "inference", "research", "recursion")


@dataclass
class RngStreams:
    seed: str
    streams: dict[str, random.Random] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.streams:
            for name in STREAMS:
                self.streams[name] = random.Random(seed_to_int(self.seed, name))

    def __getattr__(self, name: str) -> random.Random:
        try:
            return self.__dict__["streams"][name]
        except KeyError as e:  # pragma: no cover
            raise AttributeError(name) from e

    def get(self, name: str) -> random.Random:
        return self.streams[name]

    def to_dict(self) -> dict:
        return {name: list_state(r.getstate()) for name, r in self.streams.items()}

    @classmethod
    def from_dict(cls, seed: str, d: dict) -> RngStreams:
        inst = cls(seed)
        for name, st in d.items():
            if name in inst.streams:
                inst.streams[name].setstate(tuple_state(st))
        return inst


def list_state(state: tuple) -> list:
    version, internal, gauss = state
    return [version, list(internal), gauss]


def tuple_state(state: list) -> tuple:
    version, internal, gauss = state
    return (version, tuple(internal), gauss)
