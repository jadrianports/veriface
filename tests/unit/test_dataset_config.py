"""Two-tier dataset config: declared budgets/phase markers, and the manifest
digest as a checked precondition of use (D-19, D-20, D-25)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from veriface_eval.cli import data_app
from veriface_eval.datasets.config import (
    DATASET_CONFIGS,
    SENTINEL_MANIFEST_SHA256,
    TIERS,
    ManifestDigestMismatchError,
    SentinelManifestDigestError,
    TierNotFoundError,
    load_dataset_config,
    manifest_path_for,
    verify_manifest_digest,
)
from veriface_eval.datasets.manifest import manifest_sha256

runner = CliRunner()


def test_tiers_declares_exactly_eval_and_extended_with_phase_markers() -> None:
    assert set(TIERS) == {"eval", "extended"}
    assert TIERS["eval"].materialised_in_phase == 1
    assert TIERS["extended"].materialised_in_phase == 3


def test_tiers_budgets_are_positive_and_extended_is_larger() -> None:
    assert TIERS["eval"].size_budget_bytes > 0
    assert TIERS["extended"].size_budget_bytes > TIERS["eval"].size_budget_bytes


def test_dataset_configs_start_at_the_sentinel_digest() -> None:
    for tier_name in TIERS:
        assert DATASET_CONFIGS[tier_name].manifest_sha256 == SENTINEL_MANIFEST_SHA256


def test_load_dataset_config_raises_while_digest_is_sentinel() -> None:
    with pytest.raises(SentinelManifestDigestError):
        load_dataset_config("eval")


def test_load_dataset_config_raises_named_error_for_unknown_tier() -> None:
    with pytest.raises(TierNotFoundError):
        load_dataset_config("nonexistent")


def test_manifest_path_for_raises_named_error_for_unknown_tier() -> None:
    with pytest.raises(TierNotFoundError):
        manifest_path_for("nonexistent")


def test_verify_manifest_digest_raises_on_sentinel(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.csv"
    manifest_path.write_text("subject_id,relative_path,spoof_class,split\n", encoding="utf-8")
    with pytest.raises(SentinelManifestDigestError):
        verify_manifest_digest(manifest_path, SENTINEL_MANIFEST_SHA256)


def test_verify_manifest_digest_succeeds_on_an_unaltered_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.csv"
    manifest_path.write_text("subject_id,relative_path,spoof_class,split\n", encoding="utf-8")
    real_digest = manifest_sha256(manifest_path)

    verify_manifest_digest(manifest_path, real_digest)  # must not raise


def test_verify_manifest_digest_raises_on_an_altered_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.csv"
    manifest_path.write_text("subject_id,relative_path,spoof_class,split\n", encoding="utf-8")
    real_digest = manifest_sha256(manifest_path)

    manifest_path.write_text(
        "subject_id,relative_path,spoof_class,split\nsubject_0000,x.jpg,live,train\n",
        encoding="utf-8",
    )

    with pytest.raises(ManifestDigestMismatchError):
        verify_manifest_digest(manifest_path, real_digest)


def test_cli_manifest_help_lists_verify_and_build() -> None:
    result = runner.invoke(data_app, ["manifest", "--help"])
    assert result.exit_code == 0
    assert "verify" in result.output
    assert "build" in result.output


def test_cli_manifest_verify_reports_mismatch_for_sentinel_digest() -> None:
    result = runner.invoke(data_app, ["manifest", "verify", "--tier", "eval"])
    assert result.exit_code != 0
    assert "MISMATCH" in result.output


def test_cli_data_fetch_celeba_spoof_reports_failed_for_unknown_tier(isolated_settings) -> None:
    """WR-05: an unknown ``--tier`` must produce a clean ``FAILED`` line and
    exit code 1 through the CLI's existing ``except VerifaceError`` handler —
    not an unhandled traceback from a bare ``KeyError``."""
    result = runner.invoke(data_app, ["fetch", "celeba-spoof", "--tier", "not-a-real-tier"])

    assert result.exit_code == 1
    assert "celeba-spoof  FAILED" in result.output
    assert "not-a-real-tier" in result.output


def test_cli_manifest_build_refuses_to_overwrite_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import veriface_eval.datasets.config as dataset_config_module

    monkeypatch.setattr(dataset_config_module, "MANIFEST_DIR", tmp_path)
    existing = tmp_path / TIERS["eval"].manifest_filename
    existing.write_text("original\n", encoding="utf-8")

    result = runner.invoke(data_app, ["manifest", "build", "--tier", "eval"])

    assert result.exit_code != 0
    assert "REFUSED" in result.output
    assert existing.read_text(encoding="utf-8") == "original\n"
