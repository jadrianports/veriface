"""The model artifact registry — the only code path (with ``runtime.py``)
permitted to reach the network or construct an ``InferenceSession``.

``fetch`` is the only network-permitted path. ``path`` never downloads
(D-12) and converts a cache miss into ``ArtifactNotCachedError``. ``load``
recomputes the full SHA-256 digest on every call — no memoisation, no
size/mtime shortcut, no environment-variable bypass (D-09, T-01-01) — before
constructing a session.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import structlog

from veriface.config import VerifaceSettings
from veriface.errors import ArtifactIntegrityError, ArtifactNotCachedError, VerifaceError
from veriface.hashing import sha256_file
from veriface.models.runtime import Session, open_session
from veriface.models.sources import resolve_source
from veriface.models.specs import PROFILES, ArtifactSpec

logger = structlog.get_logger(__name__)


class ModelRegistry:
    """Fetches, verifies, and loads model artifacts for a given profile."""

    def __init__(self, settings: VerifaceSettings) -> None:
        self._settings = settings

    def fetch(self, profile: str) -> list[Path]:
        """Download every spec in ``profile``, returning their cached paths.

        Raises on the first failing spec — for a caller that wants to keep
        going and report every failure individually, use ``fetch_each``
        instead. Together, ``fetch``/``fetch_each`` are the only methods on
        this class permitted to touch the network.
        """
        paths: list[Path] = []
        for spec in PROFILES[profile]:
            source = resolve_source(spec)
            path = source.materialize(spec, self._settings.cache_dir, allow_download=True)
            paths.append(path)
        return paths

    def fetch_each(self, profile: str) -> Iterator[tuple[ArtifactSpec, Path | VerifaceError]]:
        """Download every spec in ``profile``, yielding a per-spec result.

        Unlike ``fetch``, a single spec's failure does not abort the rest of
        the profile — each ``(spec, result)`` pair carries either the
        materialized ``Path`` or the ``VerifaceError`` that spec raised, so a
        caller (the CLI's ``fetch`` command) can report every failure without
        re-implementing this loop or reaching for the network itself (WR-01:
        this and ``fetch`` remain the only network-permitted methods).
        """
        for spec in PROFILES[profile]:
            source = resolve_source(spec)
            try:
                path = source.materialize(spec, self._settings.cache_dir, allow_download=True)
            except VerifaceError as exc:
                yield spec, exc
                continue
            yield spec, path

    def path(self, spec: ArtifactSpec) -> Path:
        """Return the cached local path for ``spec`` without downloading.

        Raises ``ArtifactNotCachedError`` if the artifact is not already
        cached — loading a missing artifact never triggers a download
        (D-12).
        """
        source = resolve_source(spec)
        try:
            return source.materialize(spec, self._settings.cache_dir, allow_download=False)
        except FileNotFoundError as exc:
            profile = _profile_for_spec(spec)
            raise ArtifactNotCachedError(spec.name, profile) from exc

    def load(self, spec: ArtifactSpec) -> Session:
        """Verify ``spec``'s cached artifact and open it as a CPU-only session.

        The SHA-256 comparison runs on every call with no cached result
        (D-09): raises ``ArtifactIntegrityError`` naming the spec, the
        expected digest, the computed digest, and the cached path on
        mismatch, and only then calls ``open_session``.
        """
        cached_path = self.path(spec)
        computed_sha256 = sha256_file(cached_path)
        if computed_sha256 != spec.sha256:
            raise ArtifactIntegrityError(spec.name, spec.sha256, computed_sha256, cached_path)
        logger.info(
            "artifact_verified",
            spec_name=spec.name,
            revision=spec.revision,
            sha256=computed_sha256,
        )
        return open_session(cached_path)


def _profile_for_spec(spec: ArtifactSpec) -> str:
    """Best-effort reverse lookup of the profile name containing ``spec``.

    Used only to render an actionable error message; falls back to
    ``"default"`` if the spec is not found in any known profile (e.g. a
    caller-constructed spec used in a test).
    """
    for profile_name, specs in PROFILES.items():
        if spec in specs:
            return profile_name
    return "default"
