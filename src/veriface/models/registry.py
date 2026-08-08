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
from dataclasses import dataclass
from pathlib import Path

import structlog

from veriface.config import VerifaceSettings
from veriface.errors import ArtifactIntegrityError, ArtifactNotCachedError, VerifaceError
from veriface.hashing import sha256_bytes, sha256_file
from veriface.models.runtime import Session, open_session
from veriface.models.sources import resolve_source
from veriface.models.specs import PROFILES, ArtifactSpec

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class FetchOutcome:
    """The result of fetching one spec: its cached path, and whether a
    pin-mismatch repair happened along the way (T-01-32 — a repair must be
    visible, not indistinguishable from a no-op fetch)."""

    path: Path
    repaired: bool


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
            outcome = self._fetch_one(spec)
            paths.append(outcome.path)
        return paths

    def fetch_each(
        self, profile: str
    ) -> Iterator[tuple[ArtifactSpec, FetchOutcome | VerifaceError]]:
        """Download every spec in ``profile``, yielding a per-spec result.

        Unlike ``fetch``, a single spec's failure does not abort the rest of
        the profile — each ``(spec, result)`` pair carries either the
        ``FetchOutcome`` that spec materialized to or the ``VerifaceError``
        it raised, so a caller (the CLI's ``fetch`` command) can report every
        failure without re-implementing this loop or reaching for the
        network itself (WR-01: this and ``fetch`` remain the only
        network-permitted methods).
        """
        for spec in PROFILES[profile]:
            try:
                outcome = self._fetch_one(spec)
            except VerifaceError as exc:
                yield spec, exc
                continue
            yield spec, outcome

    def _fetch_one(self, spec: ArtifactSpec) -> FetchOutcome:
        """Materialize ``spec``, verify it against its pin, and repair once
        on a mismatch (T-01-01, T-01-29).

        A cached artifact is hashed before it is ever reported as fetched.
        On a match it is returned untouched — a warm cache costs one hash,
        never a re-download. On a mismatch a structured event names the
        spec, the source is asked for exactly one forced re-materialization,
        and the result is hashed again: a second failure is upstream drift,
        not local corruption, and a loop cannot fix that, so it becomes a
        named ``ArtifactIntegrityError`` rather than another retry.
        """
        source = resolve_source(spec)
        path = source.materialize(spec, self._settings.cache_dir, allow_download=True)
        computed = sha256_file(path)
        if computed == spec.sha256:
            return FetchOutcome(path=path, repaired=False)

        logger.warning(
            "artifact_pin_mismatch_repairing",
            spec_name=spec.name,
            expected_sha256=spec.sha256,
            computed_sha256=computed,
            cached_path=str(path),
        )
        path = source.materialize(spec, self._settings.cache_dir, allow_download=True, force=True)
        computed = sha256_file(path)
        if computed != spec.sha256:
            raise ArtifactIntegrityError(spec.name, spec.sha256, computed, path)
        return FetchOutcome(path=path, repaired=True)

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

        Reads ``cached_path`` exactly once into memory and verifies/loads
        that same buffer (WR-08) — a second by-name open of ``cached_path``
        for ``open_session`` would leave a TOCTOU window in which a process
        with write access to the cache directory could swap the file's
        contents between the digest check and session construction.
        """
        cached_path = self.path(spec)
        model_bytes = cached_path.read_bytes()
        computed_sha256 = sha256_bytes(model_bytes)
        if computed_sha256 != spec.sha256:
            raise ArtifactIntegrityError(spec.name, spec.sha256, computed_sha256, cached_path)
        logger.info(
            "artifact_verified",
            spec_name=spec.name,
            revision=spec.revision,
            sha256=computed_sha256,
        )
        return open_session(model_bytes, source_label=cached_path)


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
