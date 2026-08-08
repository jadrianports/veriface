"""The corruption/absence matrix for ``ModelRegistry`` (D-09, D-12).

No real model file or network is used: ``resolve_source`` is patched to a
stub whose ``materialize`` returns the ``fake_artifact`` fixture's path
directly, so these tests exercise only the registry's verification logic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import veriface.models.registry as registry_module
from veriface.config import VerifaceSettings
from veriface.errors import ArtifactIntegrityError, ArtifactNotCachedError
from veriface.models.registry import ModelRegistry

SENTINEL_SESSION = object()


class _StubSource:
    """Returns a fixed path, or raises ``FileNotFoundError`` if absent."""

    def __init__(self, path: Path, *, exists: bool = True) -> None:
        self._path = path
        self._exists = exists

    def materialize(self, spec: object, cache_dir: Path, *, allow_download: bool) -> Path:
        if not self._exists:
            raise FileNotFoundError(str(self._path))
        return self._path


def _patch_stub_source(monkeypatch: pytest.MonkeyPatch, path: Path, *, exists: bool = True) -> None:
    monkeypatch.setattr(
        registry_module, "resolve_source", lambda spec: _StubSource(path, exists=exists)
    )


def _patch_open_session_sentinel(monkeypatch: pytest.MonkeyPatch) -> None:
    # WR-08: open_session now takes (model_bytes, *, source_label) rather
    # than a path — the stub's signature mirrors that.
    monkeypatch.setattr(
        registry_module, "open_session", lambda model_bytes, *, source_label: SENTINEL_SESSION
    )


def _patch_open_session_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbidden(model_bytes: object, *, source_label: object) -> object:
        raise AssertionError("open_session must not be called when verification fails")

    monkeypatch.setattr(registry_module, "open_session", _forbidden)


def _registry(tmp_path: Path) -> ModelRegistry:
    return ModelRegistry(VerifaceSettings(cache_dir=tmp_path, data_dir=tmp_path))


def test_matching_digest_loads_a_session(fake_artifact, monkeypatch, tmp_path):
    _patch_stub_source(monkeypatch, fake_artifact.path)
    _patch_open_session_sentinel(monkeypatch)
    registry = _registry(tmp_path)

    session = registry.load(fake_artifact.spec)

    assert session is SENTINEL_SESSION


def test_load_reads_the_cached_path_exactly_once(fake_artifact, monkeypatch, tmp_path):
    """WR-08: verifying and loading must share one read of the cached file —
    a second by-name open (as a path-based ``open_session`` would need) would
    reopen a TOCTOU window between the digest check and session construction.
    """
    _patch_stub_source(monkeypatch, fake_artifact.path)
    captured_model_bytes: list[bytes] = []

    def _capturing_open_session(model_bytes: bytes, *, source_label: object) -> object:
        captured_model_bytes.append(model_bytes)
        return SENTINEL_SESSION

    monkeypatch.setattr(registry_module, "open_session", _capturing_open_session)

    read_call_count = 0
    real_read_bytes = Path.read_bytes

    def _counting_read_bytes(self: Path) -> bytes:
        nonlocal read_call_count
        read_call_count += 1
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", _counting_read_bytes)
    registry = _registry(tmp_path)

    session = registry.load(fake_artifact.spec)

    assert session is SENTINEL_SESSION
    assert read_call_count == 1
    assert captured_model_bytes == [fake_artifact.path.read_bytes()]


def test_one_byte_flip_raises_integrity_error(fake_artifact, monkeypatch, tmp_path):
    _patch_stub_source(monkeypatch, fake_artifact.path)
    _patch_open_session_forbidden(monkeypatch)
    fake_artifact.corrupt_one_byte()
    registry = _registry(tmp_path)

    with pytest.raises(ArtifactIntegrityError) as exc_info:
        registry.load(fake_artifact.spec)

    message = str(exc_info.value)
    assert fake_artifact.spec.sha256 in message
    computed = message.split("computed sha256=")[1].split(".")[0]
    assert computed != fake_artifact.spec.sha256


def test_zero_byte_file_raises_integrity_error(fake_artifact, monkeypatch, tmp_path):
    _patch_stub_source(monkeypatch, fake_artifact.path)
    _patch_open_session_forbidden(monkeypatch)
    fake_artifact.zero_out()
    registry = _registry(tmp_path)

    with pytest.raises(ArtifactIntegrityError):
        registry.load(fake_artifact.spec)


def test_truncated_file_raises_integrity_error(fake_artifact, monkeypatch, tmp_path):
    _patch_stub_source(monkeypatch, fake_artifact.path)
    _patch_open_session_forbidden(monkeypatch)
    fake_artifact.truncate()
    registry = _registry(tmp_path)

    with pytest.raises(ArtifactIntegrityError):
        registry.load(fake_artifact.spec)


def test_reverification_on_second_load_catches_corruption(fake_artifact, monkeypatch, tmp_path):
    _patch_stub_source(monkeypatch, fake_artifact.path)
    _patch_open_session_sentinel(monkeypatch)
    registry = _registry(tmp_path)

    first_session = registry.load(fake_artifact.spec)
    assert first_session is SENTINEL_SESSION

    fake_artifact.corrupt_one_byte()
    _patch_open_session_forbidden(monkeypatch)

    with pytest.raises(ArtifactIntegrityError):
        registry.load(fake_artifact.spec)


@pytest.mark.parametrize(
    "bypass_var", ["VERIFACE_SKIP_VERIFY", "VERIFACE_NO_VERIFY", "SKIP_HASH_CHECK"]
)
def test_no_bypass_env_var_skips_verification(fake_artifact, monkeypatch, tmp_path, bypass_var):
    _patch_stub_source(monkeypatch, fake_artifact.path)
    _patch_open_session_forbidden(monkeypatch)
    fake_artifact.corrupt_one_byte()
    monkeypatch.setenv(bypass_var, "1")
    registry = _registry(tmp_path)

    with pytest.raises(ArtifactIntegrityError):
        registry.load(fake_artifact.spec)


def test_absent_cache_entry_raises_not_cached_with_actionable_message(
    fake_artifact, monkeypatch, tmp_path
):
    missing_path = tmp_path / "does-not-exist.onnx"
    _patch_stub_source(monkeypatch, missing_path, exists=False)
    registry = _registry(tmp_path)

    with pytest.raises(ArtifactNotCachedError) as exc_info:
        registry.path(fake_artifact.spec)

    assert "veriface models fetch --profile default" in str(exc_info.value)
