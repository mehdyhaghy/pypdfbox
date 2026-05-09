from __future__ import annotations

from typing import Any

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(width: float = 4.0, height: float = 4.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (4, 4)) -> tuple[PDDocument, PDFRenderer]:
    doc, _page = _make_doc(float(size[0]), float(size[1]))
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", size, (255, 255, 255))  # noqa: SLF001
    renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
    renderer._draw.setantialias(True)  # noqa: SLF001
    renderer._gs_stack = [_GState()]  # noqa: SLF001
    renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001
    return doc, renderer


def _finish(renderer: PDFRenderer) -> None:
    draw = renderer._draw  # noqa: SLF001
    if draw is not None:
        draw.flush()


def test_transparency_group_helper_result_takes_precedence_over_group_dict() -> None:
    class _Form:
        def is_transparency_group(self) -> bool:
            return False

        def get_group(self) -> COSDictionary:
            group = COSDictionary()
            group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
            return group

    assert PDFRenderer._is_transparency_group(_Form()) is False  # noqa: SLF001


def test_blend_unknown_nonseparable_mode_falls_back_to_normal(
    caplog: Any,
) -> None:
    class _UnknownNonSeparable:
        name = "Mystery"

        def is_separable(self) -> bool:
            return False

    source = Image.new("RGBA", (1, 1), (0, 0, 255, 128))
    backdrop = Image.new("RGBA", (1, 1), (255, 255, 255, 255))

    caplog.set_level("DEBUG", logger="pypdfbox.rendering.pdf_renderer")
    blended = PDFRenderer._blend(source, backdrop, _UnknownNonSeparable())  # noqa: SLF001

    expected = backdrop.copy()
    expected.alpha_composite(source)
    assert blended.getpixel((0, 0)) == expected.getpixel((0, 0))
    assert "unknown non-separable blend mode 'Mystery'" in caplog.text


def test_paint_with_live_path_noops_without_draw_and_preserves_path() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._start_subpath(0.0, 0.0)  # noqa: SLF001
        renderer._current_subpath.append(("L", 2.0, 0.0))  # noqa: SLF001
        renderer._current_subpath.append(("L", 2.0, 2.0))  # noqa: SLF001
        renderer._draw = None  # noqa: SLF001

        renderer._paint(stroke=False, fill=True, even_odd=False)  # noqa: SLF001

        assert renderer._subpaths  # noqa: SLF001
        assert renderer._current_subpath is not None  # noqa: SLF001
        assert renderer._pending_clip is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
