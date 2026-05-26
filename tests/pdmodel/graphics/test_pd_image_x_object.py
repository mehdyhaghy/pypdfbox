from __future__ import annotations

import io
import zlib

from PIL import Image

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSStream, COSString
from pypdfbox.pdmodel.graphics.color import PDDeviceGray, PDDeviceRGB, PDIndexed
from pypdfbox.pdmodel.graphics.image import PDImageXObject


def test_image_xobject_sets_subtype_and_metadata() -> None:
    image = PDImageXObject(COSStream())
    image.set_width(640)
    image.set_height(480)
    image.set_bits_per_component(8)
    image.set_color_space("DeviceRGB")

    cos = image.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "XObject"  # type: ignore[attr-defined]
    assert cos.get_name(COSName.SUBTYPE) == "Image"  # type: ignore[attr-defined]
    assert image.get_width() == 640
    assert image.get_height() == 480
    assert image.get_bits_per_component() == 8
    assert image.get_color_space() is PDDeviceRGB.INSTANCE
    assert image.get_color_space_cos_object() == COSName.get_pdf_name("DeviceRGB")


def test_image_xobject_accepts_short_metadata_aliases() -> None:
    stream = COSStream()
    stream.set_int(COSName.get_pdf_name("BPC"), 1)
    stream.set_item(COSName.get_pdf_name("CS"), COSName.get_pdf_name("DeviceGray"))

    image = PDImageXObject(stream)
    assert image.get_bits_per_component() == 1
    assert image.get_color_space() is PDDeviceGray.INSTANCE
    assert image.get_color_space_cos_object() == COSName.get_pdf_name("DeviceGray")


def test_image_xobject_resolves_indexed_color_space_array() -> None:
    indexed = COSArray()
    indexed.add(COSName.get_pdf_name("Indexed"))
    indexed.add(COSName.get_pdf_name("DeviceRGB"))
    indexed.add(COSInteger.get(1))
    indexed.add(COSString(b"\x00\x00\x00\xff\xff\xff"))

    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("ColorSpace"), indexed)

    image = PDImageXObject(stream)
    color_space = image.get_color_space()
    assert isinstance(color_space, PDIndexed)
    assert color_space.get_base_color_space() is PDDeviceRGB.INSTANCE
    assert color_space.get_hival() == 1
    assert color_space.get_lookup_data() == b"\x00\x00\x00\xff\xff\xff"
    assert image.get_color_space_cos_object() is indexed


def test_image_create_input_stream_delegates_to_pd_stream_stop_filters() -> None:
    encoded = zlib.compress(b"pixels")
    stream = COSStream()
    stream.set_raw_data(encoded)
    stream.set_item(COSName.FILTER, COSName.FLATE_DECODE)  # type: ignore[attr-defined]

    image = PDImageXObject(stream)
    assert image.create_input_stream(["FlateDecode"]).read() == encoded
    assert image.create_input_stream().read() == b"pixels"


def test_image_create_input_stream_honors_short_filter_alias_stop() -> None:
    encoded = zlib.compress(b"alias pixels")
    stream = COSStream()
    stream.set_raw_data(encoded)
    stream.set_item(COSName.FILTER, COSName.get_pdf_name("Fl"))  # type: ignore[attr-defined]

    image = PDImageXObject(stream)
    assert image.create_input_stream(["FlateDecode"]).read() == encoded
    assert image.create_input_stream().read() == b"alias pixels"


def _g4_strip(image: Image.Image) -> bytes:
    """Encode a 1-bit Pillow image as a Group 4 TIFF and return only the
    encoded strip bytes.

    The raster is bit-inverted before libtiff encodes it so the stream
    carries Apache PDFBox's foreground-run polarity (see the same helper in
    ``tests/filter/test_ccitt_fax_decode.py``); the decoded scanlines then
    equal the source ``image.tobytes()``."""
    image = image.point(lambda v: 0 if v else 255)
    buf = io.BytesIO()
    image.save(buf, format="TIFF", compression="group4")
    raw = buf.getvalue()
    parsed = Image.open(io.BytesIO(raw))
    offsets = parsed.tag_v2[273]  # type: ignore[attr-defined]
    counts = parsed.tag_v2[279]  # type: ignore[attr-defined]
    offset = offsets[0] if isinstance(offsets, tuple) else offsets
    count = counts[0] if isinstance(counts, tuple) else counts
    return raw[offset : offset + count]


def test_image_xobject_decodes_ccitt_g4_end_to_end() -> None:
    """A CCITTFaxDecode-encoded image XObject should decode to raw
    bit-packed scanlines via the standard filter pipeline — the image
    wrapper itself does no per-codec work."""
    img = Image.new("1", (8, 4), 0)
    for x in range(0, 8, 2):
        for y in range(4):
            img.putpixel((x, y), 255)
    encoded_strip = _g4_strip(img)

    stream = COSStream()
    stream.set_raw_data(encoded_strip)
    stream.set_item(
        COSName.FILTER,  # type: ignore[attr-defined]
        COSName.get_pdf_name("CCITTFaxDecode"),
    )
    decode_parms = COSDictionary()
    decode_parms.set_int("K", -1)
    decode_parms.set_int("Columns", 8)
    decode_parms.set_int("Rows", 4)
    stream.set_item(COSName.get_pdf_name("DecodeParms"), decode_parms)

    image = PDImageXObject(stream)
    image.set_width(8)
    image.set_height(4)
    image.set_bits_per_component(1)
    image.set_color_space("DeviceGray")

    decoded = image.create_input_stream().read()
    assert decoded == b"\xaa\xaa\xaa\xaa"


def test_image_xobject_decodes_run_length_end_to_end() -> None:
    """RunLengthDecode plugged into the image filter chain decodes via
    the standard pipeline — useful for legacy scanned-image PDFs."""
    # Encoded form: literal "ab" + 4 copies of 'X' + literal "cd" + EOD.
    encoded = b"\x01ab\xfdX\x01cd\x80"
    stream = COSStream()
    stream.set_raw_data(encoded)
    stream.set_item(
        COSName.FILTER,  # type: ignore[attr-defined]
        COSName.get_pdf_name("RunLengthDecode"),
    )

    image = PDImageXObject(stream)
    image.set_width(8)
    image.set_height(1)
    image.set_bits_per_component(8)
    image.set_color_space("DeviceGray")

    decoded = image.create_input_stream().read()
    assert decoded == b"abXXXXcd"


def test_image_xobject_to_pil_image_from_raw_device_rgb() -> None:
    stream = COSStream()
    stream.set_raw_data(bytes([255, 0, 0, 0, 255, 0]))

    image = PDImageXObject(stream)
    image.set_width(2)
    image.set_height(1)
    image.set_bits_per_component(8)
    image.set_color_space("DeviceRGB")

    pil_image = image.to_pil_image()
    assert pil_image is not None
    assert pil_image.mode == "RGB"
    assert pil_image.size == (2, 1)
    assert pil_image.getpixel((0, 0)) == (255, 0, 0)
    assert pil_image.getpixel((1, 0)) == (0, 255, 0)
