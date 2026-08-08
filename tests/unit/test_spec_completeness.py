"""D-37 — the licensing-completeness invariant.

A spec cannot exist without a non-blank ``license`` and a non-blank
``training_data_provenance``. This is enforced two ways: pydantic's
``Field(min_length=1)`` at construction time (see ``specs.py``), and this
test walking every profile so a future spec added without either field
fails CI rather than review.
"""

from __future__ import annotations

from veriface.models.specs import PROFILES


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
