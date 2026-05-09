"""Hand-written tests for :class:`CCITTFactory`.

Covers 1-bit image encoding plus single-strip CCITT TIFF extraction:
filter wiring, ``/DecodeParms`` metadata, byte preservation, decoder
round-trips, and input-validation guards.
"""
from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.filter import CCITTFaxDecode
from pypdfbox.pdmodel.graphics.image import CCITTFactory, PDImageXObject
from pypdfbox.pdmodel.pd_document import PDDocument


def _pattern_image(size: tuple[int, int] = (17, 9)) -> Image.Image:
    image = Image.new("1", size, color=1)
    width, height = size
    for x in range(width):
        image.putpixel((x, x % height), 0)
    return image


def _tiff_bytes(image: Image.Image, compression: str) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="TIFF", compression=compression)
    return buf.getvalue()


def _single_strip(tiff_bytes: bytes) -> bytes:
    with Image.open(io.BytesIO(tiff_bytes)) as parsed:
        offsets = parsed.tag_v2[273]
        counts = parsed.tag_v2[279]
        offset = offsets[0] if isinstance(offsets, tuple) else offsets
        count = counts[0] if isinstance(counts, tuple) else counts
    return tiff_bytes[offset : offset + count]


def _decode(image_x: PDImageXObject) -> bytes:
    cos = image_x.get_cos_object()
    assert isinstance(cos, COSStream)
    out = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(cos.get_raw_data()), out, cos)
    return out.getvalue()

# ---------------------------------------------------------------------------
# create_from_image
# ---------------------------------------------------------------------------


def test_create_from_image_returns_pd_image_x_object() -> None:
    document = PDDocument()
    src = Image.new("1", (32, 16), color=1)

    image_x = CCITTFactory.create_from_image(document, src)
    assert isinstance(image_x, PDImageXObject)
    assert image_x.get_width() == 32
    assert image_x.get_height() == 16
    assert image_x.get_bits_per_component() == 1


def test_create_from_image_uses_ccitt_fax_decode_filter() -> None:
    """``/Filter`` must be ``/CCITTFaxDecode`` (Group 4 via ``K=-1``)."""
    document = PDDocument()
    src = Image.new("1", (24, 8), color=0)

    image_x = CCITTFactory.create_from_image(document, src)
    filt = image_x.get_filter()
    assert isinstance(filt, COSName)
    assert filt.name == "CCITTFaxDecode"


def test_create_from_image_color_space_is_device_gray() -> None:
    document = PDDocument()
    src = Image.new("1", (8, 8), color=1)

    image_x = CCITTFactory.create_from_image(document, src)
    cs = image_x.get_color_space_cos_object()
    assert isinstance(cs, COSName)
    assert cs.name == "DeviceGray"


def test_create_from_image_decode_parms_match_dimensions() -> None:
    """``/DecodeParms`` must carry ``K=-1`` plus the real columns/rows."""
    document = PDDocument()
    src = Image.new("1", (40, 24), color=1)

    image_x = CCITTFactory.create_from_image(document, src)
    cos = image_x.get_cos_object()
    assert isinstance(cos, COSStream)

    decode_parms = cos.get_dictionary_object("DecodeParms")
    assert isinstance(decode_parms, COSDictionary)
    assert decode_parms.get_int("K", 0) == -1
    assert decode_parms.get_int("Columns", 0) == 40
    assert decode_parms.get_int("Rows", 0) == 24


def test_create_from_image_round_trips_through_decoder() -> None:
    """Encoded body must decode back to the original packed bitstream."""
    document = PDDocument()
    src = Image.new("1", (64, 32), color=1)
    # Sparse pattern: black pixels along the diagonal.
    for x in range(32):
        src.putpixel((x, x), 0)

    image_x = CCITTFactory.create_from_image(document, src)
    cos = image_x.get_cos_object()
    assert isinstance(cos, COSStream)

    raw = cos.get_raw_data()
    out = io.BytesIO()
    CCITTFaxDecode().decode(io.BytesIO(raw), out, cos)
    assert out.getvalue() == src.tobytes()


def test_create_from_image_rejects_non_one_bit() -> None:
    """Upstream raises ``IllegalArgumentException`` for non-1-bit input."""
    document = PDDocument()
    src = Image.new("L", (8, 8), color=128)
    with pytest.raises(ValueError):
        CCITTFactory.create_from_image(document, src)


def test_create_from_image_rejects_non_image() -> None:
    document = PDDocument()
    with pytest.raises(TypeError):
        CCITTFactory.create_from_image(document, b"not an image")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# create_from_byte_array / create_from_file
# ---------------------------------------------------------------------------


def test_create_from_byte_array_extracts_group4_tiff_strip_verbatim() -> None:
    document = PDDocument()
    src = _pattern_image()
    tiff = _tiff_bytes(src, "group4")

    image_x = CCITTFactory.create_from_byte_array(document, tiff)
    cos = image_x.get_cos_object()

    assert isinstance(cos, COSStream)
    assert cos.get_raw_data() == _single_strip(tiff)


def test_create_from_byte_array_group4_metadata_and_decode_parms() -> None:
    document = PDDocument()
    tiff = _tiff_bytes(_pattern_image(), "group4")

    image_x = CCITTFactory.create_from_byte_array(document, tiff)
    cos = image_x.get_cos_object()

    assert isinstance(cos, COSStream)
    assert image_x.get_width() == 17
    assert image_x.get_height() == 9
    assert image_x.get_bits_per_component() == 1
    assert image_x.get_filter() == COSName.get_pdf_name("CCITTFaxDecode")
    decode_parms = cos.get_dictionary_object("DecodeParms")
    assert isinstance(decode_parms, COSDictionary)
    assert decode_parms.get_int("K", 0) == -1
    assert decode_parms.get_int("Columns", 0) == 17
    assert decode_parms.get_int("Rows", 0) == 9


def test_create_from_byte_array_group4_round_trips_through_decoder() -> None:
    document = PDDocument()
    src = _pattern_image()
    image_x = CCITTFactory.create_from_byte_array(
        document, _tiff_bytes(src, "group4")
    )

    assert _decode(image_x) == src.tobytes()


def test_create_from_byte_array_extracts_group3_tiff_as_k_zero() -> None:
    document = PDDocument()
    src = _pattern_image()
    image_x = CCITTFactory.create_from_byte_array(
        document, _tiff_bytes(src, "group3")
    )
    cos = image_x.get_cos_object()

    assert isinstance(cos, COSStream)
    decode_parms = cos.get_dictionary_object("DecodeParms")
    assert isinstance(decode_parms, COSDictionary)
    assert decode_parms.get_int("K", -99) == 0
    assert _decode(image_x) == src.tobytes()


def test_create_from_file_delegates_to_byte_array(tmp_path) -> None:  # noqa: ANN001
    document = PDDocument()
    src = _pattern_image()
    tiff = _tiff_bytes(src, "group4")
    path = tmp_path / "image.tif"
    path.write_bytes(tiff)

    image_x = CCITTFactory.create_from_file(document, path)
    cos = image_x.get_cos_object()

    assert isinstance(cos, COSStream)
    assert cos.get_raw_data() == _single_strip(tiff)


def test_ccitt_factory_file_and_byte_array_java_aliases(tmp_path) -> None:  # noqa: ANN001
    document = PDDocument()
    tiff = _tiff_bytes(_pattern_image(), "group4")
    path = tmp_path / "image.tif"
    path.write_bytes(tiff)

    from_bytes = CCITTFactory.createFromByteArray(document, tiff)
    from_file = CCITTFactory.createFromFile(document, path)

    assert from_bytes.get_width() == from_file.get_width() == 17
    assert from_bytes.get_height() == from_file.get_height() == 9


def test_create_from_byte_array_rejects_non_bytes() -> None:
    document = PDDocument()
    with pytest.raises(TypeError):
        CCITTFactory.create_from_byte_array(document, "not bytes")  # type: ignore[arg-type]


def test_create_from_byte_array_rejects_non_tiff() -> None:
    document = PDDocument()
    with pytest.raises(ValueError, match="unreadable TIFF|expected TIFF"):
        CCITTFactory.create_from_byte_array(document, b"not a tiff")


def test_create_from_byte_array_rejects_non_ccitt_tiff() -> None:
    document = PDDocument()
    image = Image.new("1", (8, 8), color=1)
    tiff = _tiff_bytes(image, "raw")

    with pytest.raises(ValueError, match="unsupported TIFF compression"):
        CCITTFactory.create_from_byte_array(document, tiff)


# ---------------------------------------------------------------------------
# class shape
# ---------------------------------------------------------------------------


def test_ccitt_factory_is_static_only() -> None:
    """Upstream marks CCITTFactory ``final`` with a private constructor —
    instantiation is forbidden. The Python port enforces the same by
    raising in ``__init__``."""
    with pytest.raises(TypeError):
        CCITTFactory()
