"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDPageTransitions.java

Upstream baseline: PDFBox 3.0.x. Fixture ``transitions_test.pdf`` bundled
under ``tests/fixtures/pdmodel/interactive/pagenavigation/``.

The upstream test calls ``firstTransition.getDirection()`` which returns the
underlying ``COSBase`` (``COSName.NONE`` or a ``COSInteger``). In pypdfbox
the same value is exposed via :meth:`PDTransition.get_direction_cos` —
:meth:`get_direction` itself returns a plain Python ``int`` for ergonomics.
We test both ways so the parity is unambiguous.
"""
from __future__ import annotations

import io
from pathlib import Path

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.pagenavigation import (
    PDTransition,
    PDTransitionDirection,
    PDTransitionStyle,
)

_FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "fixtures" / "pdmodel" / "interactive" / "pagenavigation"
)


def test_read_transitions() -> None:
    with PDDocument.load(_FIXTURES / "transitions_test.pdf") as doc:
        first_transition = doc.get_pages()[0].get_transition()
        assert first_transition.get_style() == PDTransitionStyle.GLITTER
        assert first_transition.get_duration() == 2
        # upstream: PDTransitionDirection.TOP_LEFT_TO_BOTTOM_RIGHT.getCOSBase()
        # pypdfbox: integer constant + get_direction_cos returns COSBase
        assert first_transition.get_direction() == PDTransitionDirection.TOP_LEFT_TO_BOTTOM_RIGHT
        assert (
            first_transition.get_direction_cos()
            == PDTransitionDirection.get_cos_base(PDTransitionDirection.TOP_LEFT_TO_BOTTOM_RIGHT)
        )


def test_save_and_read_transitions() -> None:
    baos = io.BytesIO()

    # save
    document = PDDocument()
    try:
        page = PDPage()
        document.add_page(page)
        # ``PDTransition.__init__(dictionary, style)`` — pass style by keyword
        # to match upstream's ``new PDTransition(PDTransitionStyle)`` shape.
        transition = PDTransition(style=PDTransitionStyle.FLY)
        transition.set_direction(PDTransitionDirection.NONE)
        transition.set_fly_scale(0.5)
        page.set_transition(transition, 2)
        document.save(baos)
    finally:
        document.close()

    # read
    with PDDocument.load(baos.getvalue()) as doc:
        page = doc.get_pages()[0]
        loaded_transition = page.get_transition()
        assert loaded_transition.get_style() == PDTransitionStyle.FLY
        assert page.get_cos_object().get_float(COSName.get_pdf_name("Dur")) == 2
        assert (
            loaded_transition.get_direction_cos()
            == PDTransitionDirection.get_cos_base(PDTransitionDirection.NONE)
        )
