from __future__ import annotations

from PIL import Image

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.rendering import PDFRenderer


def _make_doc(width: float = 100.0, height: float = 100.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _float_array(values: list[float]) -> COSArray:
    array = COSArray()
    for value in values:
        array.add(COSFloat(float(value)))
    return array


def _separation_to_magenta_color_space() -> COSArray:
    tint = COSStream()
    tint.set_int("FunctionType", 4)
    tint.set_item("Domain", _float_array([0.0, 1.0]))
    tint.set_item(
        "Range",
        _float_array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]),
    )
    tint.set_data(b"{ 0 exch 0 0 }")

    color_space = COSArray()
    color_space.add(COSName.get_pdf_name("Separation"))
    color_space.add(COSName.get_pdf_name("SpotMagenta"))
    color_space.add(COSName.get_pdf_name("DeviceCMYK"))
    color_space.add(tint)
    return color_space


def test_raw_separation_image_xobject_renders_via_image_helper() -> None:
    doc, page = _make_doc()
    try:
        stream = COSStream()
        stream.set_raw_data(bytes([255]))
        image = PDImageXObject(stream)
        image.set_width(1)
        image.set_height(1)
        image.set_bits_per_component(8)
        stream.set_item("ColorSpace", _separation_to_magenta_color_space())

        with PDPageContentStream(doc, page) as contents:
            contents.draw_image(image, x=30.0, y=30.0, width=40.0, height=40.0)

        rendered = PDFRenderer(doc).render_image(0)
        assert rendered.getpixel((50, 50)) == (255, 0, 255)
        assert rendered.getpixel((10, 10)) == (255, 255, 255)

        decoded = image.to_pil_image()
        assert isinstance(decoded, Image.Image)
    finally:
        doc.close()
