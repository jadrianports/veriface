"""T-01-03 — CelebA-Spoof dataset extraction traversal defence.

``extract_subset`` must extract exactly the manifest rows' archive members
and reject any member name that is absolute, contains a parent-directory
component, or resolves outside the extraction root — mirroring
``tests/unit/test_archive_member_safety.py``'s coverage of the model-archive
extraction path, since both paths share the same
``veriface.models.sources.validate_member_path`` guard (reused, not
reimplemented). No CelebA-Spoof bytes are needed for any of this — every
archive here is synthetic, built in-test.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from veriface.errors import ArtifactSourceError, VerifaceError
from veriface_eval.datasets.celeba_spoof import (
    AcquisitionDeferredError,
    extract_subset,
    fetch_celeba_spoof,
)
from veriface_eval.datasets.config import TierNotFoundError
from veriface_eval.datasets.manifest import ManifestRow


def _row(relative_path: str, *, subject_id: str = "s001") -> ManifestRow:
    return ManifestRow(
        subject_id=subject_id, relative_path=relative_path, spoof_class="live", split="test"
    )


def _make_zip(zip_path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(zip_path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def test_benign_row_extracts_inside_root(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    _make_zip(zip_path, {"Data/train/s001/live/0001.jpg": b"real-bytes"})
    extract_root = tmp_path / "extract"

    with zipfile.ZipFile(zip_path) as archive:
        extracted = extract_subset(archive, [_row("Data/train/s001/live/0001.jpg")], extract_root)

    assert len(extracted) == 1
    dest = extracted[0]
    assert dest == (extract_root / "Data/train/s001/live/0001.jpg").resolve()
    assert dest.read_bytes() == b"real-bytes"
    assert dest.is_relative_to(extract_root.resolve())


def test_parent_directory_component_raises_and_writes_nothing(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    hostile_member = "../evil.jpg"
    _make_zip(zip_path, {hostile_member: b"x"})
    extract_root = tmp_path / "extract"
    sibling_before = set(tmp_path.parent.iterdir()) if tmp_path.parent.exists() else set()

    with zipfile.ZipFile(zip_path) as archive, pytest.raises(ArtifactSourceError):
        extract_subset(archive, [_row(hostile_member)], extract_root)

    assert not (tmp_path.parent / "evil.jpg").exists()
    if tmp_path.parent.exists():
        assert set(tmp_path.parent.iterdir()) == sibling_before


def test_absolute_member_path_raises_and_writes_nothing(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    absolute_member = "/etc/evil.jpg"
    _make_zip(zip_path, {absolute_member: b"x"})
    extract_root = tmp_path / "extract"

    with zipfile.ZipFile(zip_path) as archive, pytest.raises(ArtifactSourceError):
        extract_subset(archive, [_row(absolute_member)], extract_root)

    assert not Path("/etc/evil.jpg").exists()
    assert not extract_root.exists() or list(extract_root.iterdir()) == []


def test_windows_backslash_traversal_raises_even_off_windows(tmp_path: Path) -> None:
    """Rejected even on a POSIX host, where a bare ``pathlib.Path`` would not
    treat ``\\`` as a separator at all — this is exactly what
    ``validate_member_path``'s dual POSIX/Windows check exists for."""
    zip_path = tmp_path / "archive.zip"
    hostile_member = "..\\..\\evil.jpg"
    _make_zip(zip_path, {hostile_member: b"x"})
    extract_root = tmp_path / "extract"

    with zipfile.ZipFile(zip_path) as archive, pytest.raises(ArtifactSourceError):
        extract_subset(archive, [_row(hostile_member)], extract_root)

    assert not extract_root.exists() or list(extract_root.iterdir()) == []


def test_extracts_exactly_manifest_rows_and_no_other_entry(tmp_path: Path) -> None:
    """Given an archive with extra members beyond what the manifest names,
    only the manifest-listed rows are written — never ``ZipFile.extractall``'s
    everything-in-the-archive behaviour."""
    zip_path = tmp_path / "archive.zip"
    _make_zip(
        zip_path,
        {
            "Data/train/s001/live/0001.jpg": b"a",
            "Data/train/s001/live/0002.jpg": b"b",
            "Data/train/s002/spoof/0001.jpg": b"c",  # not in the manifest rows below
            "Data/train/s002/spoof/0001.json": b"{}",  # not in the manifest rows below
        },
    )
    extract_root = tmp_path / "extract"
    rows = [
        _row("Data/train/s001/live/0001.jpg", subject_id="s001"),
        _row("Data/train/s001/live/0002.jpg", subject_id="s001"),
    ]

    with zipfile.ZipFile(zip_path) as archive:
        extracted = extract_subset(archive, rows, extract_root)

    assert len(extracted) == 2
    on_disk = sorted(p for p in extract_root.rglob("*") if p.is_file())
    assert on_disk == sorted(extracted)
    assert not (extract_root / "Data/train/s002").exists()


def test_hostile_cases_write_nothing_outside_tmp_path(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    extract_root = tmp_path / "extract"
    hostile_members = ["../evil.jpg", "/etc/evil.jpg", "..\\..\\evil.jpg"]

    for member in hostile_members:
        _make_zip(zip_path, {member: b"x"})
        with zipfile.ZipFile(zip_path) as archive, pytest.raises(ArtifactSourceError):
            extract_subset(archive, [_row(member)], extract_root)

    for path in tmp_path.rglob("*"):
        assert path in (zip_path, extract_root) or path.is_relative_to(extract_root)


def test_fetch_raises_acquisition_deferred_when_corpus_absent(tmp_path: Path) -> None:
    """The honest-degradation path (coordinator decision, 2026-08-08): no
    silent skip, no fake success — a clear, actionable error naming the
    deferral and pointing at the acquisition doc."""
    with pytest.raises(AcquisitionDeferredError) as exc_info:
        fetch_celeba_spoof(tmp_path, "eval")

    message = str(exc_info.value)
    assert "deferred" in message
    assert "docs/celeba-spoof-acquisition.md" in message
    assert not (tmp_path / "celeba_spoof").exists()


def test_fetch_raises_named_error_for_unknown_tier_not_a_bare_keyerror(tmp_path: Path) -> None:
    """WR-05: an unknown tier must raise TierNotFoundError (a VerifaceError,
    caught cleanly by the CLI's ``except VerifaceError`` handler) rather than
    a bare ``KeyError`` from a direct ``TIERS[tier]`` lookup. Checked before
    the corpus-presence check, so this holds regardless of whether a human
    has placed a reassembled archive under ``raw_dir`` — the exact scenario
    where an unvalidated ``tier`` would otherwise first become reachable.
    """
    with pytest.raises(TierNotFoundError) as exc_info:
        fetch_celeba_spoof(tmp_path, "not-a-real-tier")

    assert isinstance(exc_info.value, VerifaceError)
    assert "not-a-real-tier" in str(exc_info.value)
