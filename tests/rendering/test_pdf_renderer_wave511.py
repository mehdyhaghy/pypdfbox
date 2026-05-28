from __future__ import annotations

import logging
from typing import Any

from PIL import Image

from pypdfbox.cos import COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering import pdf_renderer
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(width: float = 8.0, height: float = 8.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (8, 8)) -> tuple[PDDocument, PDFRenderer]:
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


def test_dispatch_logs_and_drops_malformed_operator(monkeypatch: Any, caplog: Any) -> None:
    doc, renderer = _prepared_renderer()

    def _raising_handler(
        _renderer: PDFRenderer,
        _op: object,
        _operands: list[object],
    ) -> None:
        raise ValueError("bad operands")

    monkeypatch.setitem(pdf_renderer._DISPATCH, "rg", _raising_handler)  # noqa: SLF001
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")

        renderer.process_operator("rg", [COSFloat(1.0)])

        assert "rendering: dropping operator rg: bad operands" in caplog.text
    finally:
        _finish(renderer)
        doc.close()


def test_pattern_color_space_clears_stale_pattern_except_for_pattern_space() -> None:
    doc, renderer = _prepared_renderer()
    try:
        stroke_pattern = object()
        fill_pattern = object()
        renderer._gs.stroke_pattern = stroke_pattern  # noqa: SLF001
        renderer._gs.fill_pattern = fill_pattern  # noqa: SLF001

        renderer.process_operator("CS", [COSName.get_pdf_name("Pattern")])
        renderer.process_operator("cs", [COSName.get_pdf_name("Pattern")])
        assert renderer._gs.stroke_pattern is stroke_pattern  # noqa: SLF001
        assert renderer._gs.fill_pattern is fill_pattern  # noqa: SLF001

        renderer.process_operator("CS", [COSName.get_pdf_name("DeviceRGB")])
        renderer.process_operator("cs", [COSFloat(0.0)])
        assert renderer._gs.stroke_pattern is None  # noqa: SLF001
        assert renderer._gs.fill_pattern is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_pattern_operand_resolves_success_and_logs_resource_failure(
    caplog: Any,
) -> None:
    class _Resources:
        def __init__(self) -> None:
            self.pattern = object()

        def get_pattern(self, name: COSName) -> object:
            assert name.name == "P1"
            return self.pattern

    class _BrokenResources:
        def get_pattern(self, _name: COSName) -> object:
            raise RuntimeError("pattern boom")

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        resources = _Resources()
        renderer._resources = resources  # noqa: SLF001

        renderer.process_operator("scn", [COSFloat(0.5), COSName.get_pdf_name("P1")])
        renderer.process_operator("SCN", [COSName.get_pdf_name("P1")])
        assert renderer._gs.fill_pattern is resources.pattern  # noqa: SLF001
        assert renderer._gs.stroke_pattern is resources.pattern  # noqa: SLF001

        renderer._resources = _BrokenResources()  # noqa: SLF001
        assert renderer._resolve_pattern_operand([COSName.get_pdf_name("P1")]) is None  # noqa: SLF001
        assert "cannot resolve pattern P1: pattern boom" in caplog.text
    finally:
        _finish(renderer)
        doc.close()


def test_extgstate_alpha_constants_are_clamped_and_soft_mask_is_stored() -> None:
    class _ExtGState:
        def __init__(self) -> None:
            self.soft_mask = object()

        def get_cos_object(self) -> COSDictionary:
            # The ExtGState must carry /BM for the renderer to apply the
            # blend mode (upstream copyIntoGraphicsState only applies /BM
            # when the dict contains the key).
            d = COSDictionary()
            d.set_item(COSName.get_pdf_name("BM"), COSName.get_pdf_name("Screen"))
            return d

        def get_blend_mode(self) -> BlendMode:
            return BlendMode.SCREEN

        def get_soft_mask_typed(self) -> object:
            return self.soft_mask

        def get_stroking_alpha_constant(self) -> float:
            return 2.0

        def get_non_stroking_alpha_constant(self) -> float:
            return -1.0

    class _Resources:
        def __init__(self) -> None:
            self.ext_gstate = _ExtGState()

        def get_ext_gstate(self, name: COSName) -> _ExtGState:
            assert name.name == "GS1"
            return self.ext_gstate

    doc, renderer = _prepared_renderer()
    try:
        resources = _Resources()
        renderer._resources = resources  # noqa: SLF001

        renderer.process_operator("gs", [COSName.get_pdf_name("GS1")])

        assert renderer._gs.blend_mode is BlendMode.SCREEN  # noqa: SLF001
        assert renderer._gs.soft_mask is resources.ext_gstate.soft_mask  # noqa: SLF001
        assert renderer._gs.stroke_alpha == 1.0  # noqa: SLF001
        assert renderer._gs.fill_alpha == 0.0  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
