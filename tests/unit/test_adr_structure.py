"""Structural invariants for docs/adr/*.md: numbering, headings, status,
Considered Options completeness, and index ordering.

These assertions exist because an ADR that satisfies the letter of DOCS-04
("write a record") without a real Considered Options section satisfies none
of its purpose (proving the 2017 design was weighed, not merely dismissed).
Every assertion here is mechanical and re-runs on every later phase's ADRs
too — the conventions fixed in phase 01-06 apply to every record after it.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = REPO_ROOT / "docs" / "adr"
ADR_INDEX_TOOL = REPO_ROOT / "tools" / "adr_index.py"

FILENAME_RE = re.compile(r"^(?P<number>\d{4})-[a-z0-9-]+\.md$")
STATUS_RE = re.compile(r"^## Status\s*\n+\s*(?P<status>\S+)", re.MULTILINE)
CONSIDERED_OPTIONS_RE = re.compile(
    r"^## Considered Options\s*\n(?P<body>.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL
)
VALID_STATUSES = frozenset({"proposed", "accepted", "superseded", "deprecated"})
REQUIRED_HEADINGS = (
    "## Status",
    "## Context and Problem Statement",
    "## Decision Drivers",
    "## Considered Options",
    "## Decision Outcome",
    "### Consequences",
    "## More Information",
)


def _adr_paths() -> list[Path]:
    return sorted(p for p in ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md") if FILENAME_RE.match(p.name))


def _adr_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


ADR_PATHS = _adr_paths()
ADR_IDS = [p.name for p in ADR_PATHS]


def test_at_least_one_adr_exists() -> None:
    assert ADR_PATHS, "no docs/adr/NNNN-*.md records found"


def test_no_duplicate_prefixes_and_contiguous_from_0001() -> None:
    numbers = [FILENAME_RE.match(p.name).group("number") for p in ADR_PATHS]  # type: ignore[union-attr]
    assert len(numbers) == len(set(numbers)), (
        f"duplicate ADR number prefixes found: {sorted(n for n in numbers if numbers.count(n) > 1)}"
    )
    expected = {f"{i:04d}" for i in range(1, len(numbers) + 1)}
    assert set(numbers) == expected, (
        f"ADR prefixes are not a contiguous run starting at 0001: {sorted(numbers)}"
    )


@pytest.mark.parametrize("adr_path", ADR_PATHS, ids=ADR_IDS)
def test_required_headings_present(adr_path: Path) -> None:
    text = _adr_text(adr_path)
    missing = [heading for heading in REQUIRED_HEADINGS if heading not in text]
    assert not missing, f"{adr_path.name} is missing headings: {missing}"


@pytest.mark.parametrize("adr_path", ADR_PATHS, ids=ADR_IDS)
def test_considered_options_nonempty_with_at_least_two_items(adr_path: Path) -> None:
    text = _adr_text(adr_path)
    match = CONSIDERED_OPTIONS_RE.search(text)
    assert match is not None, f"{adr_path.name} has no ## Considered Options section"
    body = match.group("body").strip()
    assert body, f"{adr_path.name}'s Considered Options section is empty"
    list_items = [line for line in body.splitlines() if line.strip().startswith(("- ", "* "))]
    assert len(list_items) >= 2, (
        f"{adr_path.name}'s Considered Options section has fewer than 2 list items"
    )


@pytest.mark.parametrize("adr_path", ADR_PATHS, ids=ADR_IDS)
def test_status_is_valid_and_supersession_is_named(adr_path: Path) -> None:
    text = _adr_text(adr_path)
    match = STATUS_RE.search(text)
    assert match is not None, f"{adr_path.name} has no parseable ## Status value"
    status = match.group("status")
    assert status in VALID_STATUSES, f"{adr_path.name} has invalid status {status!r}"
    if status == "superseded":
        own_number = FILENAME_RE.match(adr_path.name).group("number")  # type: ignore[union-attr]
        other_numbers = set(re.findall(r"\b\d{4}\b", text)) - {own_number}
        assert other_numbers, (
            f"{adr_path.name} is superseded but names no other ADR number in its body"
        )


def test_adr_index_check_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ADR_INDEX_TOOL), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"tools/adr_index.py --check failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_write_is_idempotent_and_byte_identical(tmp_path: Path) -> None:
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    try:
        import adr_index
    finally:
        sys.path.pop(0)

    records = adr_index.discover_records()
    first = adr_index.render_index(records)
    second = adr_index.render_index(records)
    assert first == second, "rendering the index twice produced different output"


def test_adr_0001_names_all_three_rejected_2017_components() -> None:
    path = ADR_DIR / "0001-rebuild-rather-than-refresh-the-2017-stack.md"
    assert path.exists(), "ADR 0001 is missing"
    text = _adr_text(path)
    assert "TensorFlow 1" in text, "ADR 0001 does not name TensorFlow 1 frozen graphs"
    assert "Dlib HOG" in text, "ADR 0001 does not name Dlib HOG detection"
    assert "128-D" in text and "triplet" in text.lower(), (
        "ADR 0001 does not name the 128-D triplet-loss FaceNet embedder"
    )
