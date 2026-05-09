from __future__ import annotations

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.cos import COSArray, COSBoolean, COSFloat
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _bezier_point, _GState


def _make_doc(width: float = 6.0, height: float = 6.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (6, 6)) -> tuple[PDDocument, PDFRenderer]:
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


def test_shading_metadata_helpers_use_defaults_for_bad_inputs() -> None:
    class _Missing:
        def get_domain(self) -> None:
            return None

        def get_matrix(self) -> None:
            return None

        def get_extend(self) -> None:
            return None

    class _Raising:
        def get_domain(self) -> None:
            raise RuntimeError("domain")

        def get_matrix(self) -> None:
            raise RuntimeError("matrix")

        def get_extend(self) -> None:
            raise RuntimeError("extend")

    class _BadArray:
        def to_float_array(self) -> list[float]:
            raise RuntimeError("array")

    assert PDFRenderer._shading_domain_2d(_Missing()) == (0.0, 1.0, 0.0, 1.0)  # noqa: SLF001
    assert PDFRenderer._shading_domain_2d(_Raising()) == (0.0, 1.0, 0.0, 1.0)  # noqa: SLF001
    assert PDFRenderer._shading_matrix(_Missing()) == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: E501, SLF001
    assert PDFRenderer._shading_matrix(_Raising()) == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: E501, SLF001
    assert PDFRenderer._shading_domain(_Missing()) == (0.0, 1.0)  # noqa: SLF001
    assert PDFRenderer._shading_domain(_Raising()) == (0.0, 1.0)  # noqa: SLF001
    assert PDFRenderer._shading_extend(_Missing()) == (False, False)  # noqa: SLF001
    assert PDFRenderer._shading_extend(_Raising()) == (False, False)  # noqa: SLF001

    class _BadDomain:
        def get_domain(self) -> _BadArray:
            return _BadArray()

    class _BadMatrix:
        def get_matrix(self) -> _BadArray:
            return _BadArray()

    assert PDFRenderer._shading_domain_2d(_BadDomain()) == (0.0, 1.0, 0.0, 1.0)  # noqa: E501, SLF001
    assert PDFRenderer._shading_matrix(_BadMatrix()) == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: E501, SLF001


def test_shading_metadata_helpers_parse_arrays_and_tuple_extend() -> None:
    class _Shading:
        def get_domain(self) -> COSArray:
            return _float_array([2.0, 4.0, 6.0, 8.0])

        def get_matrix(self) -> COSArray:
            return _float_array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])

        def get_extend(self) -> tuple[bool, bool]:
            return (True, False)

    assert PDFRenderer._shading_domain_2d(_Shading()) == (2.0, 4.0, 6.0, 8.0)  # noqa: SLF001
    assert PDFRenderer._shading_domain(_Shading()) == (2.0, 4.0)  # noqa: SLF001
    assert PDFRenderer._shading_matrix(_Shading()) == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)  # noqa: E501, SLF001
    assert PDFRenderer._shading_extend(_Shading()) == (True, False)  # noqa: SLF001

    class _COSArrayExtend:
        def get_extend(self) -> COSArray:
            array = COSArray()
            array.add(COSBoolean.FALSE)
            array.add(COSBoolean.TRUE)
            return array

    assert PDFRenderer._shading_extend(_COSArrayExtend()) == (False, True)  # noqa: SLF001


def test_function_output_matrix_and_bezier_helpers_cover_edge_values() -> None:
    assert PDFRenderer._function_output_to_rgb([], None) == (0, 0, 0)  # noqa: SLF001
    assert PDFRenderer._function_output_to_rgb([0.5], "DeviceGray") == (128, 128, 128)  # noqa: E501, SLF001
    assert PDFRenderer._function_output_to_rgb([0.0, 1.0, 0.0, 0.5], "DeviceCMYK") == (128, 0, 128)  # noqa: E501, SLF001
    assert PDFRenderer._function_output_to_rgb([1.0, 0.5], None) == (255, 128, 0)  # noqa: E501, SLF001

    assert PDFRenderer._invert_matrix((1.0, 0.0, 0.0, 0.0, 2.0, 3.0)) is None  # noqa: E501, SLF001
    inv = PDFRenderer._invert_matrix((2.0, 0.0, 0.0, 4.0, 10.0, 20.0))  # noqa: SLF001
    assert inv == (0.5, -0.0, -0.0, 0.25, -5.0, -5.0)
    assert PDFRenderer._apply((2.0, 3.0), (2.0, 0.0, 1.0, 2.0, 5.0, 7.0)) == (12.0, 13.0)  # noqa: E501, SLF001
    assert PDFRenderer._approx_scale((2.0, 0.0, 0.0, 8.0, 0.0, 0.0)) == 4.0  # noqa: SLF001
    assert PDFRenderer._approx_scale((0.0, 0.0, 0.0, 0.0, 0.0, 0.0)) == 1.0  # noqa: SLF001
    assert _bezier_point(0.0, 0.0, 0.0, 6.0, 6.0, 6.0, 6.0, 0.0, 0.5) == (3.0, 4.5)  # noqa: E501


def test_paste_image_with_alpha_and_clip_uses_combined_mask() -> None:
    doc, renderer = _prepared_renderer()
    try:
        source = Image.new("RGBA", (2, 2), (255, 0, 0, 255))
        source.putpixel((0, 1), (255, 0, 0, 0))
        clip = Image.new("L", (6, 6), 0)
        clip.paste(255, (1, 1, 2, 3))

        renderer._gs.ctm = (2.0, 0.0, 0.0, 2.0, 1.0, 1.0)  # noqa: SLF001
        renderer._gs.clip_mask = clip  # noqa: SLF001
        renderer._paste_image(source)  # noqa: SLF001
        _finish(renderer)

        assert renderer._image.getpixel((1, 1)) == (255, 255, 255)  # noqa: SLF001
        assert renderer._image.getpixel((1, 2)) == (255, 0, 0)  # noqa: SLF001
        assert renderer._image.getpixel((2, 2)) == (255, 255, 255)  # noqa: SLF001
        assert renderer._draw is not None  # noqa: SLF001
    finally:
        doc.close()
