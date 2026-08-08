"""D-37 — license matrix and NOTICE generation, deterministic and complete."""

from __future__ import annotations

import pytest

from veriface.licensing import LicenseMetadataError, render_license_matrix, render_notice
from veriface.models.specs import PROFILES, ArtifactSpec


def _distinct_spec_names() -> set[str]:
    return {spec.name for specs in PROFILES.values() for spec in specs}


def test_matrix_has_header_and_one_row_per_distinct_artifact() -> None:
    matrix = render_license_matrix()
    lines = matrix.rstrip("\n").split("\n")
    assert lines[0].startswith("| Artifact |")
    body_rows = lines[2:]  # header, separator, then one row per artifact
    assert len(body_rows) == len(_distinct_spec_names())


def test_matrix_is_byte_identical_across_renders() -> None:
    first = render_license_matrix()
    second = render_license_matrix()
    assert first == second


def test_notice_contains_every_artifact_name_and_apache_for_minifasnet() -> None:
    notice = render_notice()
    for name in _distinct_spec_names():
        assert name in notice, f"{name} missing from NOTICE body"
    assert "Apache-2.0" in notice


def test_notice_is_byte_identical_across_renders() -> None:
    assert render_notice() == render_notice()


def _spec_with_license(license_text: str) -> ArtifactSpec:
    return ArtifactSpec(
        name="whitespace-license-spec",
        source="hf",
        locator="fake-org/fake-repo",
        revision="0" * 40,
        filename="fake.onnx",
        sha256="0" * 64,
        license=license_text,
        training_data_provenance="synthetic fixture, not a real model",
    )


def test_whitespace_only_license_raises_in_both_renderers() -> None:
    bad_profiles = {"bad": (_spec_with_license("   "),)}
    with pytest.raises(LicenseMetadataError):
        render_license_matrix(bad_profiles)
    with pytest.raises(LicenseMetadataError):
        render_notice(bad_profiles)


def test_pipe_characters_in_cells_are_escaped() -> None:
    spec = ArtifactSpec(
        name="pipe|name",
        source="hf",
        locator="fake-org/fake-repo",
        revision="0" * 40,
        filename="fake.onnx",
        sha256="0" * 64,
        license="Apache-2.0",
        training_data_provenance="synthetic fixture, not a real model",
    )
    matrix = render_license_matrix({"bad": (spec,)})
    # A raw "|" inside a cell would visually break the Markdown table; the
    # renderer must escape it to "\|" before emitting the row.
    assert "pipe\\|name" in matrix
