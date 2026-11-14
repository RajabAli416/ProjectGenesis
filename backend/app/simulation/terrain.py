"""Deterministic terrain generation: value noise over a cell grid, producing elevation and moisture
fields from which terrain classes and fertility are derived."""

from __future__ import annotations

import numpy as np

from app.core.rng import seed_to_int
from app.simulation.config import UniverseConfig

# Terrain class codes stored in the grid.
WATER, BARREN, FERTILE, VOID, BUILT = 0, 1, 2, 3, 4
CLASS_NAMES = {WATER: "water", BARREN: "barren", FERTILE: "fertile", VOID: "void", BUILT: "built"}


def _hash2(ix: np.ndarray, iy: np.ndarray, seed: int) -> np.ndarray:
    n = (ix.astype(np.int64) * 374761393 + iy.astype(np.int64) * 668265263 + (seed & 0xFFFFFFFF) * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n = n ^ (n >> 16)
    return (n & 0xFFFFFFFF).astype(np.float64) / 4294967296.0


def value_noise(cols: int, rows: int, seed: int, scale: float) -> np.ndarray:
    ys, xs = np.mgrid[0:rows, 0:cols]
    fx = xs / scale
    fy = ys / scale
    x0 = np.floor(fx).astype(np.int64)
    y0 = np.floor(fy).astype(np.int64)
    tx = fx - x0
    ty = fy - y0
    sx = tx * tx * (3 - 2 * tx)
    sy = ty * ty * (3 - 2 * ty)
    a = _hash2(x0, y0, seed)
    b = _hash2(x0 + 1, y0, seed)
    c = _hash2(x0, y0 + 1, seed)
    d = _hash2(x0 + 1, y0 + 1, seed)
    return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy


def generate(config: UniverseConfig) -> dict[str, np.ndarray]:
    cols, rows = config.cols, config.rows
    seed = seed_to_int(config.seed, "terrain") & 0xFFFFFFFF
    r = config.rules
    elevation = value_noise(cols, rows, seed, 9.0) * 0.65 + value_noise(cols, rows, seed + 7, 3.5) * 0.35
    moisture = value_noise(cols, rows, seed + 31, 12.0)
    fertility = np.clip(moisture * r.base_fertility * 2.0, 0.0, 1.0)

    cls = np.full((rows, cols), BARREN, dtype=np.int8)
    cls[elevation < r.water_level] = WATER
    cls[elevation > r.void_level] = VOID
    fertile = (moisture * r.base_fertility > r.fertility_threshold) & (cls == BARREN)
    cls[fertile] = FERTILE

    resource = np.where(cls == FERTILE, r.initial_resource * (0.6 + 0.4 * fertility), 0.0).astype(np.float32)
    hazard_base = np.clip(value_noise(cols, rows, seed + 97, 7.0) * 0.5 + r.base_hazard, 0.0, 1.0).astype(np.float32)
    return {
        "elevation": elevation.astype(np.float32),
        "moisture": moisture.astype(np.float32),
        "fertility": fertility.astype(np.float32),
        "cls": cls,
        "resource": resource,
        "hazard_base": hazard_base,
        "hazard": hazard_base.copy(),
        "built": np.zeros((rows, cols), dtype=np.int8),
    }
