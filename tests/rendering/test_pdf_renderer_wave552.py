from __future__ import annotations

import io
from typing import Any

import aggdraw  # type: ignore[import-not-found]
from PIL import Image

from pypdfbox.cos import COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


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


def test_do_operator_defensive_resource_paths_log_and_skip(caplog: Any) -> None:
    class _BrokenResources:
        def get_x_object(self, _name: COSName) -> object:
            raise RuntimeError("xobject boom")

    class _MissingResources:
        def get_x_object(self, _name: COSName) -> None:
            return None

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level("DEBUG", logger="pypdfbox.rendering.pdf_renderer")

        renderer._resources = None  # noqa: SLF001
        renderer.process_operator("Do", [COSName.get_pdf_name("Im0")])

        renderer._resources = _MissingResources()  # noqa: SLF001
        renderer.process_operator("Do", [COSName.get_pdf_name("Im0")])

        renderer._resources = _BrokenResources()  # noqa: SLF001
        renderer.process_operator("Do", [COSName.get_pdf_name("Im0")])

        assert "cannot resolve XObject Im0: xobject boom" in caplog.text
        assert renderer._image.getbbox() == (0, 0, 8, 8)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_render_form_xobject_applies_scope_and_restores_scoped_state(
    monkeypatch: Any,
) -> None:
    class _Form:
        def get_matrix(self) -> list[float]:
            return [1.0, 0.0, 0.0, 1.0, 2.0, 3.0]

        def get_bbox(self) -> PDRectangle:
            return PDRectangle(1.0, 1.0, 4.0, 4.0)

        def get_resources(self) -> object:
            return inner_resources

        def get_cos_object(self) -> COSStream:
            stream = COSStream()
            stream.set_raw_data(b"0 0 m\n")
            return stream

    outer_resources = object()
    inner_resources = object()
    doc, renderer = _prepared_renderer()
    original_ctm = (2.0, 0.0, 0.0, 2.0, 5.0, 7.0)
    seen: list[tuple[object | None, tuple[float, ...], bool, bytes]] = []
    try:
        renderer._resources = outer_resources  # noqa: SLF001
        renderer._gs.ctm = original_ctm  # noqa: SLF001
        renderer._subpaths = [[("M", 99.0, 99.0)]]  # noqa: SLF001
        renderer._current_subpath = renderer._subpaths[0]  # noqa: SLF001
        renderer._current_point = (99.0, 99.0)  # noqa: SLF001

        def _process_form_bytes(data: bytes) -> None:
            seen.append(
                (
                    renderer._resources,  # noqa: SLF001
                    renderer._gs.ctm,  # noqa: SLF001
                    renderer._gs.clip_mask is not None,  # noqa: SLF001
                    data,
                )
            )

        monkeypatch.setattr(renderer, "_process_form_bytes", _process_form_bytes)

        renderer._render_form_xobject(_Form())  # noqa: SLF001

        assert seen == [
            (inner_resources, (2.0, 0.0, 0.0, 2.0, 9.0, 13.0), True, b"0 0 m\n")
        ]
        assert renderer._resources is outer_resources  # noqa: SLF001
        assert renderer._gs.ctm == original_ctm  # noqa: SLF001
        assert renderer._subpaths == []  # noqa: SLF001
        assert renderer._current_subpath is None  # noqa: SLF001
        assert renderer._current_point == (1.0, 1.0)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_decode_image_xobject_raw_gray_and_invalid_inputs() -> None:
    class _ImageXObject:
        def __init__(
            self,
            *,
            width: int = 2,
            height: int = 1,
            bpc: int = 8,
            color_space: COSName | None = None,
            data: bytes = b"\x00\xff",
        ) -> None:
            self._stream = COSStream()
            self._width = width
            self._height = height
            self._bpc = bpc
            self._color_space = color_space or COSName.get_pdf_name("DeviceGray")
            self._data = data

        def get_cos_object(self) -> COSStream:
            return self._stream

        def get_width(self) -> int:
            return self._width

        def get_height(self) -> int:
            return self._height

        def get_bits_per_component(self) -> int:
            return self._bpc

        def get_color_space(self) -> COSName | None:
            return self._color_space

        def create_input_stream(self, stop_filters: list[str] | None = None) -> io.BytesIO:
            assert stop_filters is None
            return io.BytesIO(self._data)

    doc, renderer = _prepared_renderer()
    try:
        decoded = renderer._decode_image_xobject(_ImageXObject())  # noqa: SLF001

        assert decoded is not None
        assert decoded.mode == "RGB"
        assert decoded.getpixel((0, 0)) == (0, 0, 0)
        assert decoded.getpixel((1, 0)) == (255, 255, 255)
        assert renderer._decode_image_xobject(_ImageXObject(width=0)) is None  # noqa: SLF001
        assert renderer._decode_image_xobject(_ImageXObject(bpc=4)) is None  # noqa: SLF001
        assert renderer._decode_image_xobject(  # noqa: SLF001
            _ImageXObject(color_space=COSName.get_pdf_name("DeviceCMYK"))
        ) is None
    finally:
        _finish(renderer)
        doc.close()


def test_concat_matrix_and_short_text_positioning_operands_are_noops() -> None:
    doc, renderer = _prepared_renderer()
    try:
        renderer._gs.ctm = (1.0, 0.0, 0.0, 1.0, 5.0, 6.0)  # noqa: SLF001
        renderer._gs.text_matrix = (1.0, 0.0, 0.0, 1.0, 7.0, 8.0)  # noqa: SLF001
        renderer._gs.text_line_matrix = renderer._gs.text_matrix  # noqa: SLF001

        renderer.process_operator("cm", [COSFloat(1.0), COSFloat(0.0)])
        renderer.process_operator("Td", [COSFloat(2.0)])
        renderer.process_operator("TD", [COSFloat(2.0)])
        renderer.process_operator("Tm", [COSFloat(1.0)])

        assert renderer._gs.ctm == (1.0, 0.0, 0.0, 1.0, 5.0, 6.0)  # noqa: SLF001
        assert renderer._gs.text_matrix == (1.0, 0.0, 0.0, 1.0, 7.0, 8.0)  # noqa: SLF001
        assert renderer._gs.text_line_matrix == renderer._gs.text_matrix  # noqa: SLF001

        renderer.process_operator(
            "cm",
            [
                COSFloat(2.0),
                COSFloat(0.0),
                COSFloat(0.0),
                COSFloat(3.0),
                COSFloat(4.0),
                COSFloat(5.0),
            ],
        )

        assert renderer._gs.ctm == (2.0, 0.0, 0.0, 3.0, 9.0, 11.0)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
