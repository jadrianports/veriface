"""Shared fixtures for tests/unit.

No fixture here ever touches a real model file or the network — the goal is
a unit suite that proves the registry's failure paths (D-09, D-12) using
synthetic bytes and stub sources, so it runs offline in well under 30
seconds.
"""

from __future__ import annotations

import socket
import ssl
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from veriface.config import VerifaceSettings, clear_settings_cache
from veriface.hashing import sha256_file
from veriface.models.specs import ArtifactSpec

_FAKE_ARTIFACT_BYTES = b"veriface-fake-artifact-fixture-payload-not-a-real-model" * 64


@dataclass
class FakeArtifact:
    """A synthetic cached artifact: a real spec whose sha256 matches real bytes."""

    spec: ArtifactSpec
    path: Path

    def corrupt_one_byte(self) -> None:
        content = bytearray(self.path.read_bytes())
        content[0] ^= 0xFF
        self.path.write_bytes(bytes(content))

    def truncate(self) -> None:
        content = self.path.read_bytes()
        self.path.write_bytes(content[: len(content) // 2])

    def zero_out(self) -> None:
        self.path.write_bytes(b"")

    def restore(self) -> None:
        self.path.write_bytes(_FAKE_ARTIFACT_BYTES)


@pytest.fixture
def fake_artifact(tmp_path: Path) -> FakeArtifact:
    """A deterministic byte payload on disk plus a matching ``ArtifactSpec``.

    No test needs a real model file: the spec's ``sha256`` is the real
    digest of the fixture's own bytes.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "fake_artifact.onnx"
    path.write_bytes(_FAKE_ARTIFACT_BYTES)
    digest = sha256_file(path)
    spec = ArtifactSpec(
        name="fake-artifact",
        source="hf",
        locator="fake-org/fake-artifact",
        revision="0" * 40,
        filename="fake_artifact.onnx",
        sha256=digest,
        license="Apache-2.0",
        training_data_provenance="synthetic fixture bytes, not a real model",
    )
    return FakeArtifact(spec=spec, path=path)


@pytest.fixture
def blocked_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make socket construction raise a distinctive, observable RuntimeError.

    Gives offline tests a hard failure rather than a slow connection
    timeout if a code path unexpectedly reaches for the network.
    """

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("blocked_sockets: socket construction attempted")

    monkeypatch.setattr(socket, "socket", _raise)
    monkeypatch.setattr(socket, "create_connection", _raise)
    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", _raise)


@pytest.fixture
def isolated_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[VerifaceSettings]:
    """Point ``VERIFACE_CACHE_DIR`` / ``VERIFACE_DATA_DIR`` at ``tmp_path``.

    Clears the ``get_settings()`` cache before and after so no test leaks
    its settings into another.
    """
    cache_dir = tmp_path / "cache"
    data_dir = tmp_path / "data"
    monkeypatch.setenv("VERIFACE_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("VERIFACE_DATA_DIR", str(data_dir))
    clear_settings_cache()
    try:
        yield VerifaceSettings()
    finally:
        clear_settings_cache()
