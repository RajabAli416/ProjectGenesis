"""Shared helpers for the operator scripts. Scripts run from the `backend/` directory with the
project virtualenv active (`python scripts/<name>.py ...`)."""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import Settings, get_settings  # noqa: E402


def add_db_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--db", help="SQLite file to use (default: the configured RECURSION data dir)")
    p.add_argument("--force", action="store_true", help="proceed even if a backend server is answering on the configured port")


def settings_from_args(args: argparse.Namespace) -> Settings:
    if args.db:
        path = Path(args.db).resolve()
        settings = Settings(data_dir=path.parent, db_filename=path.name)
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        return settings
    return get_settings()


def server_is_running(settings: Settings) -> bool:
    try:
        with urllib.request.urlopen(f"http://{settings.host}:{settings.port}/api/health", timeout=1.5) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def refuse_if_server_running(settings: Settings, force: bool) -> None:
    """Two SimulationHosts must never write the same SQLite file at once: counters, snapshots and
    experiment state would diverge. Scripts therefore refuse to run against a live server's DB."""
    if force or not server_is_running(settings):
        return
    sys.exit(
        f"A backend is answering on {settings.host}:{settings.port} and would share {settings.db_path}. Stop it, pass --db <other file>, or use --force if you know the server uses a different database."
    )
