from __future__ import annotations

import builtins
from typing import Any

from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _AggdrawPathPen, _GState


def _make_doc(
    width: float = 4.0,
    height: float = 4.0,
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(
    size: tuple[int, int] = (4, 4),
) -> tuple[PDDocument, PDFRenderer]:
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


def _float_array(*values: float) -> COSArray:
    array = COSArray()
    for value in values:
        array.add(COSFloat(value))
    return array


class _RGBFunction:
    def __init__(self, rgb: list[float]) -> None:
        self._rgb = rgb

    def eval(self, _inputs: list[float]) -> list[float]:
        return self._rgb


def test_unknown_shading_type_uses_evaluated_fallback_color() -> None:
    class _UnknownShading:
        def get_function(self) -> _RGBFunction:
            return _RGBFunction([0.0, 1.0, 0.0])

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        renderer._paint_shading(  # noqa: SLF001
            _UnknownShading(),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (0, 255, 0)  # noqa: SLF001
    finally:
        doc.close()


def test_shading_extend_defaults_when_cosboolean_import_fails(
    monkeypatch: Any,
) -> None:
    original_import = builtins.__import__

    def raising_import(
        name: str,
        globals: dict[str, object] | None = None,  # noqa: A002
        locals: dict[str, object] | None = None,  # noqa: A002
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "pypdfbox.cos" and "COSBoolean" in fromlist:
            raise RuntimeError("import failed")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", raising_import)

    class _Shading:
        def get_extend(self) -> object:
            return object()

    assert PDFRenderer._shading_extend(_Shading()) == (False, False)  # noqa: SLF001


def test_hsl_helpers_cover_tie_and_in_gamut_paths() -> None:
    assert PDFRenderer._hsl_clip_color(0.25, 0.5, 0.75) == (  # noqa: SLF001
        0.25,
        0.5,
        0.75,
    )
    assert PDFRenderer._hsl_set_sat(0.8, 0.2, 0.8, 0.4) == (  # noqa: SLF001
        0.4,
        0.0,
        0.4,
    )


def test_aggdraw_path_pen_qcurve_ignores_empty_and_missing_current_point() -> None:
    pen = _AggdrawPathPen(scale=1.0)

    pen.q_curve_to()
    pen.q_curve_to((1.0, 2.0))

    assert pen.has_segments is False
