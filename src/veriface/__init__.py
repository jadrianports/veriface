"""veriface — open-set face recognition + presentation-attack detection.

Importing this package never touches the network or the filesystem beyond
ordinary Python module loading (D-12) — no model is downloaded, no session
is constructed, and no cache directory is created at import time.
"""

from __future__ import annotations

__all__: list[str] = []

__version__ = "0.1.0"
