"""Success criterion 3 for the phase, expressed as a test rather than a claim:
with the network unreachable, every default-profile artifact resolves from
local cache, and no code path attempts a download (D-12, API-05).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from veriface.cli import app
from veriface.config import clear_settings_cache, get_settings
from veriface.errors import ArtifactNotCachedError
from veriface.models.registry import ModelRegistry
from veriface.models.specs import PROFILES

if TYPE_CHECKING:
    # conftest.py is not a package member (tests/ has no __init__.py), so
    # this import is type-checking-only; pytest injects the `offline`
    # fixture at runtime without needing this module to be importable.
    from .conftest import SocketAttempts

pytestmark = pytest.mark.integration

runner = CliRunner()


def test_default_profile_resolves_and_loads_fully_offline(
    populated_cache: Path,
    offline: SocketAttempts,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VERIFACE_CACHE_DIR", str(populated_cache))
    clear_settings_cache()
    try:
        settings = get_settings()
        registry = ModelRegistry(settings)

        for spec in PROFILES["default"]:
            cached_path = registry.path(spec)
            assert cached_path.exists()
            session = registry.load(spec)
            assert session.get_providers() == ["CPUExecutionProvider"]

        result = runner.invoke(app, ["models", "verify", "--profile", "default"])
        assert result.exit_code == 0, result.output
        assert "MISMATCH" not in result.stdout
        assert "MISSING" not in result.stdout

        # The whole test above exercised path()/load() for all four specs and
        # a full CLI `verify` invocation — assert none of it ever constructed
        # a socket, not just that no exception propagated.
        assert offline.count == 0
    finally:
        clear_settings_cache()


def test_empty_cache_raises_not_cached_without_hanging(
    tmp_path: Path,
    offline: SocketAttempts,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Distinguishes "resolves from cache" from "would have downloaded but
    could not": with an empty cache and the network blocked, `path()` must
    raise `ArtifactNotCachedError` immediately, never attempt a connection,
    and never hang on a connection timeout.
    """
    empty_cache_dir = tmp_path / "empty-cache"
    monkeypatch.setenv("VERIFACE_CACHE_DIR", str(empty_cache_dir))
    clear_settings_cache()
    try:
        settings = get_settings()
        registry = ModelRegistry(settings)
        spec = PROFILES["default"][0]

        start = time.monotonic()
        with pytest.raises(ArtifactNotCachedError):
            registry.path(spec)
        elapsed = time.monotonic() - start

        assert elapsed < 5.0, f"path() took {elapsed:.2f}s — looks like it attempted a connection"
        assert offline.count == 0
    finally:
        clear_settings_cache()
