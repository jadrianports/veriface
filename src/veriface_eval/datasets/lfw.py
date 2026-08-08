"""LFW archive fetch, digest verification, and extraction under the data dir.

``LFW_SPEC`` records the archive this module fetches and its pinned digest.
``fetch_lfw`` streams it, verifies the digest with the core ``sha256_file``
helper *before* any extraction happens, extracts under
``data_dir / LFW_SPEC.extraction_subdir``, and deletes the archive afterward.

Host choice (Claude's Discretion, D-11/CONTEXT.md): the canonical UMass host
(``vis-www.cs.umass.edu``) did not resolve from this network during planning
research or during this plan's execution (DNS failure, confirmed live this
session — see 01-04-SUMMARY.md). ``ndownloader.figshare.com`` is used
instead: it is scikit-learn's own official LFW mirror (the exact URL
``sklearn.datasets.fetch_lfw_people``/``fetch_lfw_pairs`` resolve to), not an
anonymous third-party re-host, and LFW itself carries no restrictive
redistribution terms (PITFALLS.md Pitfall 4: "fully public, no agreement").
The archive is the funneled variant (``lfw-funneled.tgz``) and its own
top-level directory (``lfw_funneled/``) already contains the standard
``pairs.txt`` plus the ten ``pairs_NN.txt`` cross-validation folds — verified
by listing the real downloaded archive's members this session — so no
second ``LFW_SPEC`` entry is needed for the pairs file.
"""

from __future__ import annotations

import tarfile
from pathlib import Path, PurePosixPath

import httpx

from veriface.errors import ArtifactIntegrityError, ArtifactSourceError
from veriface.hashing import sha256_file
from veriface.models.sources import validate_member_path

_DOWNLOAD_CHUNK_SIZE = 1 << 20  # 1 MiB — never buffer the full archive in memory


class DatasetArchiveSpec:
    """A single pinned, hash-verified dataset archive.

    Deliberately not ``veriface.models.specs.ArtifactSpec`` — that model is
    keyed to the model-registry's ``{hf, https}`` source vocabulary and its
    ``spec.source``-branching boundary test (``test_source_resolver_boundary.py``);
    a dataset archive has no such branch and reusing that type would blur the
    two registries' identities for no benefit.
    """

    __slots__ = ("name", "url", "sha256", "license", "extraction_subdir")

    def __init__(
        self, *, name: str, url: str, sha256: str, license: str, extraction_subdir: str
    ) -> None:
        self.name = name
        self.url = url
        self.sha256 = sha256
        self.license = license
        self.extraction_subdir = extraction_subdir


LFW_SPEC = DatasetArchiveSpec(
    name="lfw",
    url="https://ndownloader.figshare.com/files/5976015",
    # Bootstrapped from the bytes actually downloaded this session (2026-08-08),
    # 243,346,528 bytes — never invented, never copied from a secondary source.
    sha256="b47c8422c8cded889dc5a13418c4bc2abbda121092b3533a83306f90d900100a",
    license="public research benchmark, standard academic terms",
    extraction_subdir="lfw",
)

_MARKER_FILENAME = ".materialized"


def _download(url: str, dest_path: Path) -> None:
    """Stream ``url`` to ``dest_path`` in chunks — never buffers the full body in memory."""
    with httpx.stream("GET", url, follow_redirects=True) as response:
        response.raise_for_status()
        with dest_path.open("wb") as fh:
            for chunk in response.iter_bytes(chunk_size=_DOWNLOAD_CHUNK_SIZE):
                fh.write(chunk)


def _extract_tar_safely(
    archive_path: Path, extract_root: Path, *, strip_components: int = 0
) -> None:
    """Extract every regular file/directory member of ``archive_path`` under ``extract_root``.

    A dataset tarball is no more trustworthy than a model zip (T-01-03): every
    member name is validated with the same POSIX/Windows traversal guard
    ``veriface.models.sources.validate_member_path`` uses for model archives,
    and the resolved destination is required to stay inside ``extract_root``
    before anything is written. ``strip_components`` drops that many leading
    path segments from every member (mirrors ``tar --strip-components``) so
    the archive's own wrapping directory does not nest under
    ``extract_root`` a second time. Symlinks, hardlinks, device nodes, and
    FIFOs are rejected outright — a dataset archive has no legitimate reason
    to contain any of them.
    """
    extract_root.mkdir(parents=True, exist_ok=True)
    resolved_root = extract_root.resolve()

    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            if not (member.isfile() or member.isdir()):
                raise ArtifactSourceError(
                    f"Archive member {member.name!r} is not a regular file or "
                    "directory (symlink/device/fifo) — refusing to extract"
                )
            parts = PurePosixPath(member.name).parts
            if len(parts) <= strip_components:
                continue  # the wrapping directory entry itself
            relative = PurePosixPath(*parts[strip_components:])
            validate_member_path(str(relative))
            dest_path = (extract_root / relative).resolve()
            try:
                dest_path.relative_to(resolved_root)
            except ValueError as exc:
                raise ArtifactSourceError(
                    f"Archive member {member.name!r} resolves outside the extraction root"
                ) from exc

            if member.isdir():
                dest_path.mkdir(parents=True, exist_ok=True)
                continue
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            src = archive.extractfile(member)
            if src is None:  # pragma: no cover - unreachable given the isfile() guard above
                raise ArtifactSourceError(f"Archive member {member.name!r} has no readable content")
            with src, dest_path.open("wb") as dst:
                while True:
                    chunk = src.read(_DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    dst.write(chunk)


def fetch_lfw(data_dir: Path, *, allow_download: bool) -> Path:
    """Materialize LFW under ``data_dir / LFW_SPEC.extraction_subdir``.

    Streams the archive, verifies its digest with ``sha256_file`` *before*
    any extraction is attempted, extracts every member with the tar
    containment guard, deletes the archive on success, and writes a
    ``.materialized`` marker so a later call is idempotent. Never triggers a
    download when ``allow_download`` is ``False`` (D-12's no-implicit-fetch
    posture, applied to datasets as well as models).
    """
    dest_dir = data_dir / LFW_SPEC.extraction_subdir
    marker_path = dest_dir / _MARKER_FILENAME
    if marker_path.exists():
        return dest_dir

    if not allow_download:
        raise FileNotFoundError(f"Dataset {LFW_SPEC.name!r} is not materialized under {dest_dir}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    archive_path = dest_dir / f"_{LFW_SPEC.name}.tgz.part"
    _download(LFW_SPEC.url, archive_path)

    computed = sha256_file(archive_path)
    if computed != LFW_SPEC.sha256:
        archive_path.unlink(missing_ok=True)
        raise ArtifactIntegrityError(
            f"{LFW_SPEC.name} (archive)", LFW_SPEC.sha256, computed, archive_path
        )

    _extract_tar_safely(archive_path, dest_dir, strip_components=1)
    archive_path.unlink()
    marker_path.write_text("ok\n", encoding="utf-8")
    return dest_dir


__all__ = ["DatasetArchiveSpec", "LFW_SPEC", "fetch_lfw"]
