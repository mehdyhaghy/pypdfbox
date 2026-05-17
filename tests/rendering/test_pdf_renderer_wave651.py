from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSFloat, COSInteger, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState, _to_float


def _make_doc(
    width: float = 6.0,
    height: float = 6.0,
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(
    size: tuple[int, int] = (6, 6),
) -> tuple[PDDocument, PDFRenderer]:
    doc, _page = _make_doc(float(size[0]), float(size[1]))
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", size, (255, 255, 255))  # noqa: SLF001
    renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
    renderer._draw.setantialias(True)  # noqa: SLF001
    renderer._gs_stack = [_GState(fill_rgb=(255, 0, 0))]  # noqa: SLF001
    renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001
    return doc, renderer


def _finish(renderer: PDFRenderer) -> None:
    draw = renderer._draw  # noqa: SLF001
    if draw is not None:
        draw.flush()


class _Box:
    def __init__(self, width: float = 2.0, height: float = 2.0) -> None:
        self._width = width
        self._height = height

    def get_width(self) -> float:
        return self._width

    def get_height(self) -> float:
        return self._height

    def get_lower_left_x(self) -> float:
        return 0.0

    def get_lower_left_y(self) -> float:
        return 0.0


class _TilingPattern:
    def __init__(self, stream: COSStream | None = None) -> None:
        self._stream = stream

    def get_b_box(self) -> _Box:
        return _Box()

    def get_x_step(self) -> float:
        return 2.0

    def get_y_step(self) -> float:
        return 2.0

    def get_cos_object(self) -> COSStream | None:
        return self._stream

    def get_resources(self) -> Any:
        raise RuntimeError("pattern resources unavailable")


def test_to_float_accepts_explicit_cos_number_subclasses() -> None:
    assert _to_float(COSInteger(7)) == 7.0
    assert _to_float(COSFloat(1.25)) == 1.25


def test_gs_operator_ignores_missing_operand_without_state_change() -> None:
    doc, _page = _make_doc()
    renderer = PDFRenderer(doc)
    renderer._gs_stack = [_GState(stroke_alpha=0.4, fill_alpha=0.6)]  # noqa: SLF001
    try:
        renderer.process_operator("gs", [])

        assert renderer._gs.stroke_alpha == 0.4  # noqa: SLF001
        assert renderer._gs.fill_alpha == 0.6  # noqa: SLF001
        assert renderer._gs.blend_mode is None  # noqa: SLF001
    finally:
        doc.close()


def test_even_odd_fill_skips_degenerate_subpath_and_paints_polygon() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._subpaths = [  # noqa: SLF001
            [("M", 0.0, 0.0), ("L", 5.0, 0.0)],
            [("M", 1.0, 1.0), ("L", 5.0, 1.0), ("L", 1.0, 5.0), ("Z",)],
        ]

        renderer._fill_even_odd_via_pil()  # noqa: SLF001

        _finish(renderer)
        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((2, 2)) == (255, 0, 0)  # noqa: SLF001
        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_tiling_pattern_noops_without_mask_or_rendered_tile(
    monkeypatch: Any,
) -> None:
    doc, renderer = _prepared_renderer()
    try:
        pattern = _TilingPattern()

        renderer._paint_tiling_pattern(pattern, region_mask=None)  # noqa: SLF001

        mask = Image.new("L", (6, 6), 255)
        monkeypatch.setattr(renderer, "_render_tiling_cell", lambda *_, **__: None)
        renderer._paint_tiling_pattern(pattern, region_mask=mask)  # noqa: SLF001

        _finish(renderer)
        assert renderer._image is not None  # noqa: SLF001
        assert renderer._image.getpixel((3, 3)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_tiling_cell_restores_outer_state_when_resources_fail(
    monkeypatch: Any,
) -> None:
    doc, renderer = _prepared_renderer()
    try:
        stream = COSStream()
        stream.set_raw_data(b"0 0 1 1 re f\n")
        pattern = _TilingPattern(stream)
        seen: list[bytes] = []
        outer_image = renderer._image  # noqa: SLF001

        monkeypatch.setattr(
            renderer,
            "_process_form_bytes",
            lambda data: seen.append(data),
        )

        tile = renderer._render_tiling_cell(  # noqa: SLF001
            pattern,
            bbox=_Box(),
            tile_size=(3, 4),
        )

        assert tile is not None
        assert tile.size == (3, 4)
        assert seen == [b"0 0 1 1 re f\n"]
        assert renderer._image is outer_image  # noqa: SLF001
        assert renderer._resources is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
