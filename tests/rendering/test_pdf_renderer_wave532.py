from __future__ import annotations

import io
import logging
from typing import Any

from PIL import Image

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


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


def _png_payload(color: tuple[int, int, int]) -> bytes:
    payload = io.BytesIO()
    Image.new("RGB", (1, 1), color).save(payload, format="PNG")
    return payload.getvalue()


def test_decode_image_xobject_jpx_path_uses_encoded_stream_payload() -> None:
    class _ImageXObject:
        def __init__(self, payload: bytes) -> None:
            self._stream = COSStream()
            self._stream.set_item(COSName.FILTER, COSName.get_pdf_name("JPXDecode"))
            self._payload = payload
            self.stop_filters: list[list[str]] = []

        def get_cos_object(self) -> COSStream:
            return self._stream

        def get_width(self) -> int:
            return 1

        def get_height(self) -> int:
            return 1

        def get_bits_per_component(self) -> int:
            return 8

        def get_color_space(self) -> COSName:
            return COSName.get_pdf_name("DeviceRGB")

        def create_input_stream(self, stop_filters: list[str] | None = None) -> io.BytesIO:
            self.stop_filters.append(list(stop_filters or []))
            return io.BytesIO(self._payload)

    doc, renderer = _prepared_renderer()
    image = _ImageXObject(_png_payload((12, 34, 56)))
    try:
        decoded = renderer._decode_image_xobject(image)  # noqa: SLF001

        assert decoded is not None
        assert decoded.mode == "RGB"
        assert decoded.getpixel((0, 0)) == (12, 34, 56)
        assert image.stop_filters == [["JPXDecode"]]
    finally:
        _finish(renderer)
        doc.close()


def test_decode_inline_image_jpx_filter_opens_encoded_payload() -> None:
    params = COSDictionary()
    params.set_item(COSName.get_pdf_name("Width"), COSInteger.get(1))
    params.set_item(COSName.get_pdf_name("Height"), COSInteger.get(1))
    params.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    params.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("RGB"))
    params.set_item(COSName.get_pdf_name("Filter"), COSName.get_pdf_name("JPXDecode"))

    decoded = PDFRenderer._decode_inline_image(  # noqa: SLF001
        params,
        _png_payload((90, 80, 70)),
    )

    assert decoded is not None
    assert decoded.mode == "RGB"
    assert decoded.getpixel((0, 0)) == (90, 80, 70)


def test_shading_fill_unknown_type_defaults_region_to_existing_clip(
    monkeypatch: Any,
) -> None:
    class _UnknownShading:
        pass

    doc, renderer = _prepared_renderer((4, 4))
    clip = Image.new("L", (4, 4), 0)
    clip.paste(255, (1, 1, 3, 3))
    try:
        renderer._gs.clip_mask = clip  # noqa: SLF001
        monkeypatch.setattr(
            renderer,
            "_evaluate_shading_rgb",
            lambda _shading, _t: (0.0, 0.0, 1.0),
        )

        renderer._paint_shading(_UnknownShading(), region_mask=None)  # noqa: SLF001
        _finish(renderer)

        assert renderer._image.getpixel((0, 0)) == (255, 255, 255)  # noqa: SLF001
        assert renderer._image.getpixel((1, 1)) == (0, 0, 255)  # noqa: SLF001
        assert renderer._image.getpixel((3, 3)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()


def test_tiling_pattern_missing_bbox_or_step_logs_and_skips(
    caplog: Any,
    monkeypatch: Any,
) -> None:
    class _Pattern:
        def get_b_box(self) -> None:
            return None

        def get_x_step(self) -> float:
            return 1.0

        def get_y_step(self) -> float:
            return 1.0

    doc, renderer = _prepared_renderer((2, 2))
    calls: list[object] = []
    try:
        caplog.set_level(logging.DEBUG, logger="pypdfbox.rendering.pdf_renderer")
        monkeypatch.setattr(
            renderer,
            "_render_tiling_cell",
            lambda *args, **kwargs: calls.append((args, kwargs)),
        )

        renderer._paint_tiling_pattern(  # noqa: SLF001
            _Pattern(),
            region_mask=Image.new("L", (2, 2), 255),
        )
        _finish(renderer)

        # The _Pattern stub returns get_b_box()->None, so the missing-/BBox
        # skip path fires. (Wave 1563 split the old combined "/BBox or
        # /XStep/YStep" message: a zero /XStep / /YStep no longer skips — it
        # now falls back to the /BBox dimensions, matching PDFBox's
        # TilingPaint.getAnchorRect; only a missing /BBox skips here.)
        assert "tiling pattern missing /BBox" in caplog.text
        assert calls == []
        assert renderer._image.getpixel((1, 1)) == (255, 255, 255)  # noqa: SLF001
    finally:
        doc.close()
