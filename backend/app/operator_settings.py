"""Operator settings: defaults derived from process config, persisted as one JSON document."""

from __future__ import annotations

from typing import Any

from app.api import schemas as S
from app.config import Settings


def default_settings(cfg: Settings) -> S.OperatorSettings:
    return S.OperatorSettings(
        providers=[
            S.ProviderConfig(id="p-ollama", label="Local Ollama", adapter="ollama", base_url=cfg.ollama_base_url, model=cfg.default_model, has_credential=False, enabled=True),
        ],
        reasoning=S.ReasoningConfig(
            provider_id="p-ollama",
            temperature=cfg.inference_temperature,
            max_steps=1 + cfg.inference_max_repair_attempts,
            memory_window=cfg.memory_window,
            reflection_interval=cfg.reflection_interval,
            decision_interval=cfg.decision_interval,
            num_ctx=cfg.inference_num_ctx,
            think_decisions=cfg.inference_think_decisions,
            think_reflection=cfg.inference_think_reflection,
            prompt_profile="neutral",
            concurrency=cfg.inference_concurrency,
            timeout_s=cfg.inference_timeout_s,
        ),
        simulation=S.SimulationParams(
            tick_rate=cfg.tick_rate,
            world_width=cfg.world_width,
            world_height=cfg.world_height,
            initial_population=cfg.initial_population,
            mutation_rate=cfg.mutation_rate,
            energy_decay=cfg.energy_decay,
            cell_size=cfg.cell_size,
        ),
        performance=S.PerformanceConfig(render_scale=1.0, entity_cap=5_000, fps_cap=60, cull_offscreen=True),
        persistence=S.PersistenceConfig(snapshot_interval_ticks=cfg.snapshot_interval_ticks, retain_snapshots=cfg.retain_snapshots, autosave=cfg.autosave, store_path=str(cfg.data_dir)),
    )


def merge_settings(defaults: S.OperatorSettings, stored: dict[str, Any] | None) -> S.OperatorSettings:
    if not stored:
        return defaults
    data = defaults.model_dump(by_alias=True)
    for key in ("providers", "reasoning", "simulation", "performance", "persistence"):
        if key in stored:
            if isinstance(stored[key], dict) and isinstance(data.get(key), dict):
                data[key] = {**data[key], **stored[key]}
            else:
                data[key] = stored[key]
    return S.OperatorSettings.model_validate(data)


def universe_config_overrides(settings: S.OperatorSettings) -> dict[str, Any]:
    """Operator simulation defaults expressed as UniverseConfig fields."""
    sim, rs = settings.simulation, settings.reasoning
    return {
        "width": sim.world_width,
        "height": sim.world_height,
        "cell_size": sim.cell_size,
        "initial_population": sim.initial_population,
        "tick_rate": sim.tick_rate,
        "rules.mutation_rate": sim.mutation_rate,
        "rules.energy_decay": sim.energy_decay,
        "reasoning.memory_window": rs.memory_window,
        "reasoning.reflection_interval": rs.reflection_interval,
        "reasoning.decision_interval": rs.decision_interval,
        "reasoning.prompt_profile": rs.prompt_profile,
    }
