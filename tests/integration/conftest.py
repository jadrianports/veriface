"""Shared fixtures for tests/integration.

``populated_cache`` is the one fixture in this suite permitted to touch the
network — it fetches the real default profile once, session-scoped, so every
test that needs a warm cache reuses the same download instead of re-fetching
~470 MB of real artifacts per test. ``offline`` blocks socket construction
the same way ``tests/unit/conftest.py``'s ``blocked_sockets`` does, so
"offline" means the same thing in both suites, and additionally records how
many attempts were made.
"""

from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from veriface.config import VerifaceSettings
from veriface.models.registry import ModelRegistry


@pytest.fixture(scope="session")
def populated_cache(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Fetch the real default profile once per test session, network permitted.

    Constructs ``VerifaceSettings`` directly with explicit ``cache_dir`` /
    ``data_dir`` kwargs (highest-priority source per config.py's documented
    priority order) rather than monkeypatching env vars, since this fixture
    is session-scoped and must not depend on any function-scoped
    ``monkeypatch``.
    """
    cache_dir = tmp_path_factory.mktemp("veriface-cache")
    data_dir = tmp_path_factory.mktemp("veriface-data")
    settings = VerifaceSettings(cache_dir=cache_dir, data_dir=data_dir)
    registry = ModelRegistry(settings)
    registry.fetch("default")
    return cache_dir


@dataclass
class SocketAttempts:
    """Records how many times a blocked socket constructor was called."""

    count: int = field(default=0)


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> SocketAttempts:
    """Block socket construction and record every attempt.

    Blocks the same three seams as ``tests/unit/conftest.py``'s
    ``blocked_sockets`` fixture. Each attempt still raises immediately (a
    hard failure is a better signal than a silent skip), but the count is
    exposed so a test can assert ``offline.count == 0`` explicitly at the
    end, documenting in the test body itself that no attempt occurred over
    its entire run — not merely that the run didn't raise.
    """
    attempts = SocketAttempts()

    def _raise(*_args: object, **_kwargs: object) -> None:
        attempts.count += 1
        raise RuntimeError("offline: socket construction attempted")

    monkeypatch.setattr(socket, "socket", _raise)
    monkeypatch.setattr(socket, "create_connection", _raise)
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", _raise)
    return attempts
