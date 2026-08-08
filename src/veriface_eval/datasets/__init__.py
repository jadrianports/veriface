"""Dataset fetching, subset manifests, and tier configuration for veriface_eval.

Nothing in this package is imported by ``veriface`` or ``veriface_server``
(D-03) — it is reached only through ``veriface_eval.cli``, itself mounted
behind the guarded ``_try_mount`` seam in ``veriface.cli``.
"""

from __future__ import annotations

__all__: list[str] = []
