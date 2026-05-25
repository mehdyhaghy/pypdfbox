"""Wave 1403 branch round-out for ``custom_page_drawer``.

Closes ``52->56``: when the active non-stroking color *is* the requested
color but its RGB value is not red, ``if color.to_rgb_int() == _RED_RGB``
takes its False arc and ``get_paint`` falls through to ``super().get_paint``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from pypdfbox.examples.rendering.custom_page_drawer import (
    _GREEN_RGB,
    MyPageDrawer,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.rendering.page_drawer_parameters import PageDrawerParameters
from pypdfbox.rendering.pdf_renderer import PDFRenderer
from pypdfbox.rendering.render_destination import RenderDestination


def _make_drawer() -> tuple[PDDocument, MyPageDrawer]:
    doc = PDDocument()
    doc.add_page(PDPage())
    renderer = PDFRenderer(doc)
    params = PageDrawerParameters(
        renderer, doc.get_page(0), True, RenderDestination.EXPORT, {}, 0.5,
    )
    return doc, MyPageDrawer(params)


def test_get_paint_passes_through_non_red_matching_color(monkeypatch) -> None:
    doc, drawer = _make_drawer()
    try:
        class _GreenColor:
            def to_rgb_int(self) -> int:
                return _GREEN_RGB

        color = _GreenColor()
        fake_gs = MagicMock()
        fake_gs.get_non_stroking_color.return_value = color
        drawer.get_graphics_state = lambda: fake_gs  # type: ignore[method-assign]

        sentinel = object()
        # Stub the parent so we can assert the fall-through reached it
        # without depending on the real paint pipeline.
        monkeypatch.setattr(
            type(drawer).__mro__[1],
            "get_paint",
            lambda self, c: sentinel,
            raising=True,
        )

        # Non-red color → 52 False arc → falls through to super().get_paint.
        assert drawer.get_paint(color) is sentinel
    finally:
        doc.close()
