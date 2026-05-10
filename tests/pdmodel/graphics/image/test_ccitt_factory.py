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
from pypdfbox.pdmodel.graphics.color import PDDeviceGray
from pypdfbox.pdmodel.graphics.image import CCITTFactory, PDImageXObject
from pypdfbox.pdmodel.graphics.image.ccitt_factory import (
    extract_from_tiff,
    prepare_image_x_object,
    read_long,
    read_short,
)
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


def test_create_from_byte_array_group4_metadata_includes_photometric() -> None:
    """Pillow writes photometric=1 (BlackIsZero); upstream Java sets
    ``/BlackIs1`` for that case (``CCITTFactory.java`` line 354). The
    port mirrors the upstream branch verbatim."""
    document = PDDocument()
    image_x = CCITTFactory.create_from_byte_array(
        document, _tiff_bytes(_pattern_image(), "group4")
    )
    cos = image_x.get_cos_object()

    assert isinstance(cos, COSStream)
    decode_parms = cos.get_dictionary_object("DecodeParms")
    assert isinstance(decode_parms, COSDictionary)
    assert decode_parms.get_boolean("BlackIs1", False) is True


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


def test_create_from_byte_array_rejects_non_bytes() -> None:
    document = PDDocument()
    with pytest.raises(TypeError):
        CCITTFactory.create_from_byte_array(document, "not bytes")  # type: ignore[arg-type]


def test_create_from_byte_array_rejects_non_tiff() -> None:
    document = PDDocument()
    with pytest.raises(OSError, match="Not a valid tiff file"):
        CCITTFactory.create_from_byte_array(document, b"not a tiff")


def test_create_from_byte_array_rejects_non_ccitt_tiff() -> None:
    document = PDDocument()
    image = Image.new("1", (8, 8), color=1)
    tiff = _tiff_bytes(image, "raw")

    with pytest.raises(OSError, match="not CCITT T4 or T6 compressed"):
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


# ---------------------------------------------------------------------------
# multi-page TIFF (CCITTFactory.createFromByteArray/File with `number`)
# ---------------------------------------------------------------------------


def _multi_page_tiff(images: list[Image.Image], compression: str = "group4") -> bytes:
    buf = io.BytesIO()
    head, *rest = images
    head.save(
        buf,
        format="TIFF",
        compression=compression,
        save_all=True,
        append_images=rest,
    )
    return buf.getvalue()


def test_create_from_byte_array_extracts_each_page_of_multi_page_tiff() -> None:
    document = PDDocument()
    pages = [_pattern_image((11 + i, 7 + i)) for i in range(3)]
    tiff = _multi_page_tiff(pages)

    for index, page in enumerate(pages):
        image_x = CCITTFactory.create_from_byte_array(document, tiff, index)
        assert image_x is not None, f"page {index} should resolve"
        assert image_x.get_width() == page.size[0]
        assert image_x.get_height() == page.size[1]


def test_create_from_byte_array_returns_none_past_end_of_multi_page_tiff() -> None:
    """Upstream returns ``null`` when ``number`` walks past the IFD chain."""
    document = PDDocument()
    pages = [_pattern_image((9, 5)), _pattern_image((11, 7))]
    tiff = _multi_page_tiff(pages)

    assert CCITTFactory.create_from_byte_array(document, tiff, 2) is None
    assert CCITTFactory.create_from_byte_array(document, tiff, 99) is None


def test_create_from_file_supports_number_argument(tmp_path) -> None:  # noqa: ANN001
    """``CCITTFactory.createFromFile(document, file, number)`` reaches a
    later page in the TIFF (line 190 upstream)."""
    document = PDDocument()
    pages = [_pattern_image((9, 5)), _pattern_image((11, 7))]
    path = tmp_path / "multi.tif"
    path.write_bytes(_multi_page_tiff(pages))

    page1 = CCITTFactory.create_from_file(document, path, 1)
    assert page1 is not None
    assert page1.get_width() == 11
    assert page1.get_height() == 7


def test_create_from_file_does_not_lock_source_file(tmp_path) -> None:  # noqa: ANN001
    """Mirrors upstream ``testCreateFromFileLock`` — file must be released
    after the call so the caller can immediately delete it."""
    document = PDDocument()
    path = tmp_path / "lock.tif"
    path.write_bytes(_tiff_bytes(_pattern_image(), "group4"))

    CCITTFactory.create_from_file(document, path)
    path.unlink()
    assert not path.exists()


# ---------------------------------------------------------------------------
# read_short / read_long / extract_from_tiff / prepare_image_x_object
# ---------------------------------------------------------------------------


def test_read_short_handles_both_endiannesses() -> None:
    assert read_short("I", io.BytesIO(b"\x2a\x00")) == 42
    assert read_short("M", io.BytesIO(b"\x00\x2a")) == 42


def test_read_long_handles_both_endiannesses() -> None:
    assert read_long("I", io.BytesIO(b"\x78\x56\x34\x12")) == 0x12345678
    assert read_long("M", io.BytesIO(b"\x12\x34\x56\x78")) == 0x12345678


def test_read_short_raises_on_truncated_input() -> None:
    with pytest.raises(OSError):
        read_short("I", io.BytesIO(b""))


def test_read_long_raises_on_truncated_input() -> None:
    with pytest.raises(OSError):
        read_long("I", io.BytesIO(b"\x01\x02"))


def test_extract_from_tiff_populates_decode_params_for_single_strip() -> None:
    tiff = _tiff_bytes(_pattern_image(), "group4")
    params = COSDictionary()
    out = io.BytesIO()
    extract_from_tiff(io.BytesIO(tiff), out, params, 0)

    assert params.get_int("Columns", 0) == 17
    assert params.get_int("Rows", 0) == 9
    assert params.get_int("K", 0) == -1
    assert out.getvalue() == _single_strip(tiff)


def test_extract_from_tiff_leaves_buffer_empty_past_end_of_chain() -> None:
    tiff = _tiff_bytes(_pattern_image(), "group4")
    params = COSDictionary()
    out = io.BytesIO()
    extract_from_tiff(io.BytesIO(tiff), out, params, 5)
    assert out.getvalue() == b""


def test_prepare_image_x_object_encodes_packed_bits_as_group4() -> None:
    document = PDDocument()
    src = Image.new("1", (32, 8), color=1)
    raw = src.tobytes()

    image_x = prepare_image_x_object(document, raw, 32, 8, PDDeviceGray.INSTANCE)
    cos = image_x.get_cos_object()

    assert isinstance(cos, COSStream)
    decode_parms = cos.get_dictionary_object("DecodeParms")
    assert isinstance(decode_parms, COSDictionary)
    assert decode_parms.get_int("K", 0) == -1
    assert decode_parms.get_int("Columns", 0) == 32
    assert decode_parms.get_int("Rows", 0) == 8
    assert image_x.get_filter() == COSName.get_pdf_name("CCITTFaxDecode")
