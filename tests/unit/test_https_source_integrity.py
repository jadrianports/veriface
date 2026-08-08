"""WR-02 — direct-file HTTPS downloads must be integrity-checked at fetch time.

Before this fix, ``HttpsSource._materialize_direct_file`` cached a downloaded
file with no digest check at all, unlike the archive-member shape (which
verifies ``archive_sha256`` before extraction). ``HttpsSource._download`` is
monkeypatched to write known bytes instead of making a real HTTP request —
these tests only exercise the digest-check-before-cache logic, never the
network (D-29).

G-01-8 follow-on (task 2 of 01-09): the archive-member leg verified only the
container, never the extracted member, and extracted straight over the
cached artifact before any member check ran — so a forced repair could
destroy a merely-corrupt cache entry before knowing whether the replacement
was any good. The tests below build synthetic zips in ``tmp_path`` exactly
as ``tests/unit/test_archive_member_safety.py`` does and drive them through
the same ``_patch_download_with`` fake, never touching the network.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
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


def _archive_member_spec(
    *, sha256: str, archive_sha256: str, member: str = "det_10g.onnx"
) -> ArtifactSpec:
    return ArtifactSpec(
        name="fake-archive-artifact",
        source="https",
        locator="https://example.invalid/fake_archive.zip",
        revision="v0",
        filename=member,
        member=member,
        archive_sha256=archive_sha256,
        sha256=sha256,
        license="Apache-2.0",
        training_data_provenance="synthetic fixture bytes, not a real model",
    )


def _build_zip_bytes(member_name: str, content: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(member_name, content)
    return buf.getvalue()


def _https_leg_entries(cache_dir: Path, spec: ArtifactSpec) -> list[Path]:
    dest_dir = cache_dir / "https" / spec.name
    if not dest_dir.exists():
        return []
    return sorted(p for p in dest_dir.rglob("*") if p.is_file())


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


def test_archive_member_digest_mismatch_raises_and_caches_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The container digest matches its pin; the extracted member does not
    match ``spec.sha256``. Must raise, naming both digests, and leave no
    artifact file, container, or staging directory behind."""
    member_name = "det_10g.onnx"
    member_bytes = b"wrong-member-bytes-container-is-fine" * 4
    zip_bytes = _build_zip_bytes(member_name, member_bytes)
    archive_digest = hashlib.sha256(zip_bytes).hexdigest()
    wrong_pin = "0" * 64
    spec = _archive_member_spec(sha256=wrong_pin, archive_sha256=archive_digest, member=member_name)
    _patch_download_with(monkeypatch, zip_bytes)

    with pytest.raises(ArtifactIntegrityError) as exc_info:
        HttpsSource().materialize(spec, tmp_path, allow_download=True)

    message = str(exc_info.value)
    assert spec.sha256 in message
    assert hashlib.sha256(member_bytes).hexdigest() in message
    assert _https_leg_entries(tmp_path, spec) == []


def test_successful_archive_materialization_leaves_only_the_extracted_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    member_name = "det_10g.onnx"
    member_bytes = b"a-genuine-extracted-member-payload" * 4
    zip_bytes = _build_zip_bytes(member_name, member_bytes)
    archive_digest = hashlib.sha256(zip_bytes).hexdigest()
    member_digest = hashlib.sha256(member_bytes).hexdigest()
    spec = _archive_member_spec(
        sha256=member_digest, archive_sha256=archive_digest, member=member_name
    )
    _patch_download_with(monkeypatch, zip_bytes)

    dest_path = HttpsSource().materialize(spec, tmp_path, allow_download=True)

    assert dest_path.read_bytes() == member_bytes
    assert _https_leg_entries(tmp_path, spec) == [dest_path]


def test_forced_archive_repair_preserves_previous_cache_on_member_digest_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A forced re-materialization whose freshly-downloaded member still
    misses the pin must not destroy the previously cached bytes."""
    member_name = "det_10g.onnx"
    member_bytes = b"still-wrong-member-bytes-after-forced-repair" * 4
    zip_bytes = _build_zip_bytes(member_name, member_bytes)
    archive_digest = hashlib.sha256(zip_bytes).hexdigest()
    wrong_pin = "0" * 64
    spec = _archive_member_spec(sha256=wrong_pin, archive_sha256=archive_digest, member=member_name)

    dest_dir = tmp_path / "https" / spec.name
    dest_dir.mkdir(parents=True)
    previous_bytes = b"previously-cached-bytes-must-survive-a-failed-repair"
    (dest_dir / spec.filename).write_bytes(previous_bytes)
    _patch_download_with(monkeypatch, zip_bytes)

    with pytest.raises(ArtifactIntegrityError):
        HttpsSource().materialize(spec, tmp_path, allow_download=True, force=True)

    assert (dest_dir / spec.filename).read_bytes() == previous_bytes
    assert _https_leg_entries(tmp_path, spec) == [dest_dir / spec.filename]


def test_forced_archive_repair_replaces_corrupted_cache_after_member_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    member_name = "det_10g.onnx"
    good_bytes = b"a-freshly-verified-correct-member-payload" * 4
    zip_bytes = _build_zip_bytes(member_name, good_bytes)
    archive_digest = hashlib.sha256(zip_bytes).hexdigest()
    member_digest = hashlib.sha256(good_bytes).hexdigest()
    spec = _archive_member_spec(
        sha256=member_digest, archive_sha256=archive_digest, member=member_name
    )

    dest_dir = tmp_path / "https" / spec.name
    dest_dir.mkdir(parents=True)
    (dest_dir / spec.filename).write_bytes(b"stale-corrupted-cached-bytes")
    _patch_download_with(monkeypatch, zip_bytes)

    dest_path = HttpsSource().materialize(spec, tmp_path, allow_download=True, force=True)

    assert dest_path.read_bytes() == good_bytes
    assert _https_leg_entries(tmp_path, spec) == [dest_path]


def test_forced_direct_file_repair_replaces_corrupted_cache_unforced_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _direct_file_spec(sha256=_REAL_DIGEST)
    dest_dir = tmp_path / "https" / spec.name
    dest_dir.mkdir(parents=True)
    corrupted_bytes = b"corrupted-direct-file-bytes"
    (dest_dir / spec.filename).write_bytes(corrupted_bytes)
    _patch_download_with(monkeypatch, _REAL_BYTES)

    unforced_path = HttpsSource().materialize(spec, tmp_path, allow_download=True)
    assert unforced_path.read_bytes() == corrupted_bytes

    forced_path = HttpsSource().materialize(spec, tmp_path, allow_download=True, force=True)
    assert forced_path.read_bytes() == _REAL_BYTES


def test_offline_materialize_on_corrupted_cache_neither_hashes_nor_repairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = _direct_file_spec(sha256=_REAL_DIGEST)
    dest_dir = tmp_path / "https" / spec.name
    dest_dir.mkdir(parents=True)
    corrupted_bytes = b"corrupted-bytes-offline-path-must-not-touch"
    (dest_dir / spec.filename).write_bytes(corrupted_bytes)

    def _forbidden_hash(path: Path, chunk_size: int = 1 << 20) -> str:
        raise AssertionError("offline materialize must not hash the cached file")

    def _forbidden_download(url: str, dest_path: Path) -> None:
        raise AssertionError("offline materialize must not download")

    monkeypatch.setattr(sources_module, "sha256_file", _forbidden_hash)
    monkeypatch.setattr(sources_module.HttpsSource, "_download", staticmethod(_forbidden_download))

    dest_path = HttpsSource().materialize(spec, tmp_path, allow_download=False)

    assert dest_path.read_bytes() == corrupted_bytes
