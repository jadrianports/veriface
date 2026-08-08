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

    def run(
        self, output_names: list[str] | None, input_feed: dict[str, Any]
    ) -> list[Any]: ...

    def get_providers(self) -> list[str]: ...


def _half_logical_cores() -> int:
    total = os.cpu_count() or 2
    return max(1, total // 2)


def open_session(path: Path) -> Session:
    """Construct a CPU-only ``InferenceSession`` over ``path``.

    Raises ``VerifaceError`` if the realised provider list is not exactly
    ``["CPUExecutionProvider"]`` — the silent-fallback trap RESEARCH names.
    """
    options = ort.SessionOptions()
    options.intra_op_num_threads = _half_logical_cores()

    session = ort.InferenceSession(
        str(path),
        sess_options=options,
        providers=[_CPU_PROVIDER],
    )

    providers = session.get_providers()
    if providers != [_CPU_PROVIDER]:
        raise VerifaceError(
            f"Expected CPU-only execution provider for {path}, but ONNX Runtime "
            f"realised providers={providers!r}. Refusing a silent non-CPU fallback."
        )

    return cast(Session, session)
