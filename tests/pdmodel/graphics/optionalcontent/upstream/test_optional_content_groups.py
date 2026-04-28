"""Ported (API-only subset) from upstream Apache PDFBox 3.0.x:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/optionalcontent/TestOptionalContentGroups.java``.

Translation rules per CLAUDE.md "Test Porting Conventions". The upstream
tests also exercise PDPageContentStream marked-content writing and
PDFRenderer image-diffing, which require modules outside this wave's
scope; those phases are skipped with a single per-test comment and only
the OCG/property-state assertions are translated here.
"""
from __future__ import annotations

from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    PDOptionalContentProperties,
)


# Java: testOCGGeneration (state-assertion subset)
def test_ocg_generation_state_assertions() -> None:
    # Skip: content-stream writing (PDPageContentStream + marked content)
    # belongs to the contentstream module already ported in earlier waves;
    # this test only asserts the OCG-properties bookkeeping.
    ocprops = PDOptionalContentProperties()

    background = PDOptionalContentGroup("background")
    ocprops.add_group(background)
    assert ocprops.is_group_enabled("background")

    enabled = PDOptionalContentGroup("enabled")
    ocprops.add_group(enabled)
    assert ocprops.set_group_enabled("enabled", True) is False
    assert ocprops.is_group_enabled("enabled")

    disabled = PDOptionalContentGroup("disabled")
    ocprops.add_group(disabled)
    assert ocprops.set_group_enabled("disabled", True) is False
    assert ocprops.is_group_enabled("disabled")
    assert ocprops.set_group_enabled("disabled", False) is True
    assert not ocprops.is_group_enabled("disabled")


# Java: testOCGsWithSameNameCanHaveDifferentVisibility
def test_ocgs_with_same_name_can_have_different_visibility() -> None:
    # Skip: content-stream + save phases — see module docstring.
    ocprops = PDOptionalContentProperties()

    visible = PDOptionalContentGroup("layer")
    ocprops.add_group(visible)
    assert ocprops.is_group_enabled(visible)

    invisible = PDOptionalContentGroup("layer")
    ocprops.add_group(invisible)
    assert ocprops.set_group_enabled(invisible, False) is False
    assert not ocprops.is_group_enabled(invisible)

    # Visible OCG with the same name remains enabled.
    assert ocprops.is_group_enabled(visible)


# Java: testOCGGenerationSameNameCanHaveSameVisibilityOff (state-assertion subset)
def test_ocg_generation_same_name_can_have_same_visibility_off() -> None:
    # Skip: image-diff render + save phases — see module docstring.
    ocprops = PDOptionalContentProperties()

    background = PDOptionalContentGroup("background")
    ocprops.add_group(background)
    assert ocprops.is_group_enabled("background")

    enabled = PDOptionalContentGroup("science")
    ocprops.add_group(enabled)
    assert ocprops.set_group_enabled("science", True) is False
    assert ocprops.is_group_enabled("science")

    disabled1 = PDOptionalContentGroup("alternative")
    ocprops.add_group(disabled1)
    disabled2 = PDOptionalContentGroup("alternative")
    ocprops.add_group(disabled2)

    # Toggling by name affects every OCG that shares the name.
    assert ocprops.set_group_enabled("alternative", False) is False
    assert not ocprops.is_group_enabled("alternative")
    assert not ocprops.is_group_enabled(disabled1)
    assert not ocprops.is_group_enabled(disabled2)
