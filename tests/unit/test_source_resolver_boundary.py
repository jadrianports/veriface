"""The source-resolver-boundary invariant (assumption-delta decision, 01-01-PLAN.md).

``src/veriface/models/sources.py`` is the ONLY module under ``src/``
permitted to branch on a spec's ``source`` attribute. This walks the AST of
every module under ``src/`` — not a text scan — so prose in a docstring or a
string literal cannot flip the result either way.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src"
ALLOWED_FILES = {"veriface/models/sources.py"}


class _SourceBranchVisitor(ast.NodeVisitor):
    """Detects any ``Compare`` or ``match`` construct that reads ``.source``
    off an attribute access — the shape a branch on ``spec.source`` takes.
    """

    def __init__(self) -> None:
        self.found = False

    def visit_Compare(self, node: ast.Compare) -> None:
        for operand in (node.left, *node.comparators):
            if isinstance(operand, ast.Attribute) and operand.attr == "source":
                self.found = True
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        if isinstance(node.subject, ast.Attribute) and node.subject.attr == "source":
            self.found = True
        self.generic_visit(node)


def _files_branching_on_source() -> set[str]:
    offenders: set[str] = set()
    for path in sorted(SRC_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _SourceBranchVisitor()
        visitor.visit(tree)
        if visitor.found:
            offenders.add(path.relative_to(SRC_ROOT).as_posix())
    return offenders


def test_only_sources_py_branches_on_spec_source() -> None:
    offenders = _files_branching_on_source()
    assert offenders == ALLOWED_FILES, (
        f"Only {ALLOWED_FILES} may branch on spec.source; found: {offenders}"
    )
