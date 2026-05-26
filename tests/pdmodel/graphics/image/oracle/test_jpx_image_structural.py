"""Structural parity for ``/JPXDecode`` (JPEG 2000) image XObjects.

NOT a live-oracle test — and deliberately so. PDFBox routes JPEG 2000 decode
through ``javax.imageio``, which needs a registered JPEG2000 ``ImageReader``
plugin (JAI Image I/O Tools / openjpeg). The pinned standalone
``pdfbox-app-3.0.7.jar`` bundles **no such reader**: a capability probe against
it reported ``readers 0`` and ``PDImageXObject.getImage()`` threw
``MissingImageReaderException`` ("Java Advanced Imaging (JAI) Image I/O Tools
are not installed"). So the live differential oracle physically cannot decode a
JPX raster with the bundled jar, and there is nothing to compare a pypdfbox
raster against. Rather than fake an oracle baseline, this module exercises the
pypdfbox image-XObject decode path on its own and asserts the structural
invariants the oracle *would* have checked (intrinsic dims, bits-per-component,
colorspace name, successful raster decode).

pypdfbox decodes JPX via ``imagecodecs``/Pillow's OpenJPEG bridge (library-first
per project guidelines), which the standalone PDFBox jar lacks — so on this
surface pypdfbox is strictly *more* capable than the bundled oracle, not
divergent. The filter-level byte behaviour (component count, bpc, endian, the
post-decode ``/Decode``-entry handling) is covered exhaustively in
``tests/filter/test_jpx_decode.py``; this module covers the higher-level
``PDImageXObject.get_image()`` integration that the CCITT oracle test covers for
its surface.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources


def _raster(mode: str, width: int, height: int) -> Image.Image:
    """A deterministic gradient raster in the requested Pillow mode."""
    img = Image.new(mode, (width, height))
    for y in range(height):
        for x in range(width):
            if mode == "L":
                img.putpixel((x, y), (x * 10) % 256)
            elif mode == "RGB":
                img.putpixel((x, y), ((x * 8) % 256, (y * 16) % 256, ((x + y) * 4) % 256))
            elif mode == "CMYK":
                img.putpixel(
                    (x, y), ((x * 8) % 256, (y * 16) % 256, ((x + y) * 4) % 256, 0)
                )
    return img


def _build_jpx_pdf(raster: Image.Image, colorspace: str) -> bytes:
    """Build a one-page PDF whose only image is ``raster`` JPEG-2000-encoded
    under ``/JPXDecode`` with the given device ``/ColorSpace``."""
    width, height = raster.size
    buf = io.BytesIO()
    raster.save(buf, format="JPEG2000")
    jp2 = buf.getvalue()

    document = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    document.add_page(page)
    cos_doc = document.get_document()

    stream = COSStream(cos_doc.scratch_file)
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Image"))
    stream.set_int(COSName.get_pdf_name("Width"), width)
    stream.set_int(COSName.get_pdf_name("Height"), height)
    stream.set_int(COSName.get_pdf_name("BitsPerComponent"), 8)
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name(colorspace)
    )
    stream.set_item(COSName.FILTER, COSName.get_pdf_name("JPXDecode"))
    stream.set_int(COSName.get_pdf_name("Length"), len(jp2))
    stream.set_raw_data(jp2)

    image = PDImageXObject(stream)
    resources = PDResources()
    name = resources.add_x_object(image)
    page.set_resources(resources)

    content = (
        f"q {width} 0 0 {height} 10 10 cm /{name.get_name()} Do Q"
    ).encode("ascii")
    content_stream = COSStream(cos_doc.scratch_file)
    with content_stream.create_output_stream() as out:
        out.write(content)
    page.get_cos_object().set_item(
        COSName.get_pdf_name("Contents"), content_stream
    )

    out_buf = io.BytesIO()
    document.save(out_buf)
    document.close()
    return out_buf.getvalue()


def _decode_first_image(pdf_bytes: bytes):
    """Round-trip-load ``pdf_bytes`` and decode its first image XObject."""
    document = PDDocument.load(pdf_bytes)
    try:
        page = document.get_page(0)
        resources = page.get_resources()
        names = list(resources.get_x_object_names())
        assert names, "fixture PDF has no image XObject"
        image = resources.get_x_object(names[0])
        cs = image.get_color_space()
        cs_name = cs.get_name() if cs is not None else "null"
        pil = image.get_image()
        return (
            image.get_width(),
            image.get_height(),
            image.get_bits_per_component(),
            cs_name,
            pil,
        )
    finally:
        document.close()


@pytest.mark.parametrize(
    ("mode", "colorspace"),
    [
        ("L", "DeviceGray"),
        ("RGB", "DeviceRGB"),
        ("CMYK", "DeviceCMYK"),
    ],
    ids=["gray", "rgb", "cmyk"],
)
def test_jpx_image_xobject_decodes_structurally(mode: str, colorspace: str) -> None:
    """``PDImageXObject.get_image()`` over a ``/JPXDecode`` stream resolves the
    intrinsic geometry and decodes a non-empty raster for every device
    colorspace the PDF image model can express."""
    width, height = 24, 12
    pdf = _build_jpx_pdf(_raster(mode, width, height), colorspace)
    w, h, bpc, cs, pil = _decode_first_image(pdf)

    assert (w, h) == (width, height)
    assert bpc == 8
    assert cs == colorspace
    assert pil is not None
    assert pil.size == (width, height)
    # get_image() always hands back something convertible to RGB pixels.
    assert pil.convert("RGB").size == (width, height)


def test_jpx_image_xobject_suffix_is_jpx() -> None:
    """A ``/JPXDecode`` image reports the ``jpx`` suffix (the extension the
    image-extraction tools key on)."""
    pdf = _build_jpx_pdf(_raster("RGB", 16, 16), "DeviceRGB")
    document = PDDocument.load(pdf)
    try:
        resources = document.get_page(0).get_resources()
        image = resources.get_x_object(list(resources.get_x_object_names())[0])
        assert image.get_suffix() == "jpx"
    finally:
        document.close()
