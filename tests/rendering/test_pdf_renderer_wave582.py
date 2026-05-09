from __future__ import annotations

from typing import Any

import aggdraw  # type: ignore[import-not-found]
import pytest
from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(width: float = 5.0, height: float = 5.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (5, 5)) -> tuple[PDDocument, PDFRenderer]:
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


def test_render_tiling_cell_restores_renderer_state_when_processing_fails(
    monkeypatch: Any,
) -> None:
    class _BBox:
        def get_width(self) -> float:
            return 2.0

        def get_height(self) -> float:
            return 3.0

        def get_lower_left_x(self) -> float:
            return 4.0

        def get_lower_left_y(self) -> float:
            return 5.0

    class _Pattern:
        def get_cos_object(self) -> COSStream:
            stream = COSStream()
            stream.set_raw_data(b"1 2 m\n")
            return stream

        def get_resources(self) -> object:
            return pattern_resources

    doc, renderer = _prepared_renderer()
    pattern_resources = object()
    previous_resources = object()
    previous_image = renderer._image  # noqa: SLF001
    previous_draw = renderer._draw  # noqa: SLF001
    previous_stack = renderer._gs_stack  # noqa: SLF001
    previous_subpaths = [[("M", 9.0, 9.0)]]
    try:
        renderer._resources = previous_resources  # noqa: SLF001
        renderer._subpaths = previous_subpaths  # noqa: SLF001
        renderer._current_subpath = previous_subpaths[0]  # noqa: SLF001
        renderer._current_point = (9.0, 9.0)  # noqa: SLF001
        renderer._pending_clip = "W*"  # noqa: SLF001
        renderer._page_height_px = 5.0  # noqa: SLF001

        def _raise(_data: bytes) -> None:
            assert renderer._resources is pattern_resources  # noqa: SLF001
            assert renderer._image is not previous_image  # noqa: SLF001
            raise RuntimeError("cell boom")

        monkeypatch.setattr(renderer, "_process_form_bytes", _raise)

        with pytest.raises(RuntimeError, match="cell boom"):
            renderer._render_tiling_cell(  # noqa: SLF001
                _Pattern(),
                bbox=_BBox(),
                tile_size=(2, 2),
            )

        assert renderer._image is previous_image  # noqa: SLF001
        assert renderer._draw is previous_draw  # noqa: SLF001
        assert renderer._resources is previous_resources  # noqa: SLF001
        assert renderer._gs_stack is previous_stack  # noqa: SLF001
        assert renderer._subpaths is previous_subpaths  # noqa: SLF001
        assert renderer._current_subpath is previous_subpaths[0]  # noqa: SLF001
        assert renderer._current_point == (9.0, 9.0)  # noqa: SLF001
        assert renderer._pending_clip == "W*"  # noqa: SLF001
        assert renderer._page_height_px == 5.0  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_shading_domain_helpers_default_on_malformed_arrays() -> None:
    class _ShortDomain:
        def get_domain(self) -> COSArray:
            return COSArray([COSFloat(2.0)])

        def get_extend(self) -> COSArray:
            return COSArray([COSFloat(1.0)])

        def get_matrix(self) -> COSArray:
            return COSArray([COSFloat(1.0), COSFloat(2.0)])

    shading = _ShortDomain()

    assert PDFRenderer._shading_domain(shading) == (0.0, 1.0)  # noqa: SLF001
    assert PDFRenderer._shading_domain_2d(shading) == (0.0, 1.0, 0.0, 1.0)  # noqa: SLF001
    assert PDFRenderer._shading_extend(shading) == (False, False)  # noqa: SLF001
    assert PDFRenderer._shading_matrix(shading) == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001,E501


def test_paste_image_with_blend_uses_source_alpha_without_clip() -> None:
    class _Multiply:
        name = "Multiply"

        def is_separable(self) -> bool:
            return True

    doc, renderer = _prepared_renderer((3, 3))
    try:
        renderer._image.paste((200, 200, 200), (0, 0, 3, 3))  # noqa: SLF001
        source = Image.new("RGB", (1, 1), (100, 100, 100))
        alpha = Image.new("L", (1, 1), 0)
        alpha.putpixel((0, 0), 255)

        renderer._paste_image_with_blend(  # noqa: SLF001
            source,
            alpha,
            (1, 1, 1, 1),
            None,
            _Multiply(),
        )

        assert renderer._image.getpixel((0, 0)) == (200, 200, 200)  # noqa: SLF001
        assert renderer._image.getpixel((1, 1)) == (78, 78, 78)  # noqa: SLF001
        assert renderer._image.getpixel((2, 2)) == (200, 200, 200)  # noqa: SLF001
    finally:
        doc.close()
