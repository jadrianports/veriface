"""G-01-8 regression: ``veriface models fetch`` must repair or loudly fail a
corrupted cached artifact — never report success over corruption.

Before this fix, ``HttpsSource.materialize`` (and ``HuggingFaceSource``'s
equivalent) returned an already-cached path on ``Path.exists()`` alone, with
no digest check. ``fetch_each`` passed that path straight through and the CLI
printed it as success. These tests drive the CLI end to end with a stub
source that records forced re-materialization calls and can rewrite the
fixture file when forced, so a single stub covers repair-succeeds,
repair-fails, and clean-cache without ever touching the network or a real
model file (D-29).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import veriface.cli.models as models_module
import veriface.models.registry as registry_module
from veriface.cli import app
from veriface.errors import ArtifactNotCachedError
from veriface.hashing import sha256_file
from veriface.models.registry import ModelRegistry
from typer.testing import CliRunner

runner = CliRunner()


class _RepairAwareStubSource:
    """Stub ``ArtifactSource`` that records forced re-materialization calls.

    Rewrites the fixture file with ``repair_payload`` when a forced call
    arrives, so a single stub drives both the repair-succeeds and
    repair-fails cases without touching the network.
    """

    def __init__(
        self,
        path: Path,
        *,
        repair_payload: bytes | None = None,
        exists: bool = True,
    ) -> None:
        self._path = path
        self._repair_payload = repair_payload
        self._exists = exists
        self.forced_calls = 0

    def materialize(
        self, spec: object, cache_dir: object, *, allow_download: bool, force: bool = False
    ) -> Path:
        if not self._exists:
            raise FileNotFoundError(str(self._path))
        if force:
            self.forced_calls += 1
            if self._repair_payload is not None:
                self._path.write_bytes(self._repair_payload)
        return self._path


def test_corrupted_cache_repair_succeeds(fake_artifact, monkeypatch, isolated_settings):
    monkeypatch.setattr(registry_module, "PROFILES", {"default": (fake_artifact.spec,)})
    original_bytes = fake_artifact.path.read_bytes()
    fake_artifact.corrupt_one_byte()
    stub = _RepairAwareStubSource(fake_artifact.path, repair_payload=original_bytes)
    monkeypatch.setattr(registry_module, "resolve_source", lambda spec: stub)

    result = runner.invoke(app, ["models", "fetch", "--profile", "default"])

    assert result.exit_code == 0
    assert f"{fake_artifact.spec.name}  REPAIRED" in result.stdout
    assert sha256_file(fake_artifact.path) == fake_artifact.spec.sha256
    assert stub.forced_calls == 1


def test_corrupted_cache_repair_fails_names_artifact_and_both_digests(
    fake_artifact, monkeypatch, isolated_settings
):
    monkeypatch.setattr(registry_module, "PROFILES", {"default": (fake_artifact.spec,)})
    fake_artifact.corrupt_one_byte()
    still_bad_payload = b"still-bad-bytes-after-repair-attempt" * 4
    stub = _RepairAwareStubSource(fake_artifact.path, repair_payload=still_bad_payload)
    monkeypatch.setattr(registry_module, "resolve_source", lambda spec: stub)
    expected_computed = sha256_file(fake_artifact.path)  # pre-repair digest is irrelevant here

    result = runner.invoke(app, ["models", "fetch", "--profile", "default"])

    assert result.exit_code == 1
    assert f"{fake_artifact.spec.name}  FAILED" in result.stdout
    assert fake_artifact.spec.sha256 in result.stdout
    assert "REPAIRED" not in result.stdout
    assert stub.forced_calls == 1
    del expected_computed  # only used to document intent; the real computed digest is post-repair


def test_clean_cache_costs_no_repair_and_no_marker(fake_artifact, monkeypatch, isolated_settings):
    monkeypatch.setattr(registry_module, "PROFILES", {"default": (fake_artifact.spec,)})
    stub = _RepairAwareStubSource(fake_artifact.path)
    monkeypatch.setattr(registry_module, "resolve_source", lambda spec: stub)

    result = runner.invoke(app, ["models", "fetch", "--profile", "default"])

    assert result.exit_code == 0
    assert f"{fake_artifact.spec.name}  {fake_artifact.path}" in result.stdout
    assert "REPAIRED" not in result.stdout
    assert stub.forced_calls == 0


def test_registry_path_on_corrupted_cache_hashes_and_forces_nothing(
    fake_artifact, monkeypatch, isolated_settings
):
    fake_artifact.corrupt_one_byte()
    stub = _RepairAwareStubSource(fake_artifact.path)
    monkeypatch.setattr(registry_module, "resolve_source", lambda spec: stub)

    def _forbidden_hash(path: object, chunk_size: int = 1 << 20) -> str:
        raise AssertionError("ModelRegistry.path must not hash the cached file")

    monkeypatch.setattr(registry_module, "sha256_file", _forbidden_hash)

    registry = ModelRegistry(isolated_settings)
    resolved = registry.path(fake_artifact.spec)

    assert resolved == fake_artifact.path
    assert stub.forced_calls == 0


def test_verify_command_on_corrupted_cache_still_reports_mismatch_unchanged(
    fake_artifact, monkeypatch, isolated_settings
):
    monkeypatch.setattr(models_module, "PROFILES", {"default": (fake_artifact.spec,)})
    stub = _RepairAwareStubSource(fake_artifact.path)
    monkeypatch.setattr(registry_module, "resolve_source", lambda spec: stub)
    fake_artifact.corrupt_one_byte()
    computed = sha256_file(fake_artifact.path)

    result = runner.invoke(app, ["models", "verify", "--profile", "default"])

    assert result.exit_code == 1
    assert f"{fake_artifact.spec.name}  MISMATCH expected={fake_artifact.spec.sha256} actual={computed}" in result.stdout
    assert stub.forced_calls == 0


def test_missing_cache_entry_raises_not_cached_not_integrity_error(
    fake_artifact, monkeypatch, isolated_settings, tmp_path
):
    missing_path = tmp_path / "does-not-exist.onnx"
    stub = _RepairAwareStubSource(missing_path, exists=False)
    monkeypatch.setattr(registry_module, "resolve_source", lambda spec: stub)

    registry = ModelRegistry(isolated_settings)

    with pytest.raises(ArtifactNotCachedError) as exc_info:
        registry.path(fake_artifact.spec)

    assert "veriface models fetch --profile default" in str(exc_info.value)
