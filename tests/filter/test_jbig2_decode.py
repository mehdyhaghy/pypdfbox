from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.filter import FilterFactory, JBIG2Decode
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document

# JBIG2 decoding is supported via the first-party pure-Python decoder in
# pypdfbox.jbig2 (a port of the Apache-2.0 apache/pdfbox-jbig2 plugin —
# no GPL, no native code). decode() turns the embedded JBIG2 codestream
# into a 1-bit DeviceGray raster with sample 0 = black, 1 = white (the
# same polarity /CCITTFaxDecode emits by default).

_FIXTURES = Path(__file__).resolve().parents[1] / "jbig2" / "fixtures"


def _raw_bitmap(data: bytes, globals_data: bytes | None = None):
    """Decode the raw JBIG2 page bitmap (1 = black) for polarity asserts."""
    global_segments = None
    if globals_data is not None:
        global_segments = JBIG2Document(
            ImageInputStream(globals_data)
        ).get_global_segments()
    doc = JBIG2Document(ImageInputStream(data), global_segments)
    return doc.get_page(1).get_bitmap()


# ---------- registration ----------------------------------------------


def test_jbig2_filter_registered_under_long_name_only() -> None:
    assert FilterFactory.is_registered("JBIG2Decode")
    assert isinstance(FilterFactory.get("JBIG2Decode"), JBIG2Decode)
    # ISO 32000-1 §7.4.2 Table 6 defines NO short-name abbreviation
    # for /JBIG2Decode — make sure we haven't invented one.
    with pytest.raises(KeyError):
        FilterFactory.get("JBIG2")


def test_jbig2_globals_class_constant_matches_pdf_spec_key() -> None:
    """Mirrors upstream's ``COSName.JBIG2_GLOBALS`` reference site —
    porters reaching for the constant land on a stable name on the
    filter class."""
    assert JBIG2Decode.JBIG2_GLOBALS == "JBIG2Globals"


# ---------- decode: real standalone JBIG2 streams ----------------------


@pytest.mark.parametrize("name", ["003.jb2", "005.jb2", "006.jb2"])
def test_jbig2_decode_dims_and_length(name: str) -> None:
    data = (_FIXTURES / name).read_bytes()
    bitmap = _raw_bitmap(data)

    out = io.BytesIO()
    result = JBIG2Decode().decode(io.BytesIO(data), out)

    width = bitmap.get_width()
    height = bitmap.get_height()
    row_stride = bitmap.get_row_stride()

    # Surfaced geometry matches the decoded bitmap.
    assert result.parameters.get_int("Width") == width
    assert result.parameters.get_int("Height") == height
    assert result.parameters.get_int("BitsPerComponent") == 1
    assert result.parameters.get_int("ColorComponents") == 1

    decoded = out.getvalue()
    # The decoded raster is row-padded to whole bytes, MSB-first — same
    # shape the image XObject decode path consumes for 1-bpc DeviceGray.
    assert len(decoded) == height * row_stride
    assert result.bytes_written == len(decoded)


def test_jbig2_decode_polarity_is_inverted_from_bitmap() -> None:
    """JBIG2 bitmap has 1 = black; the decoded raster must invert that so
    sample 0 = black / 1 = white (the polarity the DeviceGray image
    pipeline and Apache PDFBox's JBIG2Filter both use)."""
    data = (_FIXTURES / "003.jb2").read_bytes()
    bitmap = _raw_bitmap(data)
    raw = bytes(bitmap.get_byte_array())

    out = io.BytesIO()
    JBIG2Decode().decode(io.BytesIO(data), out)
    decoded = out.getvalue()

    width = bitmap.get_width()
    row_stride = bitmap.get_row_stride()
    rem = width & 7
    full_bytes = row_stride if rem == 0 else row_stride - 1
    pad_mask = 0 if rem == 0 else (~0xFF >> rem) & 0xFF

    # Every full byte is the bitwise inverse; the trailing pad byte (if
    # any) is the inverse masked to clear the pad bits — matching
    # upstream Bitmaps.buildRaster exactly.
    for row in range(bitmap.get_height()):
        base = row * row_stride
        for col in range(full_bytes):
            assert decoded[base + col] == (~raw[base + col]) & 0xFF
        if pad_mask:
            assert decoded[base + full_bytes] == ((~raw[base + full_bytes]) & pad_mask)


def test_jbig2_decode_embedded_with_globals() -> None:
    """Embedded organisation: bare segments + a separate /JBIG2Globals
    stream. The globals stream is decoded and handed to the document so
    the per-image text region can resolve its symbol dictionary."""
    data = (_FIXTURES / "21.jb2").read_bytes()
    globals_data = (_FIXTURES / "21.glob").read_bytes()
    bitmap = _raw_bitmap(data, globals_data)

    # Build a stream dict carrying /DecodeParms /JBIG2Globals (a stream).
    globals_stream = COSStream()
    globals_stream.set_raw_data(globals_data)
    decode_parms = COSDictionary()
    decode_parms.set_item(
        COSName.get_pdf_name("JBIG2Globals"), globals_stream
    )
    parameters = COSDictionary()
    parameters.set_item(COSName.get_pdf_name("DecodeParms"), decode_parms)

    out = io.BytesIO()
    result = JBIG2Decode().decode(io.BytesIO(data), out, parameters)

    assert result.parameters.get_int("Width") == bitmap.get_width()
    assert result.parameters.get_int("Height") == bitmap.get_height()
    assert len(out.getvalue()) == bitmap.get_height() * bitmap.get_row_stride()


def test_jbig2_decode_empty_input_writes_nothing() -> None:
    out = io.BytesIO()
    result = JBIG2Decode().decode(io.BytesIO(b""), out)
    assert result.bytes_written == 0
    assert out.getvalue() == b""


def test_jbig2_decode_garbage_raises_oserror() -> None:
    with pytest.raises(OSError):
        JBIG2Decode().decode(io.BytesIO(b"\xfa\xce\x01not-jbig2"), io.BytesIO())


# ---------- encode -----------------------------------------------------


def test_jbig2_encode_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="decode-only"):
        JBIG2Decode().encode(io.BytesIO(b""), io.BytesIO(), COSDictionary())
