"""Artifact spec table.

``ArtifactSpec`` is source-agnostic (D-06): every row records
``{source, locator, revision, sha256, license, training_data_provenance}``,
regardless of whether the artifact ultimately comes from the Hugging Face
Hub or a plain HTTPS URL. ``PROFILES`` is keyed by profile name from day one
(D-10) so a second profile is a data change, not a refactor.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    """Digest of the file ``materialize`` returns — the thing that gets loaded."""
    archive_sha256: str | None = None
    """Digest of the container ``sha256`` was extracted from, verified before
    the container is opened. Required exactly when ``member`` is set — the
    pairing cannot be half-declared (a model validator enforces this)."""
    license: str = Field(min_length=1)
    training_data_provenance: str = Field(min_length=1)

    @model_validator(mode="after")
    def _member_requires_archive_sha256(self) -> ArtifactSpec:
        if self.member is not None and self.archive_sha256 is None:
            raise ValueError(
                f"ArtifactSpec {self.name!r} declares a non-null member "
                f"({self.member!r}) but no archive_sha256 — a spec that names an "
                "archive member must also pin the container's own digest."
            )
        return self


_BUFFALO_L_URL = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
_BUFFALO_L_SHA256 = "80ffe37d8a5940d59a7384c201a2a38d4741f2f3c51eef46ebb28218a7b0ca2f"
_INSIGHTFACE_LICENSE = "InsightFace model zoo — non-commercial research use only"

PROFILES: dict[str, tuple[ArtifactSpec, ...]] = {
    "default": (
        ArtifactSpec(
            name="scrfd_10g_bnkps",
            source="https",
            locator=_BUFFALO_L_URL,
            revision="v0.7",
            filename="det_10g.onnx",
            member="det_10g.onnx",
            archive_sha256=_BUFFALO_L_SHA256,
            sha256="5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91",
            license=_INSIGHTFACE_LICENSE,
            training_data_provenance="InsightFace-curated detection training sets",
        ),
        ArtifactSpec(
            name="arcface_w600k_r50",
            source="https",
            locator=_BUFFALO_L_URL,
            revision="v0.7",
            filename="w600k_r50.onnx",
            member="w600k_r50.onnx",
            archive_sha256=_BUFFALO_L_SHA256,
            sha256="4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43",
            license=_INSIGHTFACE_LICENSE,
            training_data_provenance=(
                "MS1MV2/MS1MV3-family refined sets, cleaned derivatives of the "
                "withdrawn MS-Celeb-1M"
            ),
        ),
        ArtifactSpec(
            name="minifasnet_v1se",
            source="https",
            locator=(
                "https://github.com/yakhyo/face-anti-spoofing/releases/download/"
                "weights/MiniFASNetV1SE.onnx"
            ),
            revision="weights",
            filename="MiniFASNetV1SE.onnx",
            sha256="ebab7f90c7833fbccd46d3a555410e78d969db5438e169b6524be444862b3676",
            license="Apache-2.0",
            training_data_provenance=(
                "Minivision AI's own presentation-attack-detection dataset, via "
                "minivision-ai/Silent-Face-Anti-Spoofing (MiniFASNetV1SE, "
                "4.0_80x80). ONNX conversion by yakhyo/face-anti-spoofing "
                "(Apache-2.0), a direct re-export of the same upstream .pth "
                "weights — no HF Hub ONNX port of V1SE exists (verified during "
                "plan 01-02; see 01-02-SUMMARY.md). Not derived from MS-Celeb-1M "
                "or any face-recognition training corpus."
            ),
        ),
        ArtifactSpec(
            name="minifasnet_v2se",
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
