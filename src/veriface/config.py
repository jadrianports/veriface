"""Process-wide configuration for veriface.

Nothing in this module touches the filesystem or the network at import time
(D-12). Cache/data directory defaults are OS-conditional (D-13, D-24) and are
exposed as free functions so tests can monkeypatch ``sys.platform`` and the
relevant environment variables and re-derive them without importing the
platform-specific branch logic themselves.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_cache_dir() -> Path:
    """Return the OS-conditional default model-artifact cache directory (D-13).

    Windows: ``%LOCALAPPDATA%/veriface/cache`` (falling back to
    ``~/AppData/Local`` if the environment variable is unset).
    Everything else: ``$XDG_CACHE_HOME/veriface`` if set, else
    ``~/.cache/veriface``.
    """
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return base / "veriface" / "cache"

    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg_cache_home) if xdg_cache_home else Path.home() / ".cache"
    return base / "veriface"


def default_data_dir() -> Path:
    """Return the default dataset directory (D-24).

    Deliberately a different variable and a different tree from the model
    cache: datasets are large, project-specific, and disposable, while models
    are small, hash-pinned, and shared across projects.
    """
    return Path.cwd() / "data"


class VerifaceSettings(BaseSettings):
    """Environment-driven settings for veriface.

    Fields default to the OS-conditional functions above but can be
    overridden via ``VERIFACE_CACHE_DIR`` / ``VERIFACE_DATA_DIR``.
    """

    model_config = SettingsConfigDict(env_prefix="VERIFACE_")

    # default_factory is only invoked when no higher-priority source (explicit
    # init kwarg, then the VERIFACE_CACHE_DIR / VERIFACE_DATA_DIR env vars)
    # supplies a value, so an explicit env var always overrides the
    # OS-conditional default.
    cache_dir: Path = Field(default_factory=default_cache_dir)
    data_dir: Path = Field(default_factory=default_data_dir)


@lru_cache(maxsize=1)
def _cached_settings() -> VerifaceSettings:
    return VerifaceSettings()


def get_settings() -> VerifaceSettings:
    """Return a process-cached ``VerifaceSettings`` instance."""
    return _cached_settings()


def clear_settings_cache() -> None:
    """Clear the cached settings instance (test-only helper)."""
    _cached_settings.cache_clear()
