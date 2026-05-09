from __future__ import annotations

import math
from typing import Any

import aggdraw  # type: ignore[import-not-found]
import pytest
from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(width: float = 6.0, height: float = 6.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (3, 3)) -> tuple[PDDocument, PDFRenderer]:
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


@pytest.mark.parametrize("dpi", [0.01, math.nextafter(0.0, 1.0)])
def test_render_image_with_dpi_keeps_subpixel_pages_at_one_pixel(dpi: float) -> None:
    doc, _page = _make_doc(0.1, 0.1)
    try:
        renderer = PDFRenderer(doc)

        image = renderer.render_image_with_dpi(0, dpi=dpi)

        assert image.size == (1, 1)
        assert renderer.get_page_image() is image
        assert image.getpixel((0, 0)) == (255, 255, 255)
    finally:
        doc.close()


def test_render_image_resets_per_render_font_warning_caches(
    monkeypatch: Any,
) -> None:
    doc, _page = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._warned_standard14_fonts.add(123)  # noqa: SLF001
    renderer._font_program_cache[456] = object()  # noqa: SLF001

    def _capture_reset(_page: PDPage) -> None:
        assert renderer._warned_standard14_fonts == set()  # noqa: SLF001
        assert renderer._font_program_cache == {}  # noqa: SLF001

    try:
        monkeypatch.setattr(renderer, "process_page", _capture_reset)

        renderer.render_image(0)
    finally:
        doc.close()


def test_extgstate_accessor_failures_leave_transparency_defaults(
    caplog: Any,
) -> None:
    class _Resources:
        def get_ext_gstate(self, name: COSName) -> object:
            assert name.name == "GS0"
            return _BrokenExtGState()

    class _BrokenExtGState:
        def get_blend_mode(self) -> object:
            raise RuntimeError("blend unavailable")

        def get_soft_mask_typed(self) -> object:
            raise RuntimeError("smask unavailable")

        def get_stroking_alpha_constant(self) -> object:
            raise RuntimeError("CA unavailable")

        def get_non_stroking_alpha_constant(self) -> object:
            raise RuntimeError("ca unavailable")

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level("DEBUG", logger="pypdfbox.rendering.pdf_renderer")
        renderer._resources = _Resources()  # noqa: SLF001

        renderer.process_operator("gs", [COSName.get_pdf_name("GS0")])

        assert renderer._gs.blend_mode is None  # noqa: SLF001
        assert renderer._gs.soft_mask is None  # noqa: SLF001
        assert renderer._gs.stroke_alpha == 1.0  # noqa: SLF001
        assert renderer._gs.fill_alpha == 1.0  # noqa: SLF001
        assert "cannot resolve ExtGState /SMask on GS0: smask unavailable" in caplog.text
    finally:
        _finish(renderer)
        doc.close()
