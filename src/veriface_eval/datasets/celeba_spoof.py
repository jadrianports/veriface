"""CelebA-Spoof volume download, reassembly, label-index build, manifest-driven
selective extraction, and cleanup (D-19, D-21, D-22, D-23, D-25).

**Acquisition is deferred to Phase 2.** Plan 01-07's spike (Task 2) measured the
real Google Drive distribution without downloading it — 74 split-zip volumes,
73 at a Drive-displayed ~1,000M each plus a final ~432M volume, totaling
roughly 71.7-77.0 GB depending on unit interpretation — against this machine's
actually-free disk (measured 74-76 GiB, not the stale 78.5 GB figure in
CLAUDE.md/D-20). No acquisition sequence fits inside the mandated 10 GB safety
floor; the developer decision at the Task 3 checkpoint was to defer rather
than force it. See ``docs/celeba-spoof-acquisition.md`` for the full measured
arithmetic and the rejected alternatives (including why a binary-labeled HF
mirror was considered and rejected).

Every function below is implemented for real — this module is what Phase 2
runs once disk headroom exists — but ``fetch_celeba_spoof`` refuses to start
a download today. It checks for the corpus's local presence first and raises
``AcquisitionDeferredError`` with a message naming the deferral and pointing
at the acquisition doc, rather than silently skipping or faking success
(T-01-05's disk-exhaustion mitigation applied at the orchestration layer,
not just the download layer).
"""

from __future__ import annotations

import json
import shutil
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from veriface.errors import ArtifactSourceError, VerifaceError
from veriface.models.sources import validate_member_path
from veriface_eval.datasets.manifest import LabelIndexEntry, ManifestRow, SpoofClass

ACQUISITION_DOC = "docs/celeba-spoof-acquisition.md"

GOOGLE_DRIVE_FOLDER_ID = "1OW_1bawO79pRqdVEVmBzp8HSxdSwln_Z"
"""The dataset's own Google Drive folder ID, per its GitHub README (verified
live in the 01-07 spike)."""

RAW_SUBDIR = "celeba_spoof/raw"
"""Where downloaded volumes and the reassembled archive live under
``VERIFACE_DATA_DIR``, before ``cleanup`` deletes them."""

_REASSEMBLED_NAME = "CelebA_Spoof.zip"


class AcquisitionDeferredError(VerifaceError):
    """Raised by ``fetch_celeba_spoof`` when the corpus is not locally present.

    This is the honest-degradation path (not a silent skip, not a fake
    success): every attempt to fetch CelebA-Spoof today fails loudly, naming
    the deferral decision and the document that records the measured reason
    for it.
    """

    def __init__(self, tier: str, raw_dir: Path) -> None:
        self.tier = tier
        self.raw_dir = raw_dir
        super().__init__(
            f"CelebA-Spoof ({tier!r} tier) acquisition is deferred — the corpus is not "
            f"present under {raw_dir}. This is a deliberate decision, not a bug: the "
            f"01-07 spike measured the full corpus (~71.7-77.0 GB) against this "
            f"machine's free disk (~74-76 GiB) and found no acquisition sequence fits "
            f"inside the mandated 10 GB safety floor. See {ACQUISITION_DOC} for the "
            "measured numbers and the rejected alternatives. To proceed once disk "
            f"headroom exists, place the 74 downloaded volumes under {raw_dir} (or run "
            "the acquisition manually) before calling this again."
        )


@dataclass(frozen=True, slots=True)
class CelebASpoofVolume:
    """One split-zip volume, as listed and size-probed by the 01-07 spike.

    ``displayed_size`` is Google Drive's own rounded confirmation-page
    display (e.g. ``"1,000M"``), **not** a byte-exact size — the spike could
    not obtain an exact byte count without downloading the volume, and
    downloading was blocked this session (see ``docs/celeba-spoof-acquisition.md``
    § Blockers). Treat this as a sanity-check bound (a volume dramatically
    short of its displayed size is a failed/truncated download), not a strict
    equality check.
    """

    name: str
    drive_file_id: str
    displayed_size: str


_VOLUME_RAW: tuple[tuple[str, str, str], ...] = (
    ("CelebA_Spoof.zip.001", "1gd0M4qpxzqrnOkCl7hv7vnCWV4JJTFwM", "1,000M"),
    ("CelebA_Spoof.zip.002", "1OsOiow42GS4wbE7o1csPA2HtKLSgXT5_", "1,000M"),
    ("CelebA_Spoof.zip.003", "1_07Q7VA4-4R5fvHpkyoorhD5igeathko", "1,000M"),
    ("CelebA_Spoof.zip.004", "1Oy-5J10hsrZ2gyHH9U2oet0F92oaEqSq", "1,000M"),
    ("CelebA_Spoof.zip.005", "1NxlMSgvJSlDJMRFIfq_cT_RRybYS8eNW", "1,000M"),
    ("CelebA_Spoof.zip.006", "1mpMTb5ODq-9NV4IEVFwEDhUbYSNfVQtC", "1,000M"),
    ("CelebA_Spoof.zip.007", "14d1TYmcVXg1TlmuywM0HgOKcPqa71Rmq", "1,000M"),
    ("CelebA_Spoof.zip.008", "1st5Yh8yRQGAmI02iueWPm2rrJN1TpOlC", "1,000M"),
    ("CelebA_Spoof.zip.009", "1K-6UwtmUvrW7sZqaUvGYIkqpPC1G3K1V", "1,000M"),
    ("CelebA_Spoof.zip.010", "1wNgEJSBlZuQKePCTbwLM_9jBuIg3Hj1f", "1,000M"),
    ("CelebA_Spoof.zip.011", "18qd2y1fBPiqQqgSM-vrQq2rMbXeSHWLy", "1,000M"),
    ("CelebA_Spoof.zip.012", "1HgwT6-NLplcBkowdSHQz5VZEGEsFFDRd", "1,000M"),
    ("CelebA_Spoof.zip.013", "1-UYx3LoCloTNchmSq5otd4GxkWVTEGs_", "1,000M"),
    ("CelebA_Spoof.zip.014", "1MiHlWChmvOy53eTyiwWvd6hRV8zSeEYJ", "1,000M"),
    ("CelebA_Spoof.zip.015", "1WqikxT7XCMZLaPaYfOo0gYZOxeqAiFcP", "1,000M"),
    ("CelebA_Spoof.zip.016", "1iswrU0QuYSbzwKk0g0TWDD52hbtOps21", "1,000M"),
    ("CelebA_Spoof.zip.017", "1JPAB1jjLVdn8BBJk4hydDZq-IV5czrGq", "1,000M"),
    ("CelebA_Spoof.zip.018", "1Qpsou4EJJVd8aVyr9UKdtNvU_Rap3fAU", "1,000M"),
    ("CelebA_Spoof.zip.019", "1MOfdHWaU_ijqmDjLE34KG5AgmnBuTUnC", "1,000M"),
    ("CelebA_Spoof.zip.020", "1nKmKMvWV4kqeIPKQkoYnLPGB2QHFS7U1", "1,000M"),
    ("CelebA_Spoof.zip.021", "1Nkwv2phRRdbEA2Ief1Y9MCrd7UvZIs-G", "1,000M"),
    ("CelebA_Spoof.zip.022", "1W-IQReuw1Rc6PfTeLpeDxu-1v3n5tRcl", "1,000M"),
    ("CelebA_Spoof.zip.023", "1lU_RQN_HtB_8yYbRwkCzapfc5-4d0gW1", "1,000M"),
    ("CelebA_Spoof.zip.024", "1euzrQ4qxGLpOgmW1tIujvDUSdZFlsWmn", "1,000M"),
    ("CelebA_Spoof.zip.025", "1E6zkuosSUPAQBVGSWg5FlqnhhlACCeYS", "1,000M"),
    ("CelebA_Spoof.zip.026", "1jZerN3JzvTjxucNnQExqq61gDjxS0l5v", "1,000M"),
    ("CelebA_Spoof.zip.027", "1F-FI0JO8GLfA2QF5X8SSnjMpNeV5avZH", "1,000M"),
    ("CelebA_Spoof.zip.028", "1JTGaAL0d6QhwDoY1FRGq_IoexBXKCDAh", "1,000M"),
    ("CelebA_Spoof.zip.029", "1canVFU2jxJKs6VbcsvHPQeM1qEa8UVwY", "1,000M"),
    ("CelebA_Spoof.zip.030", "1wt9mOElhnkoYzlVPm5N_69SFhLSvy3YA", "1,000M"),
    ("CelebA_Spoof.zip.031", "1XwEjdvaBG_xFLVxauZK5MoeeFAnygkYI", "1,000M"),
    ("CelebA_Spoof.zip.032", "1FhekjS7l-0pDsymm_GM9aMJhh8VwcEah", "1,000M"),
    ("CelebA_Spoof.zip.033", "1mqXdA81AaAMM-MZvu6h0vCFh0gXWoHNU", "1,000M"),
    ("CelebA_Spoof.zip.034", "1BQtBSRoA0jFxt7zS9sZgJUFkZUQYj_rU", "1,000M"),
    ("CelebA_Spoof.zip.035", "1NO1vsdldaVj2pe93QdNfBZ3Ao6VWYvM7", "1,000M"),
    ("CelebA_Spoof.zip.036", "1xOq1PXanKDpUs1-JAcNaz6Hs5I8MFxxn", "1,000M"),
    ("CelebA_Spoof.zip.037", "1dihf4baq-_17g2tj1K3ya4Nf7xxMC96O", "1,000M"),
    ("CelebA_Spoof.zip.038", "1_pA7wv_nMgla0d3KH2cqN8JizL7vZyxP", "1,000M"),
    ("CelebA_Spoof.zip.039", "1z7c31kyQdrFxbpT6ZblIwAKRnJ9c2MTf", "1,000M"),
    ("CelebA_Spoof.zip.040", "1oftTxjUVLJdEOGADJzXjVNlUM6_BLlaO", "1,000M"),
    ("CelebA_Spoof.zip.041", "1jxuF9VFgRwD7ayd3c19cxPb7zLLFM1fp", "1,000M"),
    ("CelebA_Spoof.zip.042", "16gXdRiWd1tTiuRe5beaVYGXAUhX2m5f_", "1,000M"),
    ("CelebA_Spoof.zip.043", "1BTtMkRJO-DOhrZhR0kjenegN41mM5qbU", "1,000M"),
    ("CelebA_Spoof.zip.044", "1JsY9XCjW_Du5VZyPnkuh1Qdajs5aGopt", "1,000M"),
    ("CelebA_Spoof.zip.045", "11EdKR_DrmAmbvIXhPI6bj7FfMGNh0lAh", "1,000M"),
    ("CelebA_Spoof.zip.046", "1VX9YmcjCAWXYeQ3OjbEwO7cCPpn0UUzd", "1,000M"),
    ("CelebA_Spoof.zip.047", "18z-KimWHTh6-T05KzVlENogci5NF-PQH", "1,000M"),
    ("CelebA_Spoof.zip.048", "1EmVAkbAf3ZfGfVZrZpb7jHqsWqIy3wJa", "1,000M"),
    ("CelebA_Spoof.zip.049", "1fsS9it_vKV9bgntj8awTx-mRE1uhN9cA", "1,000M"),
    ("CelebA_Spoof.zip.050", "1lzd-nWagDEqldxkVFRK5-dwGqIf8XYp7", "1,000M"),
    ("CelebA_Spoof.zip.051", "1krpR7L20uRnOgNo1gx59pOhEcCa_pkyE", "1,000M"),
    ("CelebA_Spoof.zip.052", "1FZ4OGHJ_CWCf04oysgmCSONRTTYNsf5Y", "1,000M"),
    ("CelebA_Spoof.zip.053", "1Ac-DvMyCeUzRYsT1R_NrK1zcsQlRy_QL", "1,000M"),
    ("CelebA_Spoof.zip.054", "1ychf3AazgFb73Z1LIJ_lLhQwvYnOBCXd", "1,000M"),
    ("CelebA_Spoof.zip.055", "1s11ngviLIOiZcWjX_mkjEdQc7H_oY52-", "1,000M"),
    ("CelebA_Spoof.zip.056", "1X2Bg5acR0sVkrR4_h3BEMnm6PQFlwzVW", "1,000M"),
    ("CelebA_Spoof.zip.057", "1g9Ucb8m3l8rV5IpVG1Y2VTkNcZz8DImF", "1,000M"),
    ("CelebA_Spoof.zip.058", "15n2kpdRqu5rhyIYWIy50JleUHhEXezxt", "1,000M"),
    ("CelebA_Spoof.zip.059", "1j44juO753d5cp7xLA9ul5bTN8upjgrjY", "1,000M"),
    ("CelebA_Spoof.zip.060", "1VJoKI6vJJ5lb-JRazmjhDv_NsXzVpQTx", "1,000M"),
    ("CelebA_Spoof.zip.061", "1G16gR7eM45wAaPt8jVFdDt8Dx510QxNY", "1,000M"),
    ("CelebA_Spoof.zip.062", "1XZ5oYVAO8J8Zjp_dHb2-4YHWhobE9r2s", "1,000M"),
    ("CelebA_Spoof.zip.063", "1YI5f9Er6TGq3nlmut2zUfC-bumPtZUOg", "1,000M"),
    ("CelebA_Spoof.zip.064", "1FO7e7SBv50VOPaQJb_Kh9QfUHXwBrqXb", "1,000M"),
    ("CelebA_Spoof.zip.065", "1dJ3m7aygdJhcweTmPkZPUxFIYbAM6ysM", "1,000M"),
    ("CelebA_Spoof.zip.066", "1IjmswQCGQEtpdO3jr9TyJSNj5ikhOCDA", "1,000M"),
    ("CelebA_Spoof.zip.067", "1P7GD4fTK36dBvASLEVkeG01CUoDbX_Yl", "1,000M"),
    ("CelebA_Spoof.zip.068", "124cQ_o0MwY3jsieIEHqr2mfHpO3BuKrE", "1,000M"),
    ("CelebA_Spoof.zip.069", "1eoLXTSOr6MF53D9cElrkg7o5l7yI0xde", "1,000M"),
    ("CelebA_Spoof.zip.070", "1MZnG9Uzf5q86deEjev4REeOevKsN4eyy", "1,000M"),
    ("CelebA_Spoof.zip.071", "1U34bffAOUmBsR5YSF_B6Nz2k-97rMFTM", "1,000M"),
    ("CelebA_Spoof.zip.072", "1v7_ruZ2xvLCl9yQp9dEoPs94qe-rNDjL", "1,000M"),
    ("CelebA_Spoof.zip.073", "16VogXk2Onsva5i9wszhTL4Sigg-kFlQN", "1,000M"),
    ("CelebA_Spoof.zip.074", "1m9dVjwU-KajHbuUMVHgENg62fUdCZg1f", "432M"),
)

CELEBA_SPOOF_VOLUMES: tuple[CelebASpoofVolume, ...] = tuple(
    CelebASpoofVolume(name=name, drive_file_id=drive_file_id, displayed_size=displayed_size)
    for name, drive_file_id, displayed_size in _VOLUME_RAW
)
"""The 74 split-zip volumes, listed live via ``gdown --folder --json`` against
the real Google Drive folder in the 01-07 spike (no download involved in
producing this list). Recorded as data — not re-derived at call time — so a
future run can verify it got the volume set it expected before spending disk
on it, and so the spike's measurement is preserved even though acquisition
itself is deferred."""


# CelebA-Spoof's own README documents the per-image annotation JSON's Spoof
# Type field (index 40 of the 43-element vector) as:
#   0 Live, 1 Photo, 2 Poster, 3 A4, 4 Face Mask, 5 Upper Body Mask,
#   6 Region Mask, 7 PC, 8 Pad, 9 Phone, 10 3D Mask
# This project's class vocabulary (veriface_eval.datasets.manifest.SpoofClass)
# only has three slots: "live", "print", "screen_replay" — D-39 shelved
# video-replay out of v1, and there is no slot for the three mask-based
# attack types (Face/Upper-Body/Region/3D Mask) either. Both are therefore
# excluded from the label index entirely, exactly like video-replay: a
# spoof type this project's Literal cannot represent must not be smuggled
# into a class it doesn't belong to.
#
# CAVEAT: this mapping is inferred from the README's documented field
# layout only — no real annotation JSON was ever opened this session (the
# 01-07 spike's own download was blocked before it could confirm this
# against a real file, per docs/celeba-spoof-acquisition.md § 1). Re-verify
# against a handful of real annotation files as the first step of whichever
# phase actually runs this fetcher, before trusting this mapping at scale.
_SPOOF_TYPE_LABEL_INDEX = 40
_SPOOF_TYPE_TO_CLASS: dict[int, SpoofClass] = {
    0: "live",
    1: "print",  # Photo
    2: "print",  # Poster
    3: "print",  # A4
    7: "screen_replay",  # PC
    8: "screen_replay",  # Pad
    9: "screen_replay",  # Phone
}
_EXCLUDED_SPOOF_TYPES = frozenset({4, 5, 6, 10})  # Face/Upper-Body/Region/3D Mask — no class slot


def download_volumes(dest: Path, *, resume: bool = True) -> list[Path]:
    """Download every volume in ``CELEBA_SPOOF_VOLUMES`` into ``dest``, one at a time.

    Uses ``gdown`` (handles Google Drive's large-file confirmation-page
    token exchange; ``resume=True`` maps to gdown's own ``--continue``
    semantics so an interrupted run picks up rather than restarts). After
    each volume, its on-disk size is sanity-checked against
    ``CelebASpoofVolume.displayed_size`` — a volume dramatically short of
    that figure is treated as a failed download, not a smaller file (T-01-27).
    Checkpointed after each volume by construction: a later call with the
    same ``dest`` skips any volume already present at its expected size.

    Not exercised by this plan's tests — network downloads have no place in
    the unit suite (D-29), and this session's acquisition is deferred (see
    the module docstring). Implemented in full so Phase 2 can call it
    directly once headroom exists.
    """
    import gdown  # local import: gdown is an [eval]-extra-only dependency

    dest.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    for volume in CELEBA_SPOOF_VOLUMES:
        volume_path = dest / volume.name
        gdown.download(  # type: ignore[attr-defined]  # gdown re-exports without __all__
            id=volume.drive_file_id,
            output=str(volume_path),
            quiet=False,
            resume=resume,
        )
        if not volume_path.exists() or volume_path.stat().st_size == 0:
            raise VerifaceError(
                f"Download of {volume.name} produced no bytes at {volume_path} "
                f"(expected roughly {volume.displayed_size})"
            )
        downloaded.append(volume_path)
    return downloaded


def reassemble(volumes: Sequence[Path], dest: Path) -> Path:
    """Concatenate ``volumes`` in strict numeric order into ``dest``, then verify.

    Volumes are sorted by name before concatenation regardless of the order
    they were passed in — a split-zip's byte order is the archive's identity,
    and getting that wrong silently produces a corrupt file that looks
    superficially fine. Runs ``zipfile.ZipFile(dest).testzip()`` before
    returning; a non-``None`` result (or a ``BadZipFile``) raises rather than
    handing a caller an archive nothing has verified.
    """
    ordered = sorted(volumes, key=lambda p: p.name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as out:
        for volume_path in ordered:
            with volume_path.open("rb") as src:
                shutil.copyfileobj(src, out)

    try:
        with zipfile.ZipFile(dest) as archive:
            bad_member = archive.testzip()
    except zipfile.BadZipFile as exc:
        raise VerifaceError(
            f"Reassembled archive {dest} is not a valid zip after concatenating "
            f"{len(ordered)} volumes — see {ACQUISITION_DOC} for the documented "
            "fallback sequence (zip -FF, then py7zr/7z, then the Baidu Drive mirror)."
        ) from exc
    if bad_member is not None:
        raise VerifaceError(
            f"Reassembled archive {dest} failed CRC verification on member "
            f"{bad_member!r} — the concatenation or a source volume is corrupt."
        )
    return dest


def build_label_index(archive: zipfile.ZipFile) -> list[LabelIndexEntry]:
    """Read every per-image annotation JSON in ``archive`` and return label-index rows.

    Returns ``(subject_id, relative_path, spoof_class)`` tuples — the shape
    ``veriface_eval.datasets.manifest.build_manifest`` consumes. Images whose
    spoof-type label has no slot in this project's class vocabulary (masks,
    per the module-level caveat above) are silently excluded from the
    returned index — not an error, just not selectable into any manifest.

    Subject id is taken from the image path's parent-of-parent directory
    component, matching CelebA-Spoof's own ``Data/<train|test>/<subject_id>/
    <live|spoof>/...`` layout as described in the dataset's public
    documentation. This has not been verified against a real extracted
    archive this session (see the module docstring) — the first real
    invocation of this function should double-check the assumed path shape
    against a handful of real members before trusting the full index.

    Parses the member path with ``PurePosixPath`` (WR-07), not a bare
    ``pathlib.Path`` — zip member names are always POSIX-style regardless of
    host OS, matching every other archive-member path parse in this codebase
    (``sources.py``'s ``validate_member_path``, ``lfw.py``'s
    ``_extract_tar_safely``) rather than being the one host-platform-dependent
    exception.
    """
    entries: list[LabelIndexEntry] = []
    for member in archive.namelist():
        if not member.endswith(".json"):
            continue
        with archive.open(member) as fh:
            annotation: list[Any] = json.load(fh)
        if len(annotation) <= _SPOOF_TYPE_LABEL_INDEX:
            continue  # malformed/unexpected annotation shape — skip, don't guess
        spoof_type = int(annotation[_SPOOF_TYPE_LABEL_INDEX])
        if spoof_type in _EXCLUDED_SPOOF_TYPES:
            continue
        spoof_class = _SPOOF_TYPE_TO_CLASS.get(spoof_type)
        if spoof_class is None:
            continue  # unrecognised label value — exclude rather than misclassify

        image_member = member[: -len(".json")]
        parts = PurePosixPath(image_member).parts
        if len(parts) < 3:
            continue
        subject_id = parts[-3]
        entries.append((subject_id, image_member, spoof_class))
    return entries


def extract_subset(archive: zipfile.ZipFile, rows: Iterable[ManifestRow], dest: Path) -> list[Path]:
    """Extract exactly ``rows``' archive members into ``dest`` — no more, no fewer.

    Reuses ``veriface.models.sources.validate_member_path`` for the same
    POSIX/Windows path-traversal guard the model-archive extraction path
    uses (T-01-03), rather than a second implementation. Each destination is
    resolved and required to have ``dest`` as a parent before anything is
    written; a member that is absolute, contains a parent-directory
    component, or normalizes outside ``dest`` raises with nothing written
    outside ``dest``. Never calls ``ZipFile.extractall``.
    """
    dest.mkdir(parents=True, exist_ok=True)
    resolved_root = dest.resolve()
    extracted: list[Path] = []
    for row in rows:
        member = row.relative_path
        validate_member_path(member)
        dest_path = (dest / member).resolve()
        try:
            dest_path.relative_to(resolved_root)
        except ValueError as exc:
            raise ArtifactSourceError(
                f"Archive member {member!r} resolves outside the extraction root"
            ) from exc
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as src, dest_path.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        extracted.append(dest_path)
    return extracted


def cleanup(raw_dir: Path, archive: Path) -> int:
    """Delete every volume under ``raw_dir`` plus ``archive``; return reclaimed bytes.

    Retains raw subset images extracted elsewhere (D-22 — derived crops are
    never persisted, but the raw images themselves are kept); this function
    only ever deletes the large intermediate download artifacts, never the
    extracted subset.
    """
    reclaimed = 0
    if archive.exists():
        reclaimed += archive.stat().st_size
        archive.unlink()
    if raw_dir.exists():
        for volume in raw_dir.glob("CelebA_Spoof.zip.*"):
            reclaimed += volume.stat().st_size
            volume.unlink()
    return reclaimed


def fetch_celeba_spoof(data_dir: Path, tier: str) -> Path:
    """Materialize the CelebA-Spoof ``tier`` subset under ``data_dir`` — DEFERRED.

    Checks whether the reassembled archive is already present under
    ``data_dir / RAW_SUBDIR`` before doing anything else. If it is not (the
    case for every invocation today, per the Task 3 deferral decision), raises
    ``AcquisitionDeferredError`` immediately — no network call is attempted,
    no partial state is written. If a human has manually placed a reassembled
    archive there (the documented fallback if the tool-permission blocker in
    ``docs/celeba-spoof-acquisition.md`` is later worked around manually),
    this function proceeds: build the label index, build and write the
    manifest, extract the subset, clean up.

    Deliberately does **not** call ``download_volumes``/``reassemble`` itself
    in the deferred case — those remain available as direct entry points for
    Phase 2 once the developer decides to lift the deferral.

    Validates ``tier`` against ``dataset_config.TIERS`` before anything else
    (WR-05): the caller-facing CLI only validates ``dataset``, not ``tier``,
    so an unknown tier name reaching this function must raise a named
    ``VerifaceError`` (``TierNotFoundError``) rather than the bare
    ``KeyError`` a direct ``TIERS[tier]`` lookup would raise once a human has
    placed a reassembled archive under ``raw_dir`` — a ``KeyError`` is not a
    ``VerifaceError`` and would fall straight through the CLI's
    ``except VerifaceError`` handler as an unhandled traceback.
    """
    from veriface_eval.datasets import config as dataset_config

    if tier not in dataset_config.TIERS:
        raise dataset_config.TierNotFoundError(tier)

    raw_dir = data_dir / RAW_SUBDIR
    reassembled_path = raw_dir / _REASSEMBLED_NAME
    if not reassembled_path.exists():
        raise AcquisitionDeferredError(tier, raw_dir)

    # Reachable only once a human has placed a valid reassembled archive —
    # not exercised by this plan (no bytes were available to test it against).
    from veriface_eval.datasets.manifest import build_manifest, write_manifest

    tier_spec = dataset_config.TIERS[tier]
    with zipfile.ZipFile(reassembled_path) as archive:
        label_index = build_label_index(archive)
        header, rows = build_manifest(
            label_index,
            tier=tier,
            seed=0,
            params={
                "target_subjects": tier_spec.target_subjects,
                "splits": {"train": 0.8, "test": 0.2},
            },
        )
        manifest_path = dataset_config.manifest_path_for(tier)
        write_manifest(rows, header, manifest_path)
        extract_dest = data_dir / "celeba_spoof" / tier
        extract_subset(archive, rows, extract_dest)

    reclaimed = cleanup(raw_dir, reassembled_path)
    del reclaimed  # reported by the CLI caller, not this function's return value
    return extract_dest


__all__ = [
    "ACQUISITION_DOC",
    "CELEBA_SPOOF_VOLUMES",
    "GOOGLE_DRIVE_FOLDER_ID",
    "RAW_SUBDIR",
    "AcquisitionDeferredError",
    "CelebASpoofVolume",
    "build_label_index",
    "cleanup",
    "download_volumes",
    "extract_subset",
    "fetch_celeba_spoof",
    "reassemble",
]
