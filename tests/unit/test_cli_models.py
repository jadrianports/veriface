"""Drives ``veriface models fetch`` / ``verify`` through the CLI surface."""

from __future__ import annotations

from typer.testing import CliRunner

import veriface.cli.models as models_module
import veriface.models.registry as registry_module
from veriface.cli import app

runner = CliRunner()


class _StubSource:
    def __init__(self, path, *, exists: bool = True) -> None:
        self._path = path
        self._exists = exists

    def materialize(self, spec, cache_dir, *, allow_download: bool):
        if not self._exists:
            raise FileNotFoundError(str(self._path))
        return self._path


def _patch_resolve_source(monkeypatch, path, *, exists: bool = True) -> None:
    # `verify` drives ModelRegistry.path() and `fetch` drives
    # ModelRegistry.fetch_each() (WR-01) — both resolve sources through
    # veriface.models.registry's own imported name, so patching it there is
    # enough for either command path.
    def stub_factory(spec):
        return _StubSource(path, exists=exists)

    monkeypatch.setattr(registry_module, "resolve_source", stub_factory)


def test_fetch_against_fake_profile_reports_the_materialized_path(
    fake_artifact, monkeypatch, isolated_settings
):
    # `fetch` now drives ModelRegistry.fetch_each() (WR-01), which reads
    # PROFILES through registry_module's own imported name.
    monkeypatch.setattr(registry_module, "PROFILES", {"default": (fake_artifact.spec,)})
    _patch_resolve_source(monkeypatch, fake_artifact.path)

    result = runner.invoke(app, ["models", "fetch", "--profile", "default"])

    assert result.exit_code == 0
    assert f"{fake_artifact.spec.name}  {fake_artifact.path}" in result.stdout


def test_fetch_reports_failed_for_a_spec_whose_source_cannot_materialize(
    fake_artifact, monkeypatch, isolated_settings
):
    monkeypatch.setattr(registry_module, "PROFILES", {"default": (fake_artifact.spec,)})

    def _raising_stub_factory(spec):
        class _RaisingSource:
            def materialize(self, spec, cache_dir, *, allow_download):
                from veriface.errors import ArtifactSourceError

                raise ArtifactSourceError("boom")

        return _RaisingSource()

    monkeypatch.setattr(registry_module, "resolve_source", _raising_stub_factory)

    result = runner.invoke(app, ["models", "fetch", "--profile", "default"])

    assert result.exit_code == 1
    assert f"{fake_artifact.spec.name}  FAILED" in result.stdout


def test_verify_against_fake_profile_ok_then_corrupted_mismatch(
    fake_artifact, monkeypatch, isolated_settings
):
    monkeypatch.setattr(models_module, "PROFILES", {"default": (fake_artifact.spec,)})
    _patch_resolve_source(monkeypatch, fake_artifact.path)

    clean_result = runner.invoke(app, ["models", "verify", "--profile", "default"])
    assert clean_result.exit_code == 0
    assert f"{fake_artifact.spec.name}  OK" in clean_result.stdout

    fake_artifact.corrupt_one_byte()

    corrupted_result = runner.invoke(app, ["models", "verify", "--profile", "default"])
    assert corrupted_result.exit_code == 1
    assert "MISMATCH" in corrupted_result.stdout


def test_verify_twice_produces_identical_stdout(fake_artifact, monkeypatch, isolated_settings):
    monkeypatch.setattr(models_module, "PROFILES", {"default": (fake_artifact.spec,)})
    _patch_resolve_source(monkeypatch, fake_artifact.path)

    first = runner.invoke(app, ["models", "verify", "--profile", "default"])
    second = runner.invoke(app, ["models", "verify", "--profile", "default"])

    assert first.stdout == second.stdout


def test_help_lists_models_group():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "models" in result.stdout


def test_models_help_lists_fetch_and_verify():
    result = runner.invoke(app, ["models", "--help"])
    assert result.exit_code == 0
    assert "fetch" in result.stdout
    assert "verify" in result.stdout
