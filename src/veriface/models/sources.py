"""Source resolution for artifact specs.

``resolve_source`` is the ONLY site in ``src/`` permitted to branch on
``spec.source`` (see the assumption-delta decision in
``01-01-PLAN.md``) — every other module works through the
``ArtifactSource`` protocol. A future companion test
(``tests/unit/test_source_resolver_boundary.py``, plan 01-02) walks the AST
of every module under ``src/`` to enforce this.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from huggingface_hub import hf_hub_download
from huggingface_hub.errors import LocalEntryNotFoundError

from veriface.errors import ArtifactSourceError
from veriface.models.specs import ArtifactSpec


class ArtifactSource(Protocol):
    """A resolver capable of materializing an artifact spec to a local path."""

    def materialize(self, spec: ArtifactSpec, cache_dir: Path, *, allow_download: bool) -> Path:
        """Return the local path to ``spec``'s artifact.

        Raises ``FileNotFoundError`` if ``allow_download`` is ``False`` and
        the artifact is not already cached — never triggers a download in
        that case (D-12).
        """
        ...


class HuggingFaceSource:
    """Resolves specs whose ``source`` is ``"hf"`` via the Hugging Face Hub."""

    def materialize(self, spec: ArtifactSpec, cache_dir: Path, *, allow_download: bool) -> Path:
        try:
            path = hf_hub_download(
                repo_id=spec.locator,
                filename=spec.filename,
                revision=spec.revision,
                cache_dir=cache_dir,
                local_files_only=not allow_download,
            )
        except LocalEntryNotFoundError as exc:
            raise FileNotFoundError(f"Artifact {spec.name!r} is not cached in {cache_dir}") from exc
        return Path(path)


def resolve_source(spec: ArtifactSpec) -> ArtifactSource:
    """Dispatch on ``spec.source`` to the matching resolver.

    Raises ``ArtifactSourceError`` for an unknown source value.
    """
    if spec.source == "hf":
        return HuggingFaceSource()
    raise ArtifactSourceError(f"Unknown artifact source {spec.source!r} for spec {spec.name!r}")
