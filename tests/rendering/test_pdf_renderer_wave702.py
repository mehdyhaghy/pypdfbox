from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSArray, COSFloat
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


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


class _Coords:
    def __init__(self, *values: float) -> None:
        self._values = values

    def size(self) -> int:
        return len(self._values)

    def get_object(self, index: int) -> COSFloat:
        return COSFloat(self._values[index])


class _RGBFunction:
    def eval(self, _inputs: list[float]) -> list[float]:
        return [1.0, 0.0, 0.0]


def test_radial_shading_degenerate_cone_paints_start_colour() -> None:
    # Wave 1484: |c1-c0| == |r1-r0| makes upstream's quadratic denominator 0;
    # Java float division yields +/-Inf/NaN roots and ``(int)(NaN*factor)==0``
    # selects the start colour (RadialShadingContext.calculateInputValues).
    # The old pypdfbox heuristic rejected the root and left the pixel white —
    # this test used to pin that divergent behaviour.
    class _Radial:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 1.0, 1.0, 0.0, 2.0)

        def get_domain(self) -> COSArray:
            return _float_array(0.0, 1.0)

        def get_extend(self) -> tuple[bool, bool]:
            return (False, True)

        def get_function(self) -> _RGBFunction:
            return _RGBFunction()

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, 2.0, 0.0)  # noqa: SLF001

        renderer._paint_radial_shading(  # noqa: SLF001
            _Radial(),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 0, 0)  # noqa: SLF001
    finally:
        doc.close()


def test_radial_shading_equal_domain_uses_first_ramp_entry() -> None:
    class _Radial:
        def get_coords(self) -> _Coords:
            return _Coords(0.0, 0.0, 1.0, 1.0, 0.0, 2.0)

        def get_domain(self) -> COSArray:
            return _float_array(0.5, 0.5)

        def get_extend(self) -> tuple[bool, bool]:
            return (True, True)

        def get_function(self) -> _RGBFunction:
            return _RGBFunction()

    doc, renderer = _prepared_renderer(size=(1, 1))
    try:
        renderer._paint_radial_shading(  # noqa: SLF001
            _Radial(),
            region_mask=Image.new("L", (1, 1), 255),
        )
        _finish(renderer)

        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 0, 0)  # noqa: SLF001
    finally:
        doc.close()


def test_hsl_clip_color_degenerate_low_and_high_denominators() -> None:
    assert PDFRenderer._hsl_clip_color(-0.25, -0.25, -0.25) == (  # noqa: SLF001
        0.0,
        0.0,
        0.0,
    )
    assert PDFRenderer._hsl_clip_color(1.25, 1.25, 1.25) == (  # noqa: SLF001
        1.0,
        1.0,
        1.0,
    )


def test_resolve_font_program_ignores_type1_probe_failure(
    monkeypatch: Any,
) -> None:
    doc, renderer = _prepared_renderer()
    try:
        monkeypatch.setattr(
            renderer,
            "_get_ttf_glyph_set",
            lambda _font: (None, None),
        )

        def raise_type1(_font: PDType1Font) -> object:
            raise RuntimeError("type1 probe failed")

        monkeypatch.setattr(PDType1Font, "_get_type1_font", raise_type1)

        font = PDType1Font()
        resolved = renderer._resolve_font_program(font)  # noqa: SLF001

        assert renderer._font_program_cache[id(font)] is resolved  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
