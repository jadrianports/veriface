"""``sha256_bytes`` (WR-08) — the in-memory counterpart to ``sha256_file``,
used where a caller has already read a file into memory and must not
re-open it by name a second time just to hash it."""

from __future__ import annotations

import hashlib
from pathlib import Path

from veriface.hashing import sha256_bytes, sha256_file

_PAYLOAD = b"veriface-hashing-fixture-payload" * 32


def test_sha256_bytes_matches_sha256_file_for_the_same_content(tmp_path: Path) -> None:
    path = tmp_path / "payload.bin"
    path.write_bytes(_PAYLOAD)

    assert sha256_bytes(_PAYLOAD) == sha256_file(path)


def test_sha256_bytes_is_deterministic() -> None:
    assert sha256_bytes(_PAYLOAD) == sha256_bytes(_PAYLOAD)


def test_sha256_bytes_differs_for_different_content() -> None:
    assert sha256_bytes(_PAYLOAD) != sha256_bytes(_PAYLOAD + b"x")


def test_sha256_bytes_of_empty_bytes_matches_hashlib_directly() -> None:
    assert sha256_bytes(b"") == hashlib.sha256(b"").hexdigest()
