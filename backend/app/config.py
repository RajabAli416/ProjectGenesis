"""Process configuration. Everything here is overridable through RECURSION_* environment variables
or a .env file next to the backend package. Nothing simulation-specific is hardcoded elsewhere."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RECURSION_",
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- process ---
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])

    # --- storage ---
    data_dir: Path = BACKEND_ROOT / "data"
    db_filename: str = "recursion.sqlite3"
    snapshot_interval_ticks: int = 2_400
    retain_snapshots: int = 48
    autosave: bool = True
    event_flush_ticks: int = 50

    # --- simulation defaults (used for new universes unless overridden by operator settings) ---
    tick_rate: int = 24
    world_width: int = 256
    world_height: int = 160
    cell_size: int = 8
    initial_population: int = 5
    mutation_rate: float = 0.015
    energy_decay: float = 0.002
    host_tick_budget: int = 400  # total ticks/s the host will attempt across all universes
    max_ticks_per_loop: int = 200
    clock_broadcast_hz: float = 4.0
    snapshot_broadcast_hz: float = 1.0
    autostart_restored: bool = False  # restored universes come back paused unless true

    # --- inference defaults ---
    ollama_base_url: str = "http://127.0.0.1:11434"
    default_model: str = "qwen3:4b"
    inference_concurrency: int = 1
    inference_timeout_s: float = 120.0
    inference_num_ctx: int = 4096
    inference_temperature: float = 0.7
    inference_keep_alive: str = "-1"
    inference_think_decisions: bool = False
    inference_think_reflection: bool = True
    inference_max_repair_attempts: int = 1
    memory_window: int = 24
    reflection_interval: int = 400
    decision_interval: int = 120
    min_decision_gap: int = 20

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_filename

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s
