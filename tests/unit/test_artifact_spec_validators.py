"""WR-03 — an ``hf``-source spec must never pair with a non-null ``member``.

``HuggingFaceSource.materialize`` never reads ``spec.member``, so this
combination must not silently reach that code path. The check lives in
``resolve_source`` (not an ``ArtifactSpec`` model validator) because
``sources.py`` is the only module under ``src/`` permitted to branch on
``spec.source`` (``tests/unit/test_source_resolver_boundary.py`` enforces
that boundary via an AST walk) — every code path that could reach
``HuggingFaceSource`` passes through ``resolve_source`` first.
"""

from __future__ import annotations

import pytest

from veriface.errors import ArtifactSourceError
from veriface.models.sources import resolve_source
from veriface.models.specs import PROFILES, ArtifactSpec


def _hf_spec_with_member() -> ArtifactSpec:
    return ArtifactSpec(
        name="fake-hf-spec",
        source="hf",
        locator="fake-org/fake-repo",
        revision="0" * 40,
        filename="fake.onnx",
        member="inner/file.onnx",
        archive_sha256="b" * 64,
        sha256="a" * 64,
        license="Apache-2.0",
        training_data_provenance="synthetic fixture, not a real model",
    )


def test_resolve_source_rejects_hf_spec_with_a_member() -> None:
    with pytest.raises(ArtifactSourceError, match="member"):
        resolve_source(_hf_spec_with_member())


def test_resolve_source_accepts_https_spec_with_a_member() -> None:
    spec = ArtifactSpec(
        name="fake-https-spec",
        source="https",
        locator="https://example.invalid/archive.zip",
        revision="v0",
        filename="fake.onnx",
        member="inner/file.onnx",
        archive_sha256="b" * 64,
        sha256="a" * 64,
        license="Apache-2.0",
        training_data_provenance="synthetic fixture, not a real model",
    )
    source = resolve_source(spec)
    assert source.__class__.__name__ == "HttpsSource"


def test_no_declared_hf_sourced_spec_declares_a_member() -> None:
    """Belt-and-suspenders: a future PROFILES entry that pastes an
    archive-member spec's fields onto an 'hf' source fails CI directly,
    rather than only failing the first time something calls resolve_source."""
    for profile_name, specs in PROFILES.items():
        for spec in specs:
            if spec.source == "hf":
                assert spec.member is None, (
                    f"{profile_name}/{spec.name} is source='hf' but declares "
                    f"member={spec.member!r} — HuggingFaceSource never reads it"
                )
