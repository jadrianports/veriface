"""Streaming SHA-256 hashing.

This module lives in core (not under ``models/``) because ``veriface_eval``
also needs it — for dataset archive/manifest verification (D-25) — and must
not import anything from ``models/``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Stream ``path`` and return its lowercase hex SHA-256 digest.

    No memoisation, no size/mtime shortcut, no environment-variable escape
    (D-09) — every call re-reads and re-hashes the full file.
    """
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Return ``data``'s lowercase hex SHA-256 digest.

    For a caller that has already read a file fully into memory (WR-08:
    ``ModelRegistry.load`` verifies and loads the same in-memory buffer
    rather than opening the cached path by name twice, closing the TOCTOU
    window between digest verification and session construction) and would
    otherwise re-open the same path a second time just to hash it again.
    """
    return hashlib.sha256(data).hexdigest()
