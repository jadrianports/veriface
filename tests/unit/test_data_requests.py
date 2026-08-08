"""D-26/D-27: the gated-dataset request tracker and the attack-class coverage matrix.

Parses the two committed Markdown documents structurally (never by re-typing their prose into the
assertions) so a placeholder date or a dropped required row is a red test, not a silent gap.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_REQUESTS_PATH = REPO_ROOT / "docs" / "data-requests.md"
COVERAGE_MATRIX_PATH = REPO_ROOT / "docs" / "dataset-coverage-matrix.md"

_REQUIRED_COLUMNS = (
    "Dataset",
    "Date submitted",
    "Route / contact",
    "Status",
    "Follow-up date",
    "Outcome",
)

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _table_rows(text: str) -> list[list[str]]:
    """Parse every pipe-delimited Markdown table row (header, separator, and body)."""
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            rows.append(cells)
    return rows


def _data_requests_text() -> str:
    return DATA_REQUESTS_PATH.read_text(encoding="utf-8")


def _coverage_matrix_text() -> str:
    return COVERAGE_MATRIX_PATH.read_text(encoding="utf-8")


def _find_row(rows: list[list[str]], first_cell_prefix: str) -> list[str]:
    for row in rows:
        if row and row[0].startswith(first_cell_prefix):
            return row
    raise AssertionError(f"no row found with first cell starting {first_cell_prefix!r}")


def test_data_requests_header_has_all_six_required_columns() -> None:
    rows = _table_rows(_data_requests_text())
    header = rows[0]
    assert header == list(_REQUIRED_COLUMNS), f"unexpected header: {header}"


def test_bfw_row_exists() -> None:
    rows = _table_rows(_data_requests_text())
    bfw_row = _find_row(rows, "BFW")
    assert "Balanced Faces in the Wild" in bfw_row[0]


def test_bfw_date_submitted_is_a_real_date_not_a_placeholder() -> None:
    rows = _table_rows(_data_requests_text())
    bfw_row = _find_row(rows, "BFW")
    date_cell = bfw_row[1]
    assert _DATE_RE.fullmatch(date_cell), f"BFW Date submitted is not YYYY-MM-DD: {date_cell!r}"
    assert date_cell not in {"TBD", "-", ""}


def test_bfw_follow_up_date_is_real_and_later_than_submission() -> None:
    rows = _table_rows(_data_requests_text())
    bfw_row = _find_row(rows, "BFW")
    submitted = date.fromisoformat(bfw_row[1])
    follow_up_cell = bfw_row[4]
    assert _DATE_RE.fullmatch(follow_up_cell), f"BFW Follow-up date is not YYYY-MM-DD: {follow_up_cell!r}"
    follow_up = date.fromisoformat(follow_up_cell)
    assert follow_up > submitted, "BFW follow-up date must be later than the submission date"


def test_data_requests_notes_pitfalls_description_is_superseded() -> None:
    text = _data_requests_text()
    assert "superseded" in text.lower()
    assert "PITFALLS.md" in text


def test_coverage_matrix_has_print_and_screen_replay_rows_naming_celeba_spoof() -> None:
    rows = _table_rows(_coverage_matrix_text())
    print_row = _find_row(rows, "print")
    screen_replay_row = _find_row(rows, "screen replay")
    assert "CelebA-Spoof" in print_row[1]
    assert "CelebA-Spoof" in screen_replay_row[1]


def test_coverage_matrix_lists_video_replay_out_of_v1_with_a_reason() -> None:
    rows = _table_rows(_coverage_matrix_text())
    video_replay_row = _find_row(rows, "video replay")
    assert "out of v1" in video_replay_row[1].lower()
    reason = video_replay_row[2]
    assert reason.strip(), "video replay row must state a reason"
    assert "D-39" in reason or "shelved" in reason.lower()


def test_coverage_matrix_lists_3d_mask_as_unvalidated_with_a_reason() -> None:
    rows = _table_rows(_coverage_matrix_text())
    mask_row = _find_row(rows, "3D mask")
    assert "unvalidated" in mask_row[1].lower()
    reason = mask_row[2]
    assert reason.strip(), "3D mask row must state a reason"
    assert "dataset" in reason.lower()
