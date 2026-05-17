from __future__ import annotations

from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName
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


def test_knockout_dispatch_restores_snapshot_only_for_top_level_paint() -> None:
    doc, renderer = _prepared_renderer((2, 2))
    try:
        renderer._knockout_active = True  # noqa: SLF001
        renderer._knockout_snapshot = Image.new("RGB", (2, 2), (10, 20, 30))  # noqa: SLF001

        renderer._image.paste((200, 0, 0), (0, 0, 2, 2))  # noqa: SLF001
        renderer._knockout_form_depth = 0  # noqa: SLF001
        renderer.process_operator("f", [])
        _finish(renderer)
        assert renderer._image.getpixel((0, 0)) == (10, 20, 30)  # noqa: SLF001

        renderer._image.paste((200, 0, 0), (0, 0, 2, 2))  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        renderer._draw.setantialias(True)  # noqa: SLF001
        renderer._knockout_form_depth = 1  # noqa: SLF001
        renderer.process_operator("f", [])
        _finish(renderer)
        assert renderer._image.getpixel((0, 0)) == (200, 0, 0)  # noqa: SLF001
    finally:
        doc.close()


def test_radial_shading_linear_degenerate_case_paints_valid_root() -> None:
    class _Function:
        def eval(self, inputs: list[float]) -> list[float]:
            return [inputs[0], 0.0, 0.0]

    class _Shading:
        def get_coords(self) -> COSArray:
            return _float_array([0.0, 0.0, 0.0, 2.0, 0.0, 2.0])

        def get_domain(self) -> None:
            return None

        def get_extend(self) -> tuple[bool, bool]:
            return (False, False)

        def get_function(self) -> _Function:
            return _Function()

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

    doc, renderer = _prepared_renderer((3, 1))
    try:
        renderer._paint_radial_shading(  # noqa: SLF001
            _Shading(),
            region_mask=Image.new("L", (3, 1), 255),
        )
        _finish(renderer)

        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)  # noqa: SLF001
        assert 60 <= renderer._image.getpixel((1, 0))[0] <= 70  # noqa: SLF001
        assert 120 <= renderer._image.getpixel((2, 0))[0] <= 135  # noqa: SLF001
    finally:
        doc.close()


def test_evaluate_shading_rgb_normalizes_cos_function_then_cmyk() -> None:
    class _Function:
        def eval(self, inputs: list[float]) -> list[float]:
            assert inputs == [0.25]
            return [0.0, 1.0, 0.0, 0.5]

    class _Shading:
        def get_function(self) -> object:
            return object()

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceCMYK")

    doc, renderer = _prepared_renderer()
    try:
        from pypdfbox.pdmodel.common.function import PDFunction

        original_create = PDFunction.create
        PDFunction.create = staticmethod(lambda _obj: _Function())  # type: ignore[method-assign]
        try:
            assert renderer._evaluate_shading_rgb(_Shading(), 0.25) == (0.5, 0.0, 0.5)  # noqa: E501, SLF001
        finally:
            PDFunction.create = original_create  # type: ignore[method-assign]
    finally:
        _finish(renderer)
        doc.close()


def test_paint_with_empty_path_consumes_pending_clip_and_preserves_path() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._pending_clip = "W*"  # noqa: SLF001

        renderer._paint(stroke=True, fill=True, even_odd=True)  # noqa: SLF001

        assert renderer._pending_clip is None  # noqa: SLF001
        assert renderer._subpaths == []  # noqa: SLF001
        assert renderer._current_subpath is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
