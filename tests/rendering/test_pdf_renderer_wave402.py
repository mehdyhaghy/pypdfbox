from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.blend_mode import BlendMode
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import _AggdrawPathPen, _GState


def _make_doc(width: float = 20.0, height: float = 20.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (20, 20)) -> tuple[PDDocument, PDFRenderer]:
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


class _Substitute:
    def __init__(self, width: float | Exception, units: int | Exception | None = None) -> None:
        self._width = width
        self._units = units

    def get_width(self, _glyph_name: str) -> float:
        if isinstance(self._width, Exception):
            raise self._width
        return self._width

    def get_units_per_em(self) -> int:
        if isinstance(self._units, Exception):
            raise self._units
        return 1000 if self._units is None else self._units


def test_paste_image_with_blend_honors_clip_and_alpha() -> None:
    doc, renderer = _prepared_renderer((4, 2))
    try:
        renderer._image.paste((0, 255, 0), (0, 0, 4, 2))  # noqa: SLF001
        source = Image.new("RGB", (2, 2), (255, 0, 0))
        alpha = Image.new("L", (2, 2), 255)
        alpha.putpixel((1, 0), 0)
        clip = Image.new("L", (4, 2), 0)
        clip.paste(255, (0, 0, 2, 2))

        renderer._paste_image_with_blend(  # noqa: SLF001
            source,
            alpha,
            (0, 0, 2, 2),
            clip,
            BlendMode.MULTIPLY,
        )

        assert renderer._image.getpixel((0, 0)) == (0, 0, 0)  # noqa: SLF001
        assert renderer._image.getpixel((1, 0)) == (0, 255, 0)  # noqa: SLF001
        assert renderer._image.getpixel((3, 0)) == (0, 255, 0)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_render_form_xobject_restores_resources_and_renders_stream() -> None:
    class _Form:
        def __init__(self, stream: COSStream, resources: object) -> None:
            self._stream = stream
            self._resources = resources

        def get_matrix(self) -> list[float]:
            return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

        def get_bbox(self) -> PDRectangle:
            return PDRectangle(0.0, 0.0, 6.0, 6.0)

        def get_resources(self) -> object:
            return self._resources

        def get_cos_object(self) -> COSStream:
            return self._stream

    doc, renderer = _prepared_renderer()
    original_resources = object()
    form_resources = object()
    stream = COSStream()
    stream.set_raw_data(b"0 0 1 rg\n0 0 6 6 re\nf\n")
    renderer._resources = original_resources  # noqa: SLF001
    try:
        renderer._render_form_xobject(_Form(stream, form_resources))  # noqa: SLF001
        _finish(renderer)

        assert renderer._resources is original_resources  # noqa: SLF001
        assert len(renderer._gs_stack) == 1  # noqa: SLF001
        assert renderer._image.getpixel((3, 3)) == (0, 0, 255)  # noqa: SLF001
        assert renderer._image.getpixel((8, 8)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_text_metric_helpers_cover_fallback_and_error_branches() -> None:
    class _WidthFont:
        def __init__(self, value: float | Exception) -> None:
            self._value = value

        def get_glyph_width(self, _code: int) -> float:
            if isinstance(self._value, Exception):
                raise self._value
            return self._value

    assert PDFRenderer._font_width_units(_WidthFont(321.0), 65) == 321.0  # noqa: SLF001
    assert PDFRenderer._font_width_units(_WidthFont(RuntimeError("width")), 65) == 500.0  # noqa: E501, SLF001
    assert PDFRenderer._font_width_units(object(), 65) == 500.0  # noqa: SLF001

    assert PDFRenderer._fallback_advance_units(_Substitute(600.0), 65, 500.0) == 600.0  # noqa: E501, SLF001
    assert PDFRenderer._fallback_advance_units(_Substitute(1200.0, 2000), 65, 500.0) == 600.0  # noqa: E501, SLF001
    assert PDFRenderer._fallback_advance_units(_Substitute(RuntimeError("w")), 65, 500.0) == 500.0  # noqa: E501, SLF001
    assert PDFRenderer._fallback_advance_units(_Substitute(0.0), 65, 500.0) == 500.0  # noqa: E501, SLF001
    assert PDFRenderer._fallback_advance_units(_Substitute(600.0), 0, 500.0) == 500.0  # noqa: E501, SLF001


def test_code_to_gid_prefers_font_methods_then_cmap_fallback() -> None:
    class _PrivateWithTypeError:
        def _code_to_gid(self, code: int) -> int:
            return code + 10

    class _PublicRaises:
        def code_to_gid(self, _code: int) -> int:
            raise RuntimeError("gid")

    class _CMap:
        def get_glyph_id(self, code: int) -> int:
            return code + 20

    class _TTF:
        def __init__(self, cmap: Any | None) -> None:
            self._cmap = cmap

        def get_unicode_cmap_subtable(self) -> Any | None:
            return self._cmap

    assert PDFRenderer._code_to_gid(_PrivateWithTypeError(), 5, _TTF(None)) == 15  # noqa: SLF001
    assert PDFRenderer._code_to_gid(_PublicRaises(), 5, _TTF(_CMap())) == 25  # noqa: SLF001
    assert PDFRenderer._code_to_gid(object(), 5, _TTF(None)) == 0  # noqa: SLF001


def test_type1_path_builder_and_aggdraw_pen_quadratic_branches() -> None:
    assert PDFRenderer._build_aggdraw_path_from_commands(  # noqa: SLF001
        [("moveto", 0.0, 0.0)],
        scale=1.0,
    ) is None
    assert PDFRenderer._build_aggdraw_path_from_commands(  # noqa: SLF001
        [
            ("moveto", 0.0, 0.0),
            ("lineto", 10.0, 0.0),
            ("curveto", 10.0, 0.0, 10.0, 10.0, 0.0, 10.0),
            ("closepath",),
        ],
        scale=0.1,
    ) is not None

    pen = _AggdrawPathPen(scale=0.5)
    pen.q_curve_to((1.0, 1.0))
    assert pen.has_segments is False

    pen.move_to((0.0, 0.0))
    pen.q_curve_to()
    pen.q_curve_to((2.0, 0.0))
    pen.q_curve_to((3.0, 1.0), (4.0, 0.0))
    pen.q_curve_to((5.0, 1.0), (6.0, 1.0), (7.0, 0.0))
    pen.curve_to((7.0, 0.0), (8.0, 1.0))
    pen.add_component("base", (1.0, 0.0, 0.0, 1.0, 0.0, 0.0))
    pen.close_path()
    pen.end_path()

    assert pen.has_segments is True
