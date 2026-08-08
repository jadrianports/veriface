"""Source resolution for artifact specs.

``resolve_source`` is the ONLY site in ``src/`` permitted to branch on
``spec.source`` (see the assumption-delta decision in
``01-01-PLAN.md``) — every other module works through the
``ArtifactSource`` protocol. ``tests/unit/test_source_resolver_boundary.py``
(plan 01-02) walks the AST of every module under ``src/`` to enforce this.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Protocol
from urllib.parse import urlparse

import httpx
from huggingface_hub import hf_hub_download
from huggingface_hub.errors import LocalEntryNotFoundError

from veriface.errors import ArtifactIntegrityError, ArtifactSourceError
from veriface.hashing import sha256_file
from veriface.models.specs import ArtifactSpec

_DOWNLOAD_CHUNK_SIZE = 1 << 20  # 1 MiB — never buffer a multi-hundred-MB archive in memory


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


def validate_member_path(member: str) -> None:
    """Reject an archive member path that is absolute or escapes its root.

    Checked against both POSIX and Windows path semantics regardless of the
    host OS running this check (mirrors D-28's platform-independent path
    testing) — a member name containing a backslash-based parent-directory
    component must be rejected even when this process runs on Linux CI, and
    a forward-slash one must be rejected even when this process runs on
    Windows. This is T-01-03's traversal defence.
    """
    for path_cls in (PurePosixPath, PureWindowsPath):
        candidate = path_cls(member)
        if candidate.is_absolute():
            raise ArtifactSourceError(f"Archive member {member!r} is an absolute path")
        if ".." in candidate.parts:
            raise ArtifactSourceError(
                f"Archive member {member!r} contains a parent-directory component"
            )


def extract_member_safely(container_path: Path, member: str, extract_root: Path) -> Path:
    """Extract exactly ``member`` from the zip at ``container_path`` into ``extract_root``.

    Never calls ``ZipFile.extractall`` — reads the central directory and
    extracts only the single requested entry (T-01-03). The destination is
    resolved as ``(extract_root / member).resolve()`` and validated to have
    ``extract_root.resolve()`` as a parent before anything is written; a
    member name that is absolute, contains a parent-directory component, or
    resolves outside ``extract_root`` raises ``ArtifactSourceError`` with
    nothing written outside ``extract_root``.
    """
    validate_member_path(member)
    extract_root.mkdir(parents=True, exist_ok=True)
    resolved_root = extract_root.resolve()
    dest_path = (extract_root / member).resolve()
    try:
        dest_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ArtifactSourceError(
            f"Archive member {member!r} resolves outside the extraction root"
        ) from exc

    with zipfile.ZipFile(container_path) as archive:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as src, dest_path.open("wb") as dst:
            shutil.copyfileobj(src, dst)
    return dest_path


class HttpsSource:
    """Resolves specs whose ``source`` is ``"https"`` via a plain HTTPS download.

    Two shapes, distinguished by whether ``spec.member`` is set:
    - ``member`` is ``None``: ``spec.locator`` is downloaded directly to a
      ``.part`` temp file, verified against ``spec.sha256`` with
      ``sha256_file`` (WR-02 — a fetch-time check symmetric with the
      archive-member shape below, not deferred to the next ``verify``/``load``
      call), and only then renamed into the cache under ``spec.filename``. A
      digest mismatch deletes the ``.part`` file and raises
      ``ArtifactIntegrityError`` before anything is cached.
    - ``member`` is set: ``spec.locator`` is an archive. The archive is
      streamed to a temporary file, verified against ``spec.archive_sha256``
      with ``sha256_file`` *before* ``zipfile.ZipFile`` is ever constructed
      (T-01-10 — a hostile container never reaches the parser), then exactly
      ``member`` is extracted (T-01-03) and the archive is deleted (T-01-12
      — a multi-hundred-MB container never sits in the cache permanently).
    """

    def materialize(self, spec: ArtifactSpec, cache_dir: Path, *, allow_download: bool) -> Path:
        dest_dir = cache_dir / "https" / spec.name
        dest_path = dest_dir / spec.filename
        if dest_path.exists():
            return dest_path
        if not allow_download:
            # D-12: the offline path must not construct an httpx client at all.
            raise FileNotFoundError(f"Artifact {spec.name!r} is not cached in {cache_dir}")

        dest_dir.mkdir(parents=True, exist_ok=True)
        if spec.member is not None:
            self._materialize_archive_member(spec, dest_dir, dest_path)
        else:
            self._materialize_direct_file(spec, dest_dir, dest_path)
        return dest_path

    def _materialize_direct_file(self, spec: ArtifactSpec, dest_dir: Path, dest_path: Path) -> None:
        tmp_path = dest_dir / f"{spec.filename}.part"
        self._download(spec.locator, tmp_path)

        computed = sha256_file(tmp_path)
        if computed != spec.sha256:
            tmp_path.unlink(missing_ok=True)
            raise ArtifactIntegrityError(spec.name, spec.sha256, computed, tmp_path)

        tmp_path.replace(dest_path)

    def _materialize_archive_member(
        self, spec: ArtifactSpec, dest_dir: Path, dest_path: Path
    ) -> None:
        assert spec.member is not None  # narrowed by the caller
        assert spec.archive_sha256 is not None  # enforced by ArtifactSpec's model validator
        container_path = dest_dir / "_container.zip.part"
        self._download(spec.locator, container_path)

        computed = sha256_file(container_path)
        if computed != spec.archive_sha256:
            container_path.unlink(missing_ok=True)
            raise ArtifactIntegrityError(
                f"{spec.name} (archive)", spec.archive_sha256, computed, container_path
            )

        extracted_path = extract_member_safely(container_path, spec.member, dest_dir)
        if extracted_path != dest_path:
            extracted_path.replace(dest_path)
        container_path.unlink()

    @staticmethod
    def _download(url: str, dest_path: Path) -> None:
        """Stream ``url`` to ``dest_path`` in chunks — never buffers the full body in memory."""
        with httpx.stream("GET", url, follow_redirects=True) as response:
            response.raise_for_status()
            with dest_path.open("wb") as fh:
                for chunk in response.iter_bytes(chunk_size=_DOWNLOAD_CHUNK_SIZE):
                    fh.write(chunk)


def resolve_source(spec: ArtifactSpec) -> ArtifactSource:
    """Dispatch on ``spec.source`` to the matching resolver.

    Raises ``ArtifactSourceError`` for an unknown source value, and for an
    ``hf``-source spec that also declares a non-null ``member`` (WR-03):
    ``HuggingFaceSource.materialize`` never reads ``spec.member``, so that
    combination would otherwise silently download and cache the whole HF
    asset instead of extracting the intended archive member. This check
    belongs here rather than as an ``ArtifactSpec`` model validator because
    ``resolve_source`` is the one place under ``src/`` permitted to branch on
    ``spec.source`` (see the module docstring) — every code path that could
    reach ``HuggingFaceSource`` passes through here first, so the invalid
    combination is caught before any network call, not merely documented.
    """
    if spec.source == "hf":
        if spec.member is not None:
            raise ArtifactSourceError(
                f"ArtifactSpec {spec.name!r} declares a non-null member "
                f"({spec.member!r}) but source='hf' — HuggingFaceSource never reads "
                "spec.member; an archive-member spec must use source='https'."
            )
        return HuggingFaceSource()
    if spec.source == "https":
        return HttpsSource()
    raise ArtifactSourceError(f"Unknown artifact source {spec.source!r} for spec {spec.name!r}")


def describe_source(spec: ArtifactSpec) -> str:
    """Human-readable ``"<kind> (<host>)"`` label for documentation renderers.

    Lives here rather than in ``licensing.py`` precisely because computing it
    requires branching on ``spec.source`` — this module is the only one
    permitted to make that branch (see the module docstring).
    """
    if spec.source == "hf":
        return f"{spec.source} (huggingface.co)"
    return f"{spec.source} ({urlparse(spec.locator).netloc})"
