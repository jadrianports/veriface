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
