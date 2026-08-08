"""Real-network proof of ``fetch_lfw`` (marked ``integration``).

Two cases: the digest check runs before extraction (a corrupted download is
never extracted), and a real, full fetch materializes the expected identity
structure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from veriface.errors import ArtifactIntegrityError
from veriface_eval.datasets import lfw

pytestmark = pytest.mark.integration


def test_corrupted_download_is_never_extracted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A monkeypatched download hook writes corrupt bytes; nothing gets extracted."""

    def _fake_download(_url: str, dest_path: Path) -> None:
        dest_path.write_bytes(b"not a real archive")

    monkeypatch.setattr(lfw, "_download", _fake_download)

    with pytest.raises(ArtifactIntegrityError):
        lfw.fetch_lfw(tmp_path, allow_download=True)

    dest_dir = tmp_path / lfw.LFW_SPEC.extraction_subdir
    # The digest check ran and failed before extraction: no identity
    # subdirectory exists, the marker was never written, and the corrupted
    # archive itself was deleted rather than left behind.
    assert not (dest_dir / ".materialized").exists()
    remaining = list(dest_dir.iterdir()) if dest_dir.exists() else []
    assert remaining == [], f"extraction ran despite a failed digest check: {remaining}"


def test_real_fetch_materializes_expected_identity_structure(tmp_path: Path) -> None:
    """A real, full fetch (real network, ~250 MB) extracts >1000 identity directories."""
    dest_dir = lfw.fetch_lfw(tmp_path, allow_download=True)

    assert dest_dir == tmp_path / "lfw"
    identity_dirs = [p for p in dest_dir.iterdir() if p.is_dir()]
    assert len(identity_dirs) > 1000, (
        f"expected >1000 identity directories, found {len(identity_dirs)}"
    )

    # No archive container remains under the data dir after a successful fetch.
    leftover_archives = list(dest_dir.glob("*.tgz*")) + list(tmp_path.rglob("*.tar.gz"))
    assert leftover_archives == [], f"archive left behind: {leftover_archives}"

    # pairs.txt shipped inside the archive itself (see lfw.py's module
    # docstring) — no second LFW_SPEC entry was needed.
    assert (dest_dir / "pairs.txt").is_file()

    # Idempotent: a second call with the marker present returns immediately
    # without touching the network again.
    dest_dir_again = lfw.fetch_lfw(tmp_path, allow_download=False)
    assert dest_dir_again == dest_dir
