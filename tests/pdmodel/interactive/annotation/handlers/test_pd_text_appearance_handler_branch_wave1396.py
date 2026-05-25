"""Wave 1396 branch-coverage tests for ``PDTextAppearanceHandler.add_path``
and ``_adjust_rect_and_bbox``.

Closes False-branch arrows:

* 158->162 — ``_adjust_rect_and_bbox`` skip rect update when no rect
* 162->168 — ``_adjust_rect_and_bbox`` skip /F branch when /F is present
* 215->201 — ``add_path`` unknown op falls through silently
"""

from __future__ import annotations

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.interactive.annotation.handlers.pd_text_appearance_handler import (  # noqa: E501
    PDTextAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import (
    PDAnnotationText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)


def _appearance_stream() -> PDAppearanceContentStream:
    return PDAppearanceContentStream(PDAppearanceStream(COSStream()))


def test_add_path_skips_unknown_operators() -> None:
    """Unknown path operator is silently skipped.

    Closes False arm at line 215.
    """
    annot = PDAnnotationText()
    handler = PDTextAppearanceHandler(annot)
    cs = _appearance_stream()
    # Path containing an unrecognised "X" op.
    handler.add_path(
        cs,
        [
            ("M", (0.0, 0.0)),
            ("X", (1.0, 2.0)),  # unknown → skipped
            ("H", ()),
        ],
    )
    # Method completed without raising.


def test_adjust_rect_and_bbox_when_rect_is_none_skips_resize() -> None:
    """When the annotation has no /Rect, the rect-resize branch is skipped.

    Closes False arm at line 158 (``rect is not None and not is_no_zoom``).
    """
    annot = PDAnnotationText()
    # Remove /Rect entirely so get_rectangle() returns None.
    annot.get_cos_object().remove_item(COSName.get_pdf_name("Rect"))
    handler = PDTextAppearanceHandler(annot)
    bbox = handler._adjust_rect_and_bbox(annot, 24.0, 24.0)  # noqa: SLF001
    assert bbox is not None
    # Width/height carried through to the bbox even though rect was unchanged.
    assert bbox.get_width() == 24.0
    assert bbox.get_height() == 24.0


def test_adjust_rect_and_bbox_when_flags_present_skips_setting_no_rotate() -> None:
    """When /F is present, we skip setting NoRotate / NoZoom.

    Closes False arm at line 162.
    """
    annot = PDAnnotationText()
    # Pre-set /F so the branch sees it present.
    annot.get_cos_object().set_int(COSName.get_pdf_name("F"), 0)
    handler = PDTextAppearanceHandler(annot)
    handler._adjust_rect_and_bbox(annot, 24.0, 24.0)  # noqa: SLF001
    # NoRotate / NoZoom are not set since we skipped the branch.
    assert annot.is_no_rotate() is False
    assert annot.is_no_zoom() is False
