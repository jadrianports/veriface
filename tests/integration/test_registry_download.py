"""The tracer's end-to-end proof: one real pinned artifact, fetched from the
Hugging Face Hub, SHA-256 verified, and opened as a CPU-only ONNX session.

Exercises the real network path — not a mock. Requires network access and
is marked ``integration`` so ``tests/unit`` stays offline.
"""

from __future__ import annotations

import pytest

from veriface.config import VerifaceSettings, clear_settings_cache
from veriface.models.registry import ModelRegistry
from veriface.models.specs import PROFILES

pytestmark = pytest.mark.integration


def test_default_profile_fetches_verifies_and_loads(tmp_path, monkeypatch):
    monkeypatch.setenv("VERIFACE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("VERIFACE_DATA_DIR", str(tmp_path / "data"))
    clear_settings_cache()

    settings = VerifaceSettings()
    registry = ModelRegistry(settings)

    fetched_paths = registry.fetch("default")
    assert len(fetched_paths) == len(PROFILES["default"])
    for fetched_path in fetched_paths:
        assert fetched_path.exists()

    for spec in PROFILES["default"]:
        session = registry.load(spec)
        assert session.get_providers() == ["CPUExecutionProvider"]

    clear_settings_cache()
