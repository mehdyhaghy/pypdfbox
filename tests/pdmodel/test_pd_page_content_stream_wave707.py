from __future__ import annotations

import sys
import types
from collections.abc import Iterator

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def _make_page(doc: PDDocument) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)
    return page


@pytest.fixture
def doc() -> Iterator[PDDocument]:
    document = PDDocument()
    try:
        yield document
    finally:
        document.close()


def _stream_bytes(page: PDPage) -> bytes:
    return page.get_contents()


def test_pd_color_device_gray_emits_colorspace_then_sc(
    doc: PDDocument,
) -> None:
    page = _make_page(doc)
    gray = PDColor([0.25], PDDeviceGray.INSTANCE)

    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color(gray)
        cs.set_non_stroking_color(gray)

    # Mirrors upstream PDAbstractContentStream.setStrokingColor(PDColor):
    # ``/DeviceGray CS 0.25 SC`` (and the non-stroking ``cs``/``sc`` pair),
    # NOT the ``G``/``g`` device shorthand reserved for the float[] overload.
    assert _stream_bytes(page) == b"/DeviceGray CS\n0.25 SC\n/DeviceGray cs\n0.25 sc\n"


def test_draw_image_jpeg_path_uses_jpeg_factory(
    doc: PDDocument,
    tmp_path,
) -> None:
    from PIL import Image

    src = tmp_path / "tile.jpg"
    Image.new("RGB", (3, 2), (10, 20, 30)).save(src, format="JPEG")

    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(src, 1, 2)

    assert _stream_bytes(page) == b"q\n3 0 0 2 1 2 cm\n/Im0 Do\nQ\n"
    xobject = page.get_resources().get_x_object(COSName.get_pdf_name("Im0"))
    filters = [name.get_name() for name in xobject.get_cos_object().get_filter_list()]
    assert filters == ["DCTDecode"]


def test_draw_image_png_bytes_uses_lossless_factory(
    doc: PDDocument,
    tmp_path,
) -> None:
    from PIL import Image

    src = tmp_path / "tile.png"
    Image.new("RGB", (4, 3), (200, 10, 50)).save(src, format="PNG")

    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(src.read_bytes(), 5, 6)

    assert _stream_bytes(page) == b"q\n4 0 0 3 5 6 cm\n/Im0 Do\nQ\n"


def test_draw_image_pillow_image_uses_lossless_factory(
    doc: PDDocument,
) -> None:
    from PIL import Image

    page = _make_page(doc)
    image = Image.new("RGB", (7, 5), (1, 2, 3))

    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(image, 9, 10)

    assert _stream_bytes(page) == b"q\n7 0 0 5 9 10 cm\n/Im0 Do\nQ\n"


def test_draw_image_pillow_image_without_lossless_factory_raises(
    doc: PDDocument,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from PIL import Image

    dummy_lossless = types.ModuleType(
        "pypdfbox.pdmodel.graphics.image.lossless_factory"
    )
    monkeypatch.setitem(
        sys.modules,
        "pypdfbox.pdmodel.graphics.image.lossless_factory",
        dummy_lossless,
    )

    page = _make_page(doc)
    with (
        PDPageContentStream(doc, page) as cs,
        pytest.raises(NotImplementedError, match="LosslessFactory"),
    ):
        cs.draw_image(Image.new("RGB", (1, 1)), 0, 0)
