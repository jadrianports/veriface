"""D-19/D-21 invariants for the CelebA-Spoof subset manifest — pinned against a
synthetic label index, before a single CelebA-Spoof byte is downloaded.

``_make_label_index`` builds several subjects with deliberately uneven
per-class counts, several spoof classes, and a random enumeration order, so
none of these tests can pass by accident of a tidy input.
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from veriface_eval.datasets.manifest import (
    EmptyLabelIndexError,
    InsufficientSubjectPoolError,
    ManifestHeader,
    ManifestRow,
    build_manifest,
    manifest_sha256,
    read_manifest,
    write_manifest,
)

_SPLITS = {"train": 0.6, "val": 0.2, "test": 0.2}


def _make_label_index(
    *, subjects: int = 24, seed: int = 1
) -> list[tuple[str, str, str]]:
    """A synthetic ``(subject_id, relative_path, spoof_class)`` label index.

    Per-subject, per-class counts are deliberately uneven (1..6 images per
    class) so a naive "keep everything" sampler would fail the class-balance
    invariant, and enumeration order is randomized independently of any seed
    ``build_manifest`` itself uses.
    """
    rng = random.Random(seed)
    classes = ("live", "print", "screen_replay")
    rows: list[tuple[str, str, str]] = []
    for subject_index in range(subjects):
        subject_id = f"subject_{subject_index:04d}"
        for spoof_class in classes:
            count = rng.randint(1, 6)
            for image_index in range(count):
                rows.append(
                    (subject_id, f"{subject_id}/{spoof_class}_{image_index:03d}.jpg", spoof_class)
                )
    rng.shuffle(rows)
    return rows


def _params(target_subjects: int, *, offset: int = 0, tolerance: float = 0.0) -> dict[str, object]:
    return {
        "target_subjects": target_subjects,
        "subject_pool_offset": offset,
        "class_balance_tolerance": tolerance,
        "splits": dict(_SPLITS),
    }


def test_build_manifest_is_deterministic_across_calls() -> None:
    label_index = _make_label_index()
    header1, rows1 = build_manifest(label_index, tier="eval", seed=42, params=_params(10))
    header2, rows2 = build_manifest(label_index, tier="eval", seed=42, params=_params(10))
    assert rows1 == rows2
    assert header1.seed == header2.seed == 42


def test_write_manifest_is_byte_identical_across_writes(tmp_path: Path) -> None:
    label_index = _make_label_index()
    header, rows = build_manifest(label_index, tier="eval", seed=7, params=_params(10))
    path1 = tmp_path / "one.csv"
    path2 = tmp_path / "two.csv"
    write_manifest(rows, header, path1)
    write_manifest(rows, header, path2)
    assert path1.read_bytes() == path2.read_bytes()


def test_eval_and_extended_tiers_are_subject_disjoint_for_the_same_seed() -> None:
    label_index = _make_label_index(subjects=24)
    _, eval_rows = build_manifest(label_index, tier="eval", seed=99, params=_params(10, offset=0))
    _, extended_rows = build_manifest(
        label_index, tier="extended", seed=99, params=_params(10, offset=10)
    )
    eval_subjects = {row.subject_id for row in eval_rows}
    extended_subjects = {row.subject_id for row in extended_rows}
    assert eval_subjects.isdisjoint(extended_subjects)


def test_selected_subject_set_is_independent_of_label_index_enumeration_order() -> None:
    label_index = _make_label_index()
    shuffled = label_index.copy()
    random.Random(12345).shuffle(shuffled)
    assert shuffled != label_index  # the shuffle actually changed the order

    _, rows_original = build_manifest(label_index, tier="eval", seed=5, params=_params(10))
    _, rows_shuffled = build_manifest(shuffled, tier="eval", seed=5, params=_params(10))

    assert {row.subject_id for row in rows_original} == {row.subject_id for row in rows_shuffled}


def test_empty_label_index_raises_named_error() -> None:
    with pytest.raises(EmptyLabelIndexError):
        build_manifest([], tier="eval", seed=1, params=_params(1))


def test_target_subjects_exceeding_pool_raises_named_error() -> None:
    label_index = _make_label_index(subjects=5)
    with pytest.raises(InsufficientSubjectPoolError):
        build_manifest(label_index, tier="eval", seed=1, params=_params(10))


def test_read_manifest_round_trips_rows_and_header(tmp_path: Path) -> None:
    label_index = _make_label_index()
    header, rows = build_manifest(label_index, tier="eval", seed=3, params=_params(10))
    path = tmp_path / "manifest.csv"
    write_manifest(rows, header, path)

    read_header, read_rows = read_manifest(path)

    assert read_header == header
    assert read_rows == rows


def test_no_manifest_row_carries_a_video_replay_class() -> None:
    with pytest.raises(ValidationError):
        ManifestRow(
            subject_id="subject_0000",
            relative_path="subject_0000/video_replay_000.jpg",
            spoof_class="video_replay",  # type: ignore[arg-type]
            split="train",
        )


def test_class_balance_within_declared_tolerance() -> None:
    label_index = _make_label_index(subjects=24)
    tolerance = 0.0
    _, rows = build_manifest(label_index, tier="eval", seed=11, params=_params(12, tolerance=tolerance))

    counts = Counter(row.spoof_class for row in rows)
    assert set(counts) == {"live", "print", "screen_replay"}
    live_count = counts["live"]
    for spoof_class, count in counts.items():
        allowed = tolerance * max(live_count, count)
        assert abs(live_count - count) <= allowed + 1e-9, (
            f"{spoof_class} count {count} exceeds tolerance against live count {live_count}"
        )


def test_no_subject_spans_two_splits_within_a_tier() -> None:
    label_index = _make_label_index(subjects=24)
    _, rows = build_manifest(label_index, tier="eval", seed=17, params=_params(12))

    subject_to_splits: dict[str, set[str]] = {}
    for row in rows:
        subject_to_splits.setdefault(row.subject_id, set()).add(row.split)

    offenders = {subject: splits for subject, splits in subject_to_splits.items() if len(splits) > 1}
    assert offenders == {}


def test_rows_are_written_in_a_specified_stable_order() -> None:
    """Not an accident of ``sorted()`` — the order is subject id, then relative path."""
    label_index = _make_label_index(subjects=24)
    _, rows = build_manifest(label_index, tier="eval", seed=23, params=_params(12))

    expected = sorted(rows, key=lambda row: (row.subject_id, row.relative_path))
    assert rows == expected


def test_header_records_enough_to_tell_manifest_and_label_index_apart() -> None:
    label_index = _make_label_index()
    header, _ = build_manifest(label_index, tier="eval", seed=29, params=_params(10))

    assert header.seed == 29
    assert header.tier == "eval"
    assert isinstance(header.sampler_version, str) and header.sampler_version
    assert header.params["target_subjects"] == 10
    assert isinstance(header.label_index_sha256, str) and len(header.label_index_sha256) == 64
    assert isinstance(header.generated_at, str) and header.generated_at
    assert isinstance(header.description, str) and header.description


def test_manifest_sha256_delegates_to_core_hashing(tmp_path: Path) -> None:
    label_index = _make_label_index()
    header, rows = build_manifest(label_index, tier="eval", seed=31, params=_params(10))
    path = tmp_path / "manifest.csv"
    write_manifest(rows, header, path)

    from veriface.hashing import sha256_file

    assert manifest_sha256(path) == sha256_file(path)


def test_manifest_header_type_is_exported() -> None:
    # Guards against accidentally dropping the export while refactoring.
    assert ManifestHeader is not None
