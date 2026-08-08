"""WR-02 — direct-file HTTPS downloads must be integrity-checked at fetch time.

Before this fix, ``HttpsSource._materialize_direct_file`` cached a downloaded
file with no digest check at all, unlike the archive-member shape (which
verifies ``archive_sha256`` before extraction). ``HttpsSource._download`` is
monkeypatched to write known bytes instead of making a real HTTP request —
these tests only exercise the digest-check-before-cache logic, never the
network (D-29).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import veriface.models.sources as sources_module
from veriface.errors import ArtifactIntegrityError
from veriface.models.sources import HttpsSource
from veriface.models.specs import ArtifactSpec

_REAL_BYTES = b"a-genuine-direct-file-payload-not-a-real-model" * 8
_REAL_DIGEST = hashlib.sha256(_REAL_BYTES).hexdigest()


def _direct_file_spec(*, sha256: str) -> ArtifactSpec:
    return ArtifactSpec(
        name="fake-direct-file",
        source="https",
        locator="https://example.invalid/fake_artifact.onnx",
        revision="v0",
        filename="fake_artifact.onnx",
        sha256=sha256,
        license="Apache-2.0",
        training_data_provenance="synthetic fixture bytes, not a real model",
    )


def _patch_download_with(monkeypatch: pytest.MonkeyPatch, payload: bytes) -> None:
    def _fake_download(url: str, dest_path: Path) -> None:
        dest_path.write_bytes(payload)

    monkeypatch.setattr(sources_module.HttpsSource, "_download", staticmethod(_fake_download))


def test_matching_digest_caches_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = _direct_file_spec(sha256=_REAL_DIGEST)
    _patch_download_with(monkeypatch, _REAL_BYTES)

    dest_path = HttpsSource().materialize(spec, tmp_path, allow_download=True)

    assert dest_path.exists()
    assert dest_path.read_bytes() == _REAL_BYTES
    assert not (dest_path.parent / f"{spec.filename}.part").exists()


def test_mismatched_digest_raises_and_does_not_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wrong_digest = "0" * 64
    spec = _direct_file_spec(sha256=wrong_digest)
    _patch_download_with(monkeypatch, _REAL_BYTES)

    with pytest.raises(ArtifactIntegrityError) as exc_info:
        HttpsSource().materialize(spec, tmp_path, allow_download=True)

    message = str(exc_info.value)
    assert spec.sha256 in message
    dest_dir = tmp_path / "https" / spec.name
    assert not (dest_dir / spec.filename).exists()
    assert not (dest_dir / f"{spec.filename}.part").exists()
