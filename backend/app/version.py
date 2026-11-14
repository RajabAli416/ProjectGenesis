"""Engine version identity, recorded with every snapshot, event and inference request."""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

ENGINE_VERSION = "0.1.0"
# Bumped whenever the tick algorithm changes in a way that alters results for the same seed.
MECHANICS_VERSION = 1
# Bumped whenever prompt templates change.
PROMPT_VERSION = 1


@lru_cache(maxsize=1)
def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        sha = out.stdout.strip()
        return sha or None
    except Exception:  # noqa: BLE001 - git is optional
        return None


def full_version() -> str:
    sha = git_sha()
    return f"{ENGINE_VERSION}+{sha}" if sha else ENGINE_VERSION
