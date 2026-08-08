"""T-01-03 — archive-extraction traversal defence.

``extract_member_safely`` must extract exactly the declared member and
reject any member name that is absolute, contains a parent-directory
component, or resolves outside the extraction root — checked against both
POSIX and Windows path semantics regardless of the host OS (D-28-style
platform-independent coverage), since CI runs on ``ubuntu-latest`` only but
this project develops on Windows.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from veriface.errors import ArtifactSourceError
from veriface.models.sources import extract_member_safely


def _make_zip(zip_path: Path, member_name: str, content: bytes = b"payload") -> None:
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(member_name, content)


def test_benign_member_extracts_inside_root(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    _make_zip(zip_path, "det_10g.onnx", b"real-bytes")
    extract_root = tmp_path / "extract"

    dest = extract_member_safely(zip_path, "det_10g.onnx", extract_root)

    assert dest == (extract_root / "det_10g.onnx").resolve()
    assert dest.read_bytes() == b"real-bytes"
    assert dest.is_relative_to(extract_root.resolve())


def test_member_with_parent_directory_component_raises(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    _make_zip(zip_path, "../evil.onnx")
    extract_root = tmp_path / "extract"
    sibling_before = set((tmp_path.parent).iterdir()) if tmp_path.parent.exists() else set()

    with pytest.raises(ArtifactSourceError):
        extract_member_safely(zip_path, "../evil.onnx", extract_root)

    assert not (tmp_path.parent / "evil.onnx").exists()
    if tmp_path.parent.exists():
        assert set(tmp_path.parent.iterdir()) == sibling_before


def test_absolute_member_path_raises(tmp_path: Path) -> None:
    zip_path = tmp_path / "archive.zip"
    absolute_member = "/etc/evil.onnx"
    _make_zip(zip_path, absolute_member)
    extract_root = tmp_path / "extract"

    with pytest.raises(ArtifactSourceError):
        extract_member_safely(zip_path, absolute_member, extract_root)

    assert not Path("/etc/evil.onnx").exists()
    assert not extract_root.exists() or list(extract_root.iterdir()) == []


def test_windows_backslash_traversal_raises_even_off_windows(tmp_path: Path) -> None:
    """A member name using backslash-based parent traversal must be rejected
    even when this test runs on a POSIX host, where a bare ``pathlib.Path``
    would not treat ``\\`` as a separator at all — this is exactly the
    platform-independent check T-01-03 requires.
    """
    zip_path = tmp_path / "archive.zip"
    hostile_member = "..\\..\\evil.onnx"
    _make_zip(zip_path, hostile_member)
    extract_root = tmp_path / "extract"

    with pytest.raises(ArtifactSourceError):
        extract_member_safely(zip_path, hostile_member, extract_root)

    assert not extract_root.exists() or list(extract_root.iterdir()) == []


def test_hostile_cases_write_nothing_outside_tmp_path(tmp_path: Path) -> None:
    """Combined regression: none of the three hostile cases leave any file
    outside ``tmp_path`` on disk, regardless of the specific ValueError/OSError
    path taken internally.
    """
    zip_path = tmp_path / "archive.zip"
    extract_root = tmp_path / "extract"
    hostile_members = ["../evil.onnx", "/etc/evil.onnx", "..\\..\\evil.onnx"]

    for member in hostile_members:
        _make_zip(zip_path, member)
        with pytest.raises(ArtifactSourceError):
            extract_member_safely(zip_path, member, extract_root)

    # The only files that may exist are the zip itself and (possibly) an
    # empty extract_root directory created before validation ran out.
    for path in tmp_path.rglob("*"):
        assert path in (zip_path, extract_root) or path.is_relative_to(extract_root)
