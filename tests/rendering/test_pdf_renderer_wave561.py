from __future__ import annotations

from typing import Any

import pytest
from PIL import Image

from pypdfbox.cos import COSFloat, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import ImageType
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering import pdf_renderer as renderer_module
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


def test_render_image_flushes_current_draw_after_process_page_rebinds_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc, _page = _make_doc()
    renderer = PDFRenderer(doc)

    def _draw_with_rebound_canvas(_page: PDPage) -> None:
        assert renderer._image is not None  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        renderer._draw.setantialias(False)  # noqa: SLF001
        path = aggdraw.Path()
        path.moveto(0.0, 0.0)
        path.lineto(4.0, 0.0)
        path.lineto(4.0, 4.0)
        path.lineto(0.0, 4.0)
        path.close()
        renderer._draw.path(path, None, aggdraw.Brush((0, 0, 0)))  # noqa: SLF001

    try:
        monkeypatch.setattr(renderer, "process_page", _draw_with_rebound_canvas)

        image = renderer.render_image_with_dpi(0, dpi=72.0, image_type=ImageType.ARGB)

        assert image.mode == "RGBA"
        assert renderer.get_page_image() is image
        assert image.getpixel((1, 1)) == (0, 0, 0, 255)
        assert image.getpixel((3, 3)) == (0, 0, 0, 255)
    finally:
        doc.close()


def test_process_operator_logs_and_swallows_handler_index_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: Any,
) -> None:
    def _broken_handler(
        _renderer: PDFRenderer,
        _op: Any,
        _operands: list[Any],
    ) -> None:
        raise IndexError("synthetic bad operand")

    doc, renderer = _prepared_renderer()
    original = renderer_module._DISPATCH["RG"]  # noqa: SLF001
    try:
        caplog.set_level("DEBUG", logger="pypdfbox.rendering.pdf_renderer")
        monkeypatch.setitem(renderer_module._DISPATCH, "RG", _broken_handler)  # noqa: SLF001

        renderer.process_operator(
            "RG",
            [COSFloat(1.0), COSFloat(0.0), COSFloat(0.0)],
        )

        assert "dropping operator RG: synthetic bad operand" in caplog.text
        assert renderer._gs.stroke_rgb == (0, 0, 0)  # noqa: SLF001
    finally:
        monkeypatch.setitem(renderer_module._DISPATCH, "RG", original)  # noqa: SLF001
        _finish(renderer)
        doc.close()


def test_process_operator_knockout_restore_runs_before_handler_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _broken_paint(
        _renderer: PDFRenderer,
        _op: Any,
        _operands: list[Any],
    ) -> None:
        calls.append("handler")
        raise TypeError("paint failed")

    doc, renderer = _prepared_renderer()
    original = renderer_module._DISPATCH["f"]  # noqa: SLF001
    try:
        renderer._knockout_active = True  # noqa: SLF001
        renderer._knockout_form_depth = 0  # noqa: SLF001
        monkeypatch.setattr(
            renderer,
            "_restore_knockout_snapshot",
            lambda: calls.append("restore"),
        )
        monkeypatch.setitem(renderer_module._DISPATCH, "f", _broken_paint)  # noqa: SLF001

        renderer.process_operator("f", [])

        assert calls == ["restore", "handler"]
    finally:
        monkeypatch.setitem(renderer_module._DISPATCH, "f", original)  # noqa: SLF001
        _finish(renderer)
        doc.close()


def test_static_matrix_helpers_cover_singular_and_degenerate_scale() -> None:
    assert PDFRenderer._invert_matrix((1.0, 2.0, 2.0, 4.0, 5.0, 6.0)) is None  # noqa: SLF001
    assert PDFRenderer._approx_scale((0.0, 0.0, 0.0, 0.0, 2.0, 3.0)) == 1.0  # noqa: SLF001
    assert PDFRenderer._apply((2.0, 3.0), (2.0, 1.0, 4.0, 3.0, 5.0, 6.0)) == (  # noqa: SLF001
        21.0,
        17.0,
    )


def test_transparency_group_detection_ignores_non_transparency_group_dict() -> None:
    class _Form:
        def get_group(self) -> object:
            return COSName.get_pdf_name("NotADictionary")

    assert PDFRenderer._is_transparency_group(_Form()) is False  # noqa: SLF001
