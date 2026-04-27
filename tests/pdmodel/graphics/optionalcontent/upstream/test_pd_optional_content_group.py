"""Ported from upstream Apache PDFBox 3.0.x:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/graphics/optionalcontent/PDOptionalContentGroupTest.java``.

Translation rules per CLAUDE.md §"Test Porting Conventions": JUnit
``@Test`` → ``def test_...``; ``assertEquals(expected, actual)`` →
``assert actual == expected``; ``assertNull(x)`` → ``assert x is None``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent import (
    PDOptionalContentGroup,
    RenderState,
)


# Java: testCreateNewGroup
def test_create_new_group() -> None:
    ocg = PDOptionalContentGroup("Test Group")
    assert ocg.get_name() == "Test Group"
    cos = ocg.get_cos_object()
    assert cos.get_dictionary_object(COSName.TYPE) == COSName.get_pdf_name(  # type: ignore[attr-defined]
        "OCG"
    )


# Java: testRenameGroup
def test_rename_group() -> None:
    ocg = PDOptionalContentGroup("Initial")
    ocg.set_name("Renamed")
    assert ocg.get_name() == "Renamed"


# Java: testRejectWrongType — when wrapping a dict whose /Type is not /OCG.
def test_reject_wrong_type() -> None:
    raw = COSDictionary()
    raw.set_item(
        COSName.TYPE,  # type: ignore[attr-defined]
        COSName.get_pdf_name("Catalog"),
    )
    with pytest.raises(ValueError):
        PDOptionalContentGroup(raw)


# Java: testRenderState — round-trip of usage /PrintState etc.
def test_render_state_round_trip() -> None:
    ocg = PDOptionalContentGroup("L")
    assert ocg.get_render_state("Print") is None
    ocg.set_render_state("OFF", "Print")
    assert ocg.get_render_state("Print") == "OFF"


# Java: testRenderStateEnum — typed-enum mirror.
def test_render_state_enum_round_trip() -> None:
    ocg = PDOptionalContentGroup("L")
    ocg.set_render_state_enum(RenderState.ON, "View")
    assert ocg.get_render_state_enum("View") is RenderState.ON
