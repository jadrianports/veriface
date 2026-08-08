"""D-17: onnxruntime is confined to exactly one module under ``src/``.

Uses an AST walk rather than a text scan, so a mention in a docstring or
comment cannot make the assertion lie in either direction.
"""

from __future__ import annotations

import ast
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


def _imports_onnxruntime(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name.split(".")[0] == "onnxruntime" for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root == "onnxruntime":
                return True
    return False


def test_exactly_one_module_imports_onnxruntime() -> None:
    importing_modules: set[str] = set()
    for py_file in _SRC_ROOT.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        if _imports_onnxruntime(tree):
            importing_modules.add(py_file.relative_to(_SRC_ROOT.parent).as_posix())

    assert importing_modules == {"src/veriface/models/runtime.py"}
