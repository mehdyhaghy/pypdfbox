from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_doc(width: float = 3.0, height: float = 3.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _prepared_renderer(size: tuple[int, int] = (3, 3)) -> tuple[PDDocument, PDFRenderer]:
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


class _Backdrop:
    def __init__(self, values: list[float] | None, *, broken: bool = False) -> None:
        self._values = values
        self._broken = broken

    def to_float_array(self) -> list[float]:
        if self._broken:
            raise RuntimeError("bad backdrop")
        return [] if self._values is None else self._values


class _SoftMask:
    def __init__(self, backdrop: _Backdrop | None) -> None:
        self._backdrop = backdrop

    def get_backdrop_color(self) -> _Backdrop | None:
        return self._backdrop


def test_soft_mask_backdrop_rgb_defaults_and_color_space_shapes() -> None:
    doc, renderer = _prepared_renderer()
    try:
        assert renderer._soft_mask_backdrop_rgb(_SoftMask(None)) == (0, 0, 0)  # noqa: SLF001
        assert renderer._soft_mask_backdrop_rgb(_SoftMask(_Backdrop(None))) == (0, 0, 0)  # noqa: SLF001
        assert renderer._soft_mask_backdrop_rgb(  # noqa: SLF001
            _SoftMask(_Backdrop([0.5]))
        ) == (128, 128, 128)
        assert renderer._soft_mask_backdrop_rgb(  # noqa: SLF001
            _SoftMask(_Backdrop([1.2, 0.25]))
        ) == (255, 64, 0)
        assert renderer._soft_mask_backdrop_rgb(  # noqa: SLF001
            _SoftMask(_Backdrop([0.0, 1.0, 0.0, 0.5]))
        ) == (128, 0, 128)
        assert renderer._soft_mask_backdrop_rgb(  # noqa: SLF001
            _SoftMask(_Backdrop([1.0], broken=True))
        ) == (0, 0, 0)
    finally:
        _finish(renderer)
        doc.close()


def test_build_transfer_lookup_identity_and_default_names_skip_remap() -> None:
    assert PDFRenderer._build_transfer_lookup(COSName.get_pdf_name("Identity")) is None  # noqa: SLF001
    assert PDFRenderer._build_transfer_lookup(COSName.get_pdf_name("Default")) is None  # noqa: SLF001


def test_decode_inline_image_uses_long_keys_and_ignores_non_name_filter_entries() -> None:
    params = COSDictionary()
    params.set_item(COSName.get_pdf_name("Width"), COSInteger.get(1))
    params.set_item(COSName.get_pdf_name("Height"), COSInteger.get(1))
    params.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    params.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB"))
    filters = COSArray()
    filters.add(COSInteger.get(7))
    params.set_item(COSName.get_pdf_name("Filter"), filters)

    image = PDFRenderer._decode_inline_image(params, b"\x11\x22\x33")  # noqa: SLF001

    assert image is not None
    assert image.mode == "RGB"
    assert image.getpixel((0, 0)) == (17, 34, 51)


def test_decode_inline_image_unknown_filter_name_is_deferred() -> None:
    params = COSDictionary()
    params.set_item(COSName.get_pdf_name("W"), COSInteger.get(1))
    params.set_item(COSName.get_pdf_name("H"), COSInteger.get(1))
    params.set_item(COSName.get_pdf_name("BPC"), COSInteger.get(8))
    params.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("RGB"))
    params.set_item(COSName.get_pdf_name("F"), COSName.get_pdf_name("Fl"))

    assert PDFRenderer._decode_inline_image(params, b"\x11\x22\x33") is None  # noqa: SLF001


def test_show_inline_image_logs_helper_and_legacy_decode_failures(
    caplog: Any,
) -> None:
    class _BrokenInlineImage:
        def to_pil_image(self) -> None:
            raise RuntimeError("helper boom")

        def get_cos_object(self) -> object:
            return object()

        def get_stream(self) -> bytes:
            return b""

    doc, renderer = _prepared_renderer()
    try:
        caplog.set_level("DEBUG", logger="pypdfbox.rendering.pdf_renderer")

        renderer.show_inline_image(_BrokenInlineImage())

        assert "cannot decode inline image (helper): helper boom" in caplog.text
        assert "cannot decode inline image:" in caplog.text
        assert renderer._image.getpixel((1, 1)) == (255, 255, 255)  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()


def test_render_soft_mask_alpha_rejects_untyped_soft_mask() -> None:
    doc, renderer = _prepared_renderer()
    try:
        assert renderer._render_soft_mask_alpha(object(), (2, 2)) is None  # noqa: SLF001
    finally:
        _finish(renderer)
        doc.close()
