"""Two-tier CelebA-Spoof dataset config: budgets, and the manifest digest as a
checked precondition of use (D-19, D-20, D-25).

``TIERS`` declares both the ``eval`` and ``extended`` tiers now, even though
Phase 1 only materializes ``eval`` (D-20) — declaring the shape of a decision
before it needs to be exercised is what makes "materialize the extended tier"
a data change in Phase 3, not a refactor. ``DATASET_CONFIGS`` pairs each
tier with its committed manifest's expected SHA-256; both currently hold the
sentinel because plan 01-07 has not generated the real eval-tier manifest
yet, and ``load_dataset_config`` refuses to treat that sentinel as "fine".
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from veriface.errors import VerifaceError
from veriface_eval.datasets.manifest import manifest_sha256

MANIFEST_DIR = Path(__file__).resolve().parent / "manifests"

SENTINEL_MANIFEST_SHA256 = "0" * 64
"""Explicit "no real manifest generated yet" marker (D-19). A placeholder
digest that silently verified as "fine" would be worse than no check at
all — ``verify_manifest_digest`` rejects this exact value before ever
comparing it to a computed hash."""


class TierNotFoundError(VerifaceError):
    """Raised when a tier name is not one of ``TIERS``' declared keys."""

    def __init__(self, tier: str) -> None:
        self.tier = tier
        super().__init__(f"Unknown dataset tier {tier!r}; known tiers: {sorted(TIERS)}")


class SentinelManifestDigestError(VerifaceError):
    """Raised when a tier's recorded manifest digest is still the sentinel."""

    def __init__(self, tier: str, manifest_path: Path) -> None:
        self.tier = tier
        self.manifest_path = manifest_path
        super().__init__(
            f"Tier {tier!r} has no recorded manifest digest yet (sentinel) — "
            f"generate {manifest_path} with `veriface data manifest build --tier {tier}` "
            "and record its real sha256 in DATASET_CONFIGS before use."
        )


class ManifestDigestMismatchError(VerifaceError):
    """Raised when a manifest's computed digest does not match its recorded pin."""

    def __init__(self, manifest_path: Path, expected: str, computed: str) -> None:
        self.manifest_path = manifest_path
        self.expected = expected
        self.computed = computed
        super().__init__(
            f"Manifest {manifest_path} digest mismatch: expected sha256={expected} but "
            f"computed sha256={computed}. The manifest was altered after being pinned — "
            "this invalidates every metric computed against the old manifest (D-19). "
            "Regenerate deliberately with `veriface data manifest build --tier <tier> --force` "
            "if this is intentional, and record the new digest."
        )


class TierSpec(BaseModel):
    """One tier's declared budget, sampling target, and materialization phase."""

    model_config = ConfigDict(frozen=True)

    name: str
    size_budget_bytes: int
    target_subjects: int
    class_balance_tolerance: float
    manifest_filename: str
    materialised_in_phase: int


class DatasetConfig(BaseModel):
    """A tier paired with its committed manifest's path and expected digest."""

    model_config = ConfigDict(frozen=True)

    tier: str
    manifest_path: Path
    manifest_sha256: str


# D-20: ~5 GB eval tier materialized in Phase 1, ~15 GB extended tier declared
# now but materialized only in Phase 3 (and only if per-attack-class APCER
# confidence intervals prove too wide without it). target_subjects values are
# provisional Phase 1 estimates (roughly size_budget / (~61 images/subject
# average x ~8 KB/image), not a measured CelebA-Spoof fact) — plan 01-07's
# spike measures the real per-subject footprint and may adjust these.
TIERS: dict[str, TierSpec] = {
    "eval": TierSpec(
        name="eval",
        size_budget_bytes=5 * 1024**3,
        target_subjects=600,
        class_balance_tolerance=0.0,
        manifest_filename="celeba_spoof_eval.csv",
        materialised_in_phase=1,
    ),
    "extended": TierSpec(
        name="extended",
        size_budget_bytes=15 * 1024**3,
        target_subjects=1800,
        class_balance_tolerance=0.0,
        manifest_filename="celeba_spoof_extended.csv",
        materialised_in_phase=3,
    ),
}

DATASET_CONFIGS: dict[str, DatasetConfig] = {
    tier_name: DatasetConfig(
        tier=tier_name,
        manifest_path=MANIFEST_DIR / tier_spec.manifest_filename,
        manifest_sha256=SENTINEL_MANIFEST_SHA256,
    )
    for tier_name, tier_spec in TIERS.items()
}


def manifest_path_for(tier: str) -> Path:
    """Resolve ``tier``'s committed manifest path — call-time, not import-time,
    so tests can monkeypatch ``MANIFEST_DIR`` cleanly."""
    if tier not in TIERS:
        raise TierNotFoundError(tier)
    return MANIFEST_DIR / TIERS[tier].manifest_filename


def verify_manifest_digest(manifest_path: Path, expected_sha256: str) -> None:
    """Recompute ``manifest_path``'s digest and compare against ``expected_sha256``.

    Raises ``SentinelManifestDigestError`` if ``expected_sha256`` is still the
    sentinel, or ``ManifestDigestMismatchError`` on a real mismatch. Returns
    ``None`` (no exception) when the digests match.
    """
    if expected_sha256 == SENTINEL_MANIFEST_SHA256:
        raise SentinelManifestDigestError("(unknown)", manifest_path)
    computed = manifest_sha256(manifest_path)
    if computed != expected_sha256:
        raise ManifestDigestMismatchError(manifest_path, expected_sha256, computed)


def load_dataset_config(tier: str) -> DatasetConfig:
    """Resolve ``tier``'s ``DatasetConfig`` and re-check its manifest digest (D-25).

    This is the check the eval harness must run before every evaluation run
    — a re-verified digest, not a recorded-and-forgotten fact.
    """
    if tier not in DATASET_CONFIGS:
        raise TierNotFoundError(tier)
    config = DATASET_CONFIGS[tier]
    try:
        verify_manifest_digest(config.manifest_path, config.manifest_sha256)
    except SentinelManifestDigestError as exc:
        raise SentinelManifestDigestError(tier, config.manifest_path) from exc
    return config


__all__ = [
    "DATASET_CONFIGS",
    "MANIFEST_DIR",
    "SENTINEL_MANIFEST_SHA256",
    "TIERS",
    "DatasetConfig",
    "ManifestDigestMismatchError",
    "SentinelManifestDigestError",
    "TierNotFoundError",
    "TierSpec",
    "load_dataset_config",
    "manifest_path_for",
    "verify_manifest_digest",
]
