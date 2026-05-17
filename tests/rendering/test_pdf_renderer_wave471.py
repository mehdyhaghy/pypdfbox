from __future__ import annotations

import logging
from typing import Any

from PIL import Image

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import _GState


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


def _float_array(values: list[float]) -> COSArray:
    array = COSArray()
    for value in values:
        array.add(COSFloat(value))
    return array


def test_axial_shading_leaves_unextended_pixels_white() -> None:
    class _Function:
        def eval(self, inputs: list[float]) -> list[float]:
            return [inputs[0], 0.0, 0.0]

    class _Shading:
        def get_coords(self) -> COSArray:
            return _float_array([1.0, 0.0, 3.0, 0.0])

        def get_domain(self) -> None:
            return None

        def get_extend(self) -> tuple[bool, bool]:
            return (False, False)

        def get_function(self) -> _Function:
            return _Function()

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    doc, renderer = _prepared_renderer((5, 1))
    try:
        renderer._paint_axial_shading(  # noqa: SLF001
            _Shading(),
            region_mask=Image.new("L", (5, 1), 255),
        )
        _finish(renderer)

        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)  # noqa: SLF001
        assert renderer._image.getpixel((4, 0)) == (255, 255, 255)  # noqa: SLF001
        assert renderer._image.getpixel((1, 0)) == (0, 0, 0)  # noqa: SLF001
        assert renderer._image.getpixel((3, 0)) == (255, 0, 0)  # noqa: SLF001
    finally:
        doc.close()


def test_function_shading_logs_singular_matrix_and_missing_function(
    caplog: Any,
) -> None:
    class _SingularMatrixShading:
        def get_domain(self) -> COSArray:
            return _float_array([0.0, 1.0, 0.0, 1.0])

        def get_matrix(self) -> COSArray:
            return _float_array([1.0, 2.0, 2.0, 4.0, 0.0, 0.0])

    class _MissingFunctionShading:
        def get_domain(self) -> COSArray:
            return _float_array([0.0, 1.0, 0.0, 1.0])

        def get_matrix(self) -> None:
            return None

        def get_function(self) -> None:
            return None

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        mask = Image.new("L", (8, 8), 255)

        renderer._paint_function_shading(  # noqa: SLF001
            _SingularMatrixShading(),
            region_mask=mask,
        )
        renderer._paint_function_shading(  # noqa: SLF001
            _MissingFunctionShading(),
            region_mask=mask,
        )

        assert "PDShadingType1 /Matrix is singular" in caplog.text
        assert "PDShadingType1 missing /Function" in caplog.text
    finally:
        _finish(renderer)
        doc.close()


def test_transparency_group_logs_color_space_and_restores_after_smask_failure(
    caplog: Any,
    monkeypatch: Any,
) -> None:
    class _Form:
        def get_group(self) -> COSDictionary:
            group = COSDictionary()
            group.set_item(COSName.get_pdf_name("I"), COSBoolean.TRUE)
            group.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceCMYK"))
            return group

    def _paint_group(_form: Any) -> None:
        assert renderer._image is not None  # noqa: SLF001
        renderer._image.paste((20, 40, 60, 255), (0, 0, 2, 2))  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        renderer._draw.setantialias(True)  # noqa: SLF001

    def _raise_mask(_soft_mask: Any, _size: tuple[int, int]) -> None:
        raise RuntimeError("mask boom")

    doc, renderer = _prepared_renderer((3, 3))
    renderer._gs.soft_mask = object()  # noqa: SLF001
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        parent_image = renderer._image  # noqa: SLF001
        parent_draw = renderer._draw  # noqa: SLF001
        monkeypatch.setattr(renderer, "_render_form_xobject", _paint_group)
        monkeypatch.setattr(renderer, "_render_soft_mask_alpha", _raise_mask)

        renderer._render_transparency_group(_Form())  # noqa: SLF001
        _finish(renderer)

        assert "transparency group /CS=DeviceCMYK" in caplog.text
        assert "soft-mask render failed: mask boom" in caplog.text
        assert renderer._image is parent_image  # noqa: SLF001
        assert renderer._draw is not parent_draw  # noqa: SLF001
        assert renderer._image.getpixel((1, 1)) == (20, 40, 60)  # noqa: SLF001
        assert renderer._image.getpixel((2, 2)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()
