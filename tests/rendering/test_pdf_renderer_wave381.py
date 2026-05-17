from __future__ import annotations

import logging
from typing import Any

from PIL import Image

from pypdfbox.cos import COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.rendering import PDFRenderer, pdf_renderer
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import _GState


def _make_doc(width: float = 60.0, height: float = 60.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer() -> tuple[PDDocument, PDFRenderer]:
    doc, _page = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._gs_stack = [_GState()]  # noqa: SLF001
    renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001
    return doc, renderer


def _is_close(
    actual: tuple[int, int, int],
    expected: tuple[int, int, int],
    tol: int = 10,
) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual, expected, strict=True))


def test_dispatch_ignores_unknown_none_operands_and_logs_dropped_handler(
    caplog: Any,
    monkeypatch: Any,
) -> None:
    doc, renderer = _prepared_renderer()

    def _raise_value_error(_self: Any, _op: Any, _operands: list[Any]) -> None:
        raise ValueError("bad operands")

    try:
        renderer.process_operator("NotARealOperator", None)

        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        monkeypatch.setitem(pdf_renderer._DISPATCH, "rg", _raise_value_error)
        renderer.process_operator("rg", None)

        assert "rendering: dropping operator rg: bad operands" in caplog.text
    finally:
        doc.close()


def test_short_operands_leave_state_and_path_unchanged() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.stroke_rgb = (7, 8, 9)  # noqa: SLF001
        renderer._gs.fill_rgb = (11, 12, 13)  # noqa: SLF001
        renderer._gs.line_width = 3.0  # noqa: SLF001

        for name in ("cm", "RG", "rg", "G", "g", "K", "k", "m", "l", "c", "v", "y", "re"):
            renderer.process_operator(name, [])
        renderer.process_operator("h", [])
        renderer.process_operator("n", [])

        assert renderer._gs.stroke_rgb == (7, 8, 9)  # noqa: SLF001
        assert renderer._gs.fill_rgb == (11, 12, 13)  # noqa: SLF001
        assert renderer._gs.line_width == 3.0  # noqa: SLF001
        assert renderer._subpaths == []  # noqa: SLF001
        assert renderer._current_subpath is None  # noqa: SLF001

        renderer.process_operator("w", [COSFloat(-5.0)])
        assert renderer._gs.line_width == 0.0  # noqa: SLF001
    finally:
        doc.close()


def test_pattern_shading_and_extgstate_resolution_error_branches(caplog: Any) -> None:
    class _BadResources:
        def get_pattern(self, _name: COSName) -> Any:
            raise RuntimeError("pattern boom")

        def get_shading(self, _name: COSName) -> Any:
            raise RuntimeError("shading boom")

        def get_ext_gstate(self, name: COSName) -> Any:
            if name.name == "Missing":
                return None
            if name.name == "Broken":
                raise RuntimeError("extgstate boom")
            return _ExtGState()

    class _ExtGState:
        def get_blend_mode(self) -> Any:
            return BlendMode.MULTIPLY

        def get_soft_mask_typed(self) -> Any:
            raise RuntimeError("smask boom")

        def get_stroking_alpha_constant(self) -> float:
            return 2.0

        def get_non_stroking_alpha_constant(self) -> float:
            return -1.0

    doc, renderer = _prepared_renderer()
    renderer._resources = _BadResources()  # noqa: SLF001
    renderer._image = Image.new("RGB", (8, 8), (255, 255, 255))  # noqa: SLF001
    renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001

    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")

        assert renderer._resolve_pattern_operand([]) is None  # noqa: SLF001
        assert renderer._resolve_pattern_operand([COSFloat(1.0)]) is None  # noqa: SLF001
        assert renderer._resolve_pattern_operand([COSName.get_pdf_name("P0")]) is None  # noqa: SLF001
        assert "cannot resolve pattern P0" in caplog.text

        renderer.process_operator("sh", [COSName.get_pdf_name("Sh0")])
        renderer.process_operator("gs", [COSName.get_pdf_name("Broken")])
        renderer.process_operator("gs", [COSName.get_pdf_name("Missing")])
        renderer.process_operator("gs", [COSName.get_pdf_name("Good")])

        assert "cannot resolve shading Sh0" in caplog.text
        assert "cannot resolve ExtGState Broken" in caplog.text
        assert "cannot resolve ExtGState /SMask on Good" in caplog.text
        assert renderer._gs.blend_mode is BlendMode.MULTIPLY  # noqa: SLF001
        assert renderer._gs.stroke_alpha == 1.0  # noqa: SLF001
        assert renderer._gs.fill_alpha == 0.0  # noqa: SLF001
    finally:
        draw = renderer._draw  # noqa: SLF001
        if draw is not None:
            draw.flush()
        doc.close()


def test_clipped_even_odd_fill_then_stroke_uses_layer_path() -> None:
    doc, page = _make_doc()
    try:
        contents = COSStream()
        contents.set_raw_data(
            b"10 10 40 40 re\n"
            b"W n\n"
            b"0 0 1 rg\n"
            b"1 0 0 RG\n"
            b"2 w\n"
            b"15 15 30 30 re\n"
            b"25 25 10 10 re\n"
            b"B*\n"
        )
        page.get_cos_object().set_item(COSName.CONTENTS, contents)

        img = PDFRenderer(doc).render_image(0)

        assert _is_close(img.getpixel((20, 30)), (0, 0, 255)), img.getpixel((20, 30))
        assert _is_close(img.getpixel((30, 30)), (255, 255, 255)), img.getpixel((30, 30))
        assert _is_close(img.getpixel((5, 5)), (255, 255, 255)), img.getpixel((5, 5))
    finally:
        doc.close()
