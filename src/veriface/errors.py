"""Exception hierarchy for veriface."""

from __future__ import annotations


class VerifaceError(Exception):
    """Base exception for every error veriface raises deliberately."""


class ArtifactNotCachedError(VerifaceError):
    """Raised when a spec's artifact is not present in the local cache.

    The message always names the exact command to run (``veriface models
    fetch --profile <profile>``) so the caller is told precisely what to do
    next — this class never triggers an implicit download (D-12).
    """

    def __init__(self, spec_name: str, profile: str) -> None:
        self.spec_name = spec_name
        self.profile = profile
        super().__init__(
            f"Artifact {spec_name!r} is not cached for profile {profile!r}. "
            f"Run `veriface models fetch --profile {profile}` to fetch it."
        )


class ArtifactIntegrityError(VerifaceError):
    """Raised when a cached artifact's SHA-256 digest does not match its pin.

    Names the spec, the expected digest, the computed digest, and the cached
    path so a mismatch is immediately actionable.
    """

    def __init__(
        self,
        spec_name: str,
        expected_sha256: str,
        computed_sha256: str,
        cached_path: object,
    ) -> None:
        self.spec_name = spec_name
        self.expected_sha256 = expected_sha256
        self.computed_sha256 = computed_sha256
        self.cached_path = cached_path
        super().__init__(
            f"Integrity check failed for artifact {spec_name!r} at {cached_path}: "
            f"expected sha256={expected_sha256} but computed sha256={computed_sha256}. "
            "The cached file is corrupted, truncated, or tampered with — delete it and "
            "re-run `veriface models fetch` to restore a verified copy."
        )


class ArtifactSourceError(VerifaceError):
    """Raised when an artifact spec names a source that cannot be resolved.

    Also raised when a pinned revision cannot be resolved upstream — an
    unavailable pin is a hard, named failure, never a silent substitution to
    a branch tip or latest.
    """
