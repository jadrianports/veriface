"""The network-access-confinement invariant (WR-01).

``models/registry.py``'s module docstring states that ``ModelRegistry``
(with ``runtime.py``) is the only code path permitted to reach the network —
concretely, the only module allowed to import ``resolve_source`` from
``veriface.models.sources`` and call ``.materialize(...)`` on the result.
Before WR-01's fix, ``veriface/cli/models.py`` imported ``resolve_source``
directly and duplicated ``ModelRegistry.fetch()``'s body, which this AST walk
would have caught. Uses ``ast.parse`` rather than a text scan so a mention in
a docstring or comment cannot flip the result either way.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
ALLOWED_FILES = {"veriface/models/registry.py"}


def _imports_resolve_source(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "veriface.models.sources" and any(
                alias.name == "resolve_source" for alias in node.names
            ):
                return True
    return False


def _files_importing_resolve_source() -> set[str]:
    offenders: set[str] = set()
    for path in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _imports_resolve_source(tree):
            offenders.add(path.relative_to(SRC_ROOT).as_posix())
    return offenders


def test_only_registry_imports_resolve_source() -> None:
    """``sources.py`` defines ``resolve_source`` but never imports it from itself
    via ``ImportFrom`` — only ``registry.py`` is expected to import it."""
    offenders = _files_importing_resolve_source()
    assert offenders == ALLOWED_FILES, (
        f"Only ModelRegistry (veriface/models/registry.py) may import "
        f"resolve_source — found: {offenders}"
    )
