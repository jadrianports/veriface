"""D-12: import and the no-network code paths never construct a socket.

A plain ``import`` inside an already-imported test process is a no-op, so
the pure import assertion runs in a subprocess with every socket
constructor patched before ``import veriface`` executes. The remaining
behaviours (``get_settings()``, ``ModelRegistry(...).path(spec)`` on a
populated cache) run in-process against the ``blocked_sockets`` fixture,
since they don't depend on import-time behaviour.
"""

from __future__ import annotations

import subprocess
import sys

import veriface.models.registry as registry_module
from veriface.config import VerifaceSettings, clear_settings_cache, get_settings

_SUBPROCESS_SCRIPT = """
import socket
import ssl


def _raise(*args, **kwargs):
    raise RuntimeError("blocked_sockets: socket construction attempted")


socket.socket = _raise
socket.create_connection = _raise
ssl.SSLContext.wrap_socket = _raise

import veriface
import veriface.models.registry

print("OK")
"""


def test_import_veriface_with_sockets_blocked_in_subprocess() -> None:
    result = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS_SCRIPT],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_get_settings_does_not_touch_the_network(blocked_sockets, isolated_settings) -> None:
    clear_settings_cache()
    settings = get_settings()
    assert isinstance(settings, VerifaceSettings)


def test_registry_path_on_populated_cache_does_not_touch_the_network(
    blocked_sockets, fake_artifact, monkeypatch, tmp_path
) -> None:
    class _StubSource:
        def materialize(self, spec: object, cache_dir: object, *, allow_download: bool) -> object:
            return fake_artifact.path

    monkeypatch.setattr(registry_module, "resolve_source", lambda spec: _StubSource())

    settings = VerifaceSettings(cache_dir=tmp_path, data_dir=tmp_path)
    registry = registry_module.ModelRegistry(settings)

    resolved = registry.path(fake_artifact.spec)

    assert resolved == fake_artifact.path
