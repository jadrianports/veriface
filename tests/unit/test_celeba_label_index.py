"""WR-07 — ``build_label_index`` must parse zip member paths with POSIX
semantics regardless of host OS, matching every other archive-member path
parse in this codebase (``sources.py``'s ``validate_member_path``,
``lfw.py``'s ``_extract_tar_safely``). Zip member names are always
POSIX-style; a bare ``pathlib.Path`` is host-platform-dependent and was the
one inconsistent exception before this fix.

A direct "literal backslash in a member name" regression test is not
constructible against the real ``zipfile.ZipFile.namelist()`` API on a
Windows host: CPython's own ``zipfile.ZipInfo`` normalizes any raw
``os.sep`` character in a filename to ``"/"`` when the central directory is
*read* (confirmed empirically — a member written with an embedded
backslash round-trips as forward-slash-only through ``namelist()`` on this
platform), so ``build_label_index`` never actually observes a backslash from
a real archive here regardless of which ``Path`` class parses it. The
correctness coverage below (subject-id extraction, spoof-type mapping,
exclusion) is what's testable; the ``PurePosixPath`` swap itself is a
consistency fix — verified by direct code inspection, not by a platform-
divergence reproduction that CPython's own zipfile module forecloses.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from veriface_eval.datasets.celeba_spoof import build_label_index

_SPOOF_TYPE_LABEL_INDEX = 40


def _annotation(spoof_type: int) -> list[int]:
    """A 41-element annotation vector with only the Spoof Type field set."""
    vector = [0] * (_SPOOF_TYPE_LABEL_INDEX + 1)
    vector[_SPOOF_TYPE_LABEL_INDEX] = spoof_type
    return vector


def _make_zip(zip_path: Path, members: dict[str, list[int]]) -> None:
    with zipfile.ZipFile(zip_path, "w") as archive:
        for name, annotation in members.items():
            archive.writestr(name, json.dumps(annotation))


def test_normal_member_extracts_subject_id_from_parent_of_parent(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    _make_zip(zip_path, {"Data/train/s001/live/0001.jpg.json": _annotation(0)})

    with zipfile.ZipFile(zip_path) as archive:
        entries = build_label_index(archive)

    assert entries == [("s001", "Data/train/s001/live/0001.jpg", "live")]


def test_photo_and_poster_and_a4_map_to_print(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    _make_zip(
        zip_path,
        {
            "Data/train/s001/spoof/0001.jpg.json": _annotation(1),  # Photo
            "Data/train/s001/spoof/0002.jpg.json": _annotation(2),  # Poster
            "Data/train/s001/spoof/0003.jpg.json": _annotation(3),  # A4
        },
    )

    with zipfile.ZipFile(zip_path) as archive:
        entries = build_label_index(archive)

    assert {spoof_class for _subject, _path, spoof_class in entries} == {"print"}
    assert len(entries) == 3


def test_pc_pad_phone_map_to_screen_replay(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    _make_zip(
        zip_path,
        {
            "Data/train/s001/spoof/0001.jpg.json": _annotation(7),  # PC
            "Data/train/s001/spoof/0002.jpg.json": _annotation(8),  # Pad
            "Data/train/s001/spoof/0003.jpg.json": _annotation(9),  # Phone
        },
    )

    with zipfile.ZipFile(zip_path) as archive:
        entries = build_label_index(archive)

    assert {spoof_class for _subject, _path, spoof_class in entries} == {"screen_replay"}
    assert len(entries) == 3


def test_mask_and_unrecognised_spoof_types_are_excluded(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    _make_zip(
        zip_path,
        {
            "Data/train/s001/spoof/0001.jpg.json": _annotation(4),  # Face Mask
            "Data/train/s001/spoof/0002.jpg.json": _annotation(5),  # Upper Body Mask
            "Data/train/s001/spoof/0003.jpg.json": _annotation(6),  # Region Mask
            "Data/train/s001/spoof/0004.jpg.json": _annotation(10),  # 3D Mask
            "Data/train/s001/live/0005.jpg.json": _annotation(0),  # Live — kept
        },
    )

    with zipfile.ZipFile(zip_path) as archive:
        entries = build_label_index(archive)

    assert entries == [("s001", "Data/train/s001/live/0005.jpg", "live")]


def test_non_json_members_are_ignored(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("Data/train/s001/live/0001.jpg", b"not-json-image-bytes")

    with zipfile.ZipFile(zip_path) as archive:
        entries = build_label_index(archive)

    assert entries == []
