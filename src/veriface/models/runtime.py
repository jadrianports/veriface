"""The sole onnxruntime seam (D-17).

This is the only module under ``src/`` that imports ``onnxruntime`` — every
other module receives a typed ``Session`` and never touches the C-extension
API directly. The corresponding ``[[tool.mypy.overrides]]`` in
``pyproject.toml`` scopes its ``ignore_missing_imports`` to ``onnxruntime.*``
and nothing else.

``open_session`` caps ``intra_op_num_threads`` at half the machine's logical
cores (PROJECT.md thermal constraint; RESEARCH Pitfall — thread
oversubscription) and asserts the realised provider list is CPU-only,
guarding against ONNX Runtime's silent-CPU-fallback trap: passing a
preferred provider list is not honored if that provider is unavailable, and
no exception is raised (RESEARCH PITFALLS § Integration Gotchas).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Protocol, cast

import onnxruntime as ort

from veriface.errors import VerifaceError

_CPU_PROVIDER = "CPUExecutionProvider"


class Session(Protocol):
    """A narrow, fully typed view over ``onnxruntime.InferenceSession``."""

    def run(self, output_names: list[str] | None, input_feed: dict[str, Any]) -> list[Any]: ...

    def get_providers(self) -> list[str]: ...


def _half_logical_cores() -> int:
    total = os.cpu_count() or 2
    return max(1, total // 2)


def open_session(model_bytes: bytes, *, source_label: Path | str) -> Session:
    """Construct a CPU-only ``InferenceSession`` over an already-read model buffer.

    Takes ``bytes`` rather than a path (WR-08): the caller reads the cached
    file exactly once, verifies that buffer's digest, and passes the same
    buffer here — closing the TOCTOU window a path-based
    ``ort.InferenceSession(str(path), ...)`` call would leave between digest
    verification and session construction (two separate by-name opens of the
    same path, either of which a writer with cache-directory access could
    race). ``source_label`` is used only to name the artifact in the
    CPU-fallback error message below.

    Raises ``VerifaceError`` if the realised provider list is not exactly
    ``["CPUExecutionProvider"]`` — the silent-fallback trap RESEARCH names.
    """
    options = ort.SessionOptions()
    options.intra_op_num_threads = _half_logical_cores()

    session = ort.InferenceSession(
        model_bytes,
        sess_options=options,
        providers=[_CPU_PROVIDER],
    )

    providers = session.get_providers()
    if providers != [_CPU_PROVIDER]:
        raise VerifaceError(
            f"Expected CPU-only execution provider for {source_label}, but ONNX Runtime "
            f"realised providers={providers!r}. Refusing a silent non-CPU fallback."
        )

    return cast(Session, session)
