"""License matrix and NOTICE body generation (D-37).

Both renderers read only ``PROFILES`` (or an explicitly injected profiles
mapping, for testability) so the rendered document can never drift from what
``veriface models fetch`` actually fetches. Neither renderer branches on
``spec.source`` directly — the "Source" column's host label is computed by
``sources.describe_source``, the sanctioned single branch site.
"""

from __future__ import annotations

from collections.abc import Mapping

from veriface.errors import VerifaceError
from veriface.models.sources import describe_source
from veriface.models.specs import PROFILES, ArtifactSpec

_REVISION_DISPLAY_LENGTH = 12


class LicenseMetadataError(VerifaceError):
    """Raised when a spec's ``license`` or ``training_data_provenance`` is blank.

    Pydantic's ``Field(min_length=1)`` on ``ArtifactSpec`` catches an empty
    string at construction time; this catches a whitespace-only string that
    would otherwise satisfy ``min_length=1`` but render as nothing.
    """


def _iter_unique_specs(profiles: Mapping[str, tuple[ArtifactSpec, ...]]) -> list[ArtifactSpec]:
    """Every spec across ``profiles``, deduplicated by name, in declared order."""
    seen: set[str] = set()
    ordered: list[ArtifactSpec] = []
    for specs in profiles.values():
        for spec in specs:
            if spec.name in seen:
                continue
            seen.add(spec.name)
            ordered.append(spec)
    return ordered


def _validate_licensing_fields(spec: ArtifactSpec) -> None:
    if not spec.license.strip():
        raise LicenseMetadataError(f"ArtifactSpec {spec.name!r} has a blank license")
    if not spec.training_data_provenance.strip():
        raise LicenseMetadataError(
            f"ArtifactSpec {spec.name!r} has a blank training_data_provenance"
        )


def _escape_cell(text: str) -> str:
    """Escape ``|`` so a cell's own text cannot break a Markdown table row."""
    return text.replace("|", "\\|")


def render_license_matrix(
    profiles: Mapping[str, tuple[ArtifactSpec, ...]] = PROFILES,
) -> str:
    """Render a GitHub-flavoured Markdown license matrix from ``profiles``.

    One row per distinct artifact name across every profile, in declared
    order. Columns: Artifact, Source, Revision, Licence, Training data.
    Repeated calls with the same ``profiles`` return byte-identical output.
    Raises ``LicenseMetadataError`` if any spec is missing license or
    training-data-provenance text.
    """
    specs = _iter_unique_specs(profiles)
    for spec in specs:
        _validate_licensing_fields(spec)

    lines = [
        "| Artifact | Source | Revision | Licence | Training data |",
        "| --- | --- | --- | --- | --- |",
    ]
    for spec in specs:
        cells = (
            spec.name,
            describe_source(spec),
            spec.revision[:_REVISION_DISPLAY_LENGTH],
            spec.license,
            spec.training_data_provenance,
        )
        lines.append("| " + " | ".join(_escape_cell(cell) for cell in cells) + " |")
    return "\n".join(lines) + "\n"


def render_notice(
    profiles: Mapping[str, tuple[ArtifactSpec, ...]] = PROFILES,
) -> str:
    """Render the Apache-2.0 NOTICE body enumerating every third-party artifact.

    Never collapses differing third-party terms into veriface's own
    Apache-2.0 grant (D-36) — each artifact's actual license text and
    training-data provenance are stated verbatim. Raises
    ``LicenseMetadataError`` under the same conditions as
    ``render_license_matrix``.
    """
    specs = _iter_unique_specs(profiles)
    for spec in specs:
        _validate_licensing_fields(spec)

    lines = [
        "veriface",
        "Copyright the veriface project contributors.",
        "",
        "This product is licensed under the Apache License, Version 2.0.",
        "You may obtain a copy of the License at",
        "http://www.apache.org/licenses/LICENSE-2.0",
        "",
        "Third-party model artifacts",
        "----------------------------",
        "",
        (
            "veriface does not vendor or redistribute any model weights. The "
            "artifacts below are downloaded at runtime, only at the user's "
            "explicit request (`veriface models fetch`), directly from each "
            "artifact's own upstream distribution."
        ),
        "",
    ]
    for spec in specs:
        lines.append(f"* {spec.name} ({spec.source}, revision {spec.revision})")
        lines.append(f"  License: {spec.license}")
        lines.append(f"  Training data provenance: {spec.training_data_provenance}")
        lines.append("")
    lines.append(
        "The non-commercial-research restriction carried by the InsightFace "
        "model-zoo artifacts above governs use of this project's default "
        "profile, regardless of veriface's own Apache-2.0 grant on its own "
        "source code."
    )
    return "\n".join(lines) + "\n"
