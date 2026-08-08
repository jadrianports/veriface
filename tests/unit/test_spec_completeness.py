"""D-37 — the licensing-completeness invariant.

A spec cannot exist without a non-blank ``license`` and a non-blank
``training_data_provenance``. This is enforced two ways: pydantic's
``Field(min_length=1)`` at construction time (see ``specs.py``), and this
test walking every profile so a future spec added without either field
fails CI rather than review.
"""

from __future__ import annotations

import re

from veriface.models.specs import PROFILES

_FULL_COMMIT_HASH_RE = re.compile(r"[0-9a-f]{40}")


def test_every_spec_has_license_and_provenance() -> None:
    for profile_name, specs in PROFILES.items():
        for spec in specs:
            assert spec.license.strip(), f"{profile_name}/{spec.name} has a blank license"
            assert spec.training_data_provenance.strip(), (
                f"{profile_name}/{spec.name} has a blank training_data_provenance"
            )


def test_insightface_sourced_rows_are_labeled_non_commercial() -> None:
    """Catches a future contributor pasting an MIT *code* licence over
    InsightFace's non-commercial *weights* licence (CLAUDE.md's Licensing
    section — the exact landmine this invariant exists to prevent).

    Identified structurally by ``locator`` (InsightFace's own distribution
    URL), not by the license text itself — the license text is the thing
    under test, so it cannot also be the selector.
    """
    found_any = False
    for specs in PROFILES.values():
        for spec in specs:
            if "insightface" in spec.locator.lower():
                found_any = True
                assert "non-commercial" in spec.license.lower(), (
                    f"{spec.name} is sourced from InsightFace's own distribution "
                    f"but its license text does not say non-commercial: {spec.license!r}"
                )
    assert found_any, "expected at least one InsightFace-sourced spec in PROFILES"


def test_hf_sourced_specs_pin_a_full_commit_hash() -> None:
    """WR-04 — ``ArtifactSpec.revision``'s docstring states it must be a *"full
    40-character commit hash for the 'hf' source"* — this is the entire basis
    of ADR 0004's "pinned revision" guarantee for that source leg. Nothing at
    construction time enforces it (adding a model validator that branches on
    ``source == "hf"`` would live in ``specs.py``, which
    ``test_source_resolver_boundary.py`` forbids from branching on
    ``spec.source`` at all — see the module's own module docstring), so this
    test is the enforcement point: a future ``hf``-source spec pinned to a
    branch name or short SHA fails CI here rather than silently reintroducing
    the "not really pinned" failure mode ADR 0004 was written to rule out.
    """
    checked_any = False
    for profile_name, specs in PROFILES.items():
        for spec in specs:
            if spec.source == "hf":
                checked_any = True
                assert _FULL_COMMIT_HASH_RE.fullmatch(spec.revision), (
                    f"{profile_name}/{spec.name} is source='hf' but revision "
                    f"{spec.revision!r} is not a full 40-character lowercase hex "
                    "commit hash"
                )
    assert checked_any, "expected at least one hf-sourced spec in PROFILES"
