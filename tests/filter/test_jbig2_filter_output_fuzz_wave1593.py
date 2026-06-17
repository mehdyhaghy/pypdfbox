"""JBIG2 filter output-path fuzz — wave 1593 (agent E).

Hammers the ``/JBIG2Decode`` filter's *output* path — the part that turns a
decoded :class:`~pypdfbox.jbig2.bitmap.Bitmap` (JBIG2 ``1`` = black) into the
1-bit ``DeviceGray`` raster the PDF image pipeline consumes
(``pypdfbox/filter/jbig2_decode.py`` + the helper it shares with
``Bitmaps.buildRaster``). The decode of *real* multi-segment fixtures is pinned
by ``tests/filter/test_jbig2_decode.py``; this wave pins the *byte-level
contract* of the raster the filter emits, across:

* a full encode -> decode -> raster -> byte-pack round trip of a *known* bitmap
  through an immediate generic region (template-0 arithmetic), at byte-aligned
  and non-byte-aligned widths, so the exact output bytes are computed
  independently and asserted;
* the JBIG2 ``1`` = black polarity inverted to ``DeviceGray`` sample ``0`` =
  black / ``1`` = white (the polarity ``/CCITTFaxDecode`` emits by default and
  Apache PDFBox's ``JBIG2Filter`` / ``Bitmaps.buildRaster`` produce);
* MSB-first bit packing and per-row pad-bit masking (the trailing pad bits of
  each row's final byte are forced to ``0`` exactly like upstream's
  ``(~0xff >> (width & 7)) & 0xff`` mask);
* the surfaced geometry (``/Width`` / ``/Height`` / ``/BitsPerComponent=1`` /
  ``/ColorComponents=1``) matching the page-information width/height;
* the page-information *default pixel* — a blank page (no region) with default
  pixel ``0`` decoding to an all-white (``0xFF``) raster and default pixel ``1``
  to an all-black (``0x00``) raster after inversion;
* the ``/JBIG2Globals`` shared-segment stream being applied (a separate globals
  stream whose symbol dictionary the page's text region resolves), including
  the globals stream itself carrying a ``/FlateDecode`` filter chain;
* empty input writing nothing, and garbage raising ``OSError``.

Expectations are derived from ITU-T T.88 and Apache PDFBox's ``JBIG2Filter``
(which writes the ``DataBufferByte`` of the ``TYPE_BYTE_BINARY`` image the
JBIG2 ImageIO reader produces). The known-bitmap streams are assembled with the
oracle-verified ``tests/jbig2/helpers/jb2_encoder`` + ``mq_encoder`` helpers.
No real divergence is exercised — the filter output path is a faithful port.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.filter import FilterFactory, JBIG2Decode
from pypdfbox.filter.jbig2_decode import _inverted_bitmap_bytes
from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.jbig2_document import JBIG2Document
from tests.jbig2.helpers.jb2_encoder import (
    BitWriter,
    assemble,
    page_info_segment_data,
    region_segment_info,
)
from tests.jbig2.helpers.mq_encoder import (
    Cx,
    MQEncoder,
    encode_generic_region_template0,
)

# JBIG2 segment type codes (ITU-T T.88 §7.3).
_PAGE_INFO = 48
_IMMEDIATE_GENERIC_REGION = 38

# Template-0 nominal AT pixels (§6.2.5.3 Figure 4).
_NOMINAL_AT = ((3, -1), (-3, -1), (2, -2), (-2, -2))


def _generic_region_data(rows: list[list[int]], width: int, height: int) -> bytes:
    """Build an immediate-generic-region data part for the given bitmap.

    Region info (17 bytes) + generic-region flags (template 0, MMR 0,
    TPGDON 0) + 4 nominal AT pairs + the template-0 arithmetic body.
    """
    enc = MQEncoder()
    cx = Cx(65536, 1)
    encode_generic_region_template0(enc, cx, rows, width, height)
    body = enc.flush()
    gen_flags = bytes([0x00])  # MMR 0, template 0, TPGDON 0, ext 0
    at = b"".join(bytes([x & 0xFF, y & 0xFF]) for x, y in _NOMINAL_AT)
    return region_segment_info(width, height) + gen_flags + at + body


def _generic_region_stream(rows: list[list[int]], width: int, height: int) -> bytes:
    """A complete standalone JBIG2 stream: page info + one generic region."""
    pi = page_info_segment_data(width, height)
    region = _generic_region_data(rows, width, height)
    return assemble(
        [
            (0, _PAGE_INFO, [], 1, pi),
            (1, _IMMEDIATE_GENERIC_REGION, [], 1, region),
        ]
    )


def _packed_rows(rows: list[list[int]], width: int, height: int) -> bytearray:
    """Pack ``rows`` MSB-first into the JBIG2 bitmap byte layout (1 = black)."""
    row_stride = (width + 7) >> 3
    out = bytearray(row_stride * height)
    for y in range(height):
        for x in range(width):
            if rows[y][x] & 1:
                out[y * row_stride + (x >> 3)] |= 0x80 >> (x & 7)
    return out


def _expected_raster(rows: list[list[int]], width: int, height: int) -> bytes:
    """The DeviceGray raster the filter must emit: inverted + pad-masked."""
    packed = _packed_rows(rows, width, height)
    row_stride = (width + 7) >> 3
    rem = width & 7
    full = row_stride if rem == 0 else row_stride - 1
    pad_mask = 0 if rem == 0 else (~0xFF >> rem) & 0xFF
    out = bytearray(len(packed))
    idx = 0
    for _y in range(height):
        for _c in range(full):
            out[idx] = (~packed[idx]) & 0xFF
            idx += 1
        if pad_mask:
            out[idx] = (~packed[idx]) & pad_mask
            idx += 1
    return bytes(out)


def _decode(stream: bytes, parameters: COSDictionary | None = None):
    out = io.BytesIO()
    result = JBIG2Decode().decode(io.BytesIO(stream), out, parameters)
    return result, out.getvalue()


# Known bitmaps spanning byte-aligned, non-aligned, single-column, tall.
_BITMAPS = {
    "8x4_diag": (
        [
            [1, 0, 0, 0, 0, 0, 0, 1],
            [0, 1, 0, 0, 0, 0, 1, 0],
            [0, 0, 1, 0, 0, 1, 0, 0],
            [0, 0, 0, 1, 1, 0, 0, 0],
        ],
        8,
        4,
    ),
    "5x2_stripe": ([[1, 0, 1, 0, 1], [0, 1, 0, 1, 0]], 5, 2),
    "1x4_col": ([[1], [0], [1], [1]], 1, 4),
    "12x3": (
        [
            [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
            [0, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 0],
            [0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0],
        ],
        12,
        3,
    ),
    "16x1_all_black": ([[1] * 16], 16, 1),
    "16x1_all_white": ([[0] * 16], 16, 1),
    "7x1_odd": ([[1, 0, 1, 1, 0, 0, 1]], 7, 1),
    "3x3_checker": ([[1, 0, 1], [0, 1, 0], [1, 0, 1]], 3, 3),
}


# ---------------------------------------------------------------------------
# Full encode -> decode -> raster round trip of a known bitmap.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", list(_BITMAPS))
def test_generic_region_round_trip_exact_bytes(name: str) -> None:
    rows, width, height = _BITMAPS[name]
    stream = _generic_region_stream(rows, width, height)
    result, decoded = _decode(stream)

    assert result.parameters.get_int("Width") == width
    assert result.parameters.get_int("Height") == height
    assert result.parameters.get_int("BitsPerComponent") == 1
    assert result.parameters.get_int("ColorComponents") == 1

    row_stride = (width + 7) >> 3
    assert len(decoded) == height * row_stride
    assert result.bytes_written == len(decoded)
    # The exact DeviceGray bytes — independently computed (1 = black inverted
    # to sample 0 = black, MSB-first, pad bits cleared).
    assert decoded == _expected_raster(rows, width, height)


@pytest.mark.parametrize("name", list(_BITMAPS))
def test_round_trip_polarity_is_inverted(name: str) -> None:
    """JBIG2 1 = black must invert to DeviceGray sample 0 = black."""
    rows, width, height = _BITMAPS[name]
    stream = _generic_region_stream(rows, width, height)
    _result, decoded = _decode(stream)
    packed = _packed_rows(rows, width, height)
    row_stride = (width + 7) >> 3
    rem = width & 7
    full = row_stride if rem == 0 else row_stride - 1
    for y in range(height):
        base = y * row_stride
        for c in range(full):
            # Every full byte is the bitwise inverse of the JBIG2 packing.
            assert decoded[base + c] == (~packed[base + c]) & 0xFF


# ---------------------------------------------------------------------------
# Pad-bit masking — trailing bits of the last row byte must be zero.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "width", [1, 2, 3, 4, 5, 6, 7, 9, 13, 15, 17], ids=lambda w: f"w{w}"
)
def test_pad_bits_cleared_for_non_aligned_widths(width: int) -> None:
    height = 2
    rows = [[1] * width for _ in range(height)]  # all black -> stress pad
    stream = _generic_region_stream(rows, width, height)
    _result, decoded = _decode(stream)
    row_stride = (width + 7) >> 3
    rem = width & 7
    if rem == 0:
        pytest.skip("byte-aligned width has no pad bits")
    pad_mask = (~0xFF >> rem) & 0xFF  # 1s in the valid region, 0s in pad
    for y in range(height):
        last = decoded[y * row_stride + row_stride - 1]
        # Pad bits (the bits NOT in pad_mask) must be zero.
        assert last & ~pad_mask & 0xFF == 0


# ---------------------------------------------------------------------------
# Blank page — page-information default pixel polarity.
# ---------------------------------------------------------------------------
def _blank_page_stream(width: int, height: int, default_pixel: int) -> bytes:
    bw = BitWriter()
    bw.write_bits(width, 32)
    bw.write_bits(height, 32)
    bw.write_bits(0, 32)  # x resolution
    bw.write_bits(0, 32)  # y resolution
    # Page-info flags byte: bit 2 == default pixel value.
    bw.write_byte((default_pixel & 1) << 2)
    bw.write_bits(0, 16)  # striping info
    return assemble([(0, _PAGE_INFO, [], 1, bw.to_bytes())])


@pytest.mark.parametrize(
    ("width", "height"), [(16, 2), (8, 1), (13, 3)], ids=["16x2", "8x1", "13x3"]
)
def test_blank_page_default_pixel_0_is_all_white(width: int, height: int) -> None:
    """Default pixel 0 (white in JBIG2) inverts to DeviceGray 0xFF (white)."""
    stream = _blank_page_stream(width, height, 0)
    result, decoded = _decode(stream)
    assert result.parameters.get_int("Width") == width
    assert result.parameters.get_int("Height") == height
    row_stride = (width + 7) >> 3
    rem = width & 7
    # Full bytes are 0xFF; trailing pad byte (if any) is pad-masked.
    expected = bytearray()
    for _y in range(height):
        if rem == 0:
            expected.extend(b"\xff" * row_stride)
        else:
            expected.extend(b"\xff" * (row_stride - 1))
            expected.append((~0xFF >> rem) & 0xFF)
    assert decoded == bytes(expected)


@pytest.mark.parametrize(
    ("width", "height"), [(16, 2), (8, 1), (13, 3)], ids=["16x2", "8x1", "13x3"]
)
def test_blank_page_default_pixel_1_is_all_black(width: int, height: int) -> None:
    """Default pixel 1 (black in JBIG2) inverts to DeviceGray 0x00 (black)."""
    stream = _blank_page_stream(width, height, 1)
    _result, decoded = _decode(stream)
    row_stride = (width + 7) >> 3
    assert decoded == b"\x00" * (height * row_stride)


# ---------------------------------------------------------------------------
# /JBIG2Globals shared-segment stream applied.
# ---------------------------------------------------------------------------
def _globals_parameters(globals_data: bytes, *, flate: bool) -> COSDictionary:
    """Stream dict with /DecodeParms /JBIG2Globals (optionally Flate-filtered)."""
    globals_stream = COSStream()
    if flate:
        # Round-trip the globals through FlateDecode so to_byte_array() must
        # run the filter chain to recover the raw global segments.
        out = globals_stream.create_output_stream(COSName.get_pdf_name("FlateDecode"))
        out.write(globals_data)
        out.close()
    else:
        globals_stream.set_raw_data(globals_data)
    decode_parms = COSDictionary()
    decode_parms.set_item(COSName.get_pdf_name("JBIG2Globals"), globals_stream)
    parameters = COSDictionary()
    parameters.set_item(COSName.get_pdf_name("DecodeParms"), decode_parms)
    return parameters


@pytest.mark.parametrize("flate", [False, True], ids=["raw_globals", "flate_globals"])
def test_globals_stream_applied(flate: bool) -> None:
    """Embedded organisation: a /JBIG2Globals stream + bare page segments.

    The globals stream carries the shared symbol dictionary the page's text
    region resolves; the decoded raster must match the dimensions/length of
    the bitmap decoded with the globals applied.
    """
    from pathlib import Path

    fixtures = Path(__file__).resolve().parents[1] / "jbig2" / "fixtures"
    data = (fixtures / "21.jb2").read_bytes()
    globals_data = (fixtures / "21.glob").read_bytes()

    global_segments = JBIG2Document(
        ImageInputStream(globals_data)
    ).get_global_segments()
    bitmap = JBIG2Document(
        ImageInputStream(data), global_segments
    ).get_page(1).get_bitmap()

    parameters = _globals_parameters(globals_data, flate=flate)
    result, decoded = _decode(data, parameters)

    assert result.parameters.get_int("Width") == bitmap.get_width()
    assert result.parameters.get_int("Height") == bitmap.get_height()
    assert len(decoded) == bitmap.get_height() * bitmap.get_row_stride()
    # With globals applied the output must equal the inverted bitmap bytes.
    assert decoded == _inverted_bitmap_bytes(bitmap)


def test_globals_in_decode_parms_array_form() -> None:
    """/DecodeParms may be an array; the entry at the filter index carries
    /JBIG2Globals."""
    from pathlib import Path

    fixtures = Path(__file__).resolve().parents[1] / "jbig2" / "fixtures"
    data = (fixtures / "21.jb2").read_bytes()
    globals_data = (fixtures / "21.glob").read_bytes()

    globals_stream = COSStream()
    globals_stream.set_raw_data(globals_data)
    entry = COSDictionary()
    entry.set_item(COSName.get_pdf_name("JBIG2Globals"), globals_stream)
    arr = COSArray()
    arr.add(entry)
    parameters = COSDictionary()
    parameters.set_item(COSName.get_pdf_name("DecodeParms"), arr)

    result, decoded = _decode(data, parameters)
    assert result.parameters.get_int("Width") > 0
    assert len(decoded) > 0


# ---------------------------------------------------------------------------
# _inverted_bitmap_bytes helper — direct byte-packing pins.
# ---------------------------------------------------------------------------
def test_inverted_helper_all_white_bitmap_is_all_0xff_masked() -> None:
    bitmap = Bitmap(11, 2)  # all zero (white) by default; non-aligned width
    out = _inverted_bitmap_bytes(bitmap)
    row_stride = bitmap.get_row_stride()
    rem = 11 & 7
    pad_mask = (~0xFF >> rem) & 0xFF
    for y in range(2):
        base = y * row_stride
        assert out[base] == 0xFF  # first full byte -> ~0 == 0xFF
        assert out[base + row_stride - 1] == (0xFF & pad_mask)


def test_inverted_helper_all_black_bitmap_is_all_zero() -> None:
    bitmap = Bitmap(16, 3)
    bitmap.fill_bitmap(0xFF)  # all black
    out = _inverted_bitmap_bytes(bitmap)
    assert out == b"\x00" * (3 * bitmap.get_row_stride())


def test_inverted_helper_byte_aligned_has_no_partial_byte() -> None:
    bitmap = Bitmap(8, 1)
    bitmap.set_pixel(0, 0, 1)  # 10000000 -> 0x80 -> inverted 0x7F
    out = _inverted_bitmap_bytes(bitmap)
    assert out == bytes([0x7F])


def test_inverted_helper_dimensions_match_bitmap() -> None:
    bitmap = Bitmap(20, 5)
    out = _inverted_bitmap_bytes(bitmap)
    assert len(out) == 5 * bitmap.get_row_stride()
    assert len(out) == 5 * ((20 + 7) >> 3)


# ---------------------------------------------------------------------------
# Empty / garbage input.
# ---------------------------------------------------------------------------
def test_empty_input_writes_nothing() -> None:
    result, decoded = _decode(b"")
    assert result.bytes_written == 0
    assert decoded == b""


def test_garbage_raises_oserror() -> None:
    with pytest.raises(OSError):
        _decode(b"\xfa\xce\x01definitely-not-jbig2")


def test_truncated_header_raises_oserror() -> None:
    # A valid file-header magic followed by nothing usable.
    magic = bytes([0x97, 0x4A, 0x42, 0x32, 0x0D, 0x0A, 0x1A, 0x0A])
    with pytest.raises(OSError):
        _decode(magic + b"\x00\x00\x00\x00\x01")


# ---------------------------------------------------------------------------
# Registration parity.
# ---------------------------------------------------------------------------
def test_filter_registered_long_name_only() -> None:
    assert FilterFactory.is_registered("JBIG2Decode")
    assert isinstance(FilterFactory.get("JBIG2Decode"), JBIG2Decode)
    with pytest.raises(KeyError):
        FilterFactory.get("JBIG2")
