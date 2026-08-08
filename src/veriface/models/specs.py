"""Artifact spec table.

``ArtifactSpec`` is source-agnostic (D-06): every row records
``{source, locator, revision, sha256, license, training_data_provenance}``,
regardless of whether the artifact ultimately comes from the Hugging Face
Hub or a plain HTTPS URL. ``PROFILES`` is keyed by profile name from day one
(D-10) so a second profile is a data change, not a refactor.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ArtifactSourceKind = Literal["hf", "https"]


class ArtifactSpec(BaseModel):
    """A single pinned, hash-verified, licensed model artifact.

    ``license`` and ``training_data_provenance`` are required with no
    defaults and a minimum length — a spec that omits either fails
    validation (D-37), making it structurally impossible to add a model
    without recording its provenance.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    source: ArtifactSourceKind
    locator: str
    """HF repo id for the ``hf`` source, or an https URL for the ``https`` source."""
    revision: str
    """Full 40-character commit hash for the ``hf`` source; a release tag or
    empty string for the ``https`` source."""
    filename: str
    member: str | None = None
    """Path inside an archive, for sources whose artifact is a member of a
    downloaded archive rather than a standalone file."""
    sha256: str
    license: str = Field(min_length=1)
    training_data_provenance: str = Field(min_length=1)


PROFILES: dict[str, tuple[ArtifactSpec, ...]] = {
    "default": (
        ArtifactSpec(
            name="minifasnet_v2",
            source="hf",
            locator="garciafido/minifasnet-v2-anti-spoofing-onnx",
            revision="d29c87568ca9b5662da803b10f217c4db20b142b",
            filename="minifasnet_v2.onnx",
            sha256="d7b3cd9ba8a7ceb13baa8c4720902e27ca3112eff52f926c08804af6b6eecc7b",
            license="Apache-2.0",
            training_data_provenance=(
                "Minivision AI's own presentation-attack-detection dataset, via "
                "minivision-ai/Silent-Face-Anti-Spoofing (MiniFASNetV2, "
                "2.7_80x80). ONNX conversion by garciafido/minifasnet-v2-anti-"
                "spoofing-onnx on Hugging Face Hub, weights bit-equivalent to "
                "upstream .pth, format-converted only. Not derived from "
                "MS-Celeb-1M or any face-recognition training corpus."
            ),
        ),
    ),
}
