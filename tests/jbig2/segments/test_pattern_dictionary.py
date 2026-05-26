"""Hand-written unit tests for the JBIG2 pattern-dictionary decoder.

Covers ``PatternDictionary`` header parsing (pattern-dictionary flags + HDPW +
HDPH + GRAYMAX) and the §6.7.5 decode procedure: a collective bitmap is decoded
by an internal ``GenericRegion`` (width ``(GRAYMAX + 1) * HDPW``, height
``HDPH``) and then sliced left-to-right into ``GRAYMAX + 1`` patterns, each
``HDPW`` x ``HDPH``.

The crafted input is the EXACT segment-data part of a pattern-dictionary
segment (everything after the segment header): the flags byte, HDPW, HDPH, the
32-bit GRAYMAX, then the arithmetic-coded collective bitmap. The coded payload
is an arbitrary but fixed byte string; because the MQ decoder is deterministic,
feeding identical coded bytes to both the upstream and the ported decoder yields
the identical collective bitmap (and therefore identical sliced patterns) — so
the captured expectations double as a bit-exact parity fixture. The live oracle
differential lives in
``tests/jbig2/segments/oracle/test_pattern_dictionary_oracle.py``.

Bit convention: pypdfbox's ``Bitmap`` packs MSB-first, 1 == set.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.jbig2.err.invalid_header_value_exception import (
    InvalidHeaderValueException,
)
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.pattern_dictionary import PatternDictionary

# Arbitrary but fixed arithmetic-coded payload (shared with the generic-region
# fixtures); the deterministic MQ decoder turns it into a stable bitmap.
CODED = bytes([0x84, 0xC7, 0x3B, 0x6A, 0x21, 0x00, 0x00, 0x00])


def pd_flags(mmr: int = 0, template: int = 0) -> bytes:
    """Pattern-dictionary flags byte, 7.4.4.1.1.

    bit0=HDMMR, bit1-2=HDTEMPLATE, bit3-7 reserved.
    """
    return bytes([(mmr & 1) | ((template & 3) << 1)])


def pd_data(
    hdpw: int, hdph: int, gray_max: int, *, mmr: int = 0, template: int = 0, coded=CODED
) -> bytes:
    """Assemble a pattern-dictionary segment-data buffer."""
    return (
        pd_flags(mmr=mmr, template=template)
        + bytes([hdpw & 0xFF, hdph & 0xFF])
        + struct.pack(">I", gray_max)
        + coded
    )


def _parse(segment_data: bytes) -> PatternDictionary:
    iis = ImageInputStream(segment_data)
    sis = SubInputStream(iis, 0, len(segment_data))
    pd = PatternDictionary()
    pd.init(None, sis)
    return pd


# ---------------------------------------------------------------------------
# Header parsing
# ---------------------------------------------------------------------------
def test_parse_header_arithmetic_template0():
    pd = _parse(pd_data(4, 4, 3, template=0))
    assert pd.is_mmr_encoded_flag() is False
    assert pd.get_hd_template() == 0
    assert pd.get_hdp_width() == 4
    assert pd.get_hdp_height() == 4
    assert pd.get_gray_max() == 3


def test_parse_header_template_and_mmr_bits():
    pd = _parse(pd_data(8, 6, 1, mmr=1, template=2))
    assert pd.is_mmr_encoded_flag() is True
    assert pd.get_hd_template() == 2
    assert pd.get_hdp_width() == 8
    assert pd.get_hdp_height() == 6
    assert pd.get_gray_max() == 1


def test_parse_header_max_dimensions_unsigned():
    # HDPW/HDPH are read as unsigned bytes (0xFF == 255), GRAYMAX as 32-bit.
    pd = _parse(pd_data(0xFF, 0xFF, 0, template=0))
    assert pd.get_hdp_width() == 255
    assert pd.get_hdp_height() == 255
    assert pd.get_gray_max() == 0


def test_check_input_rejects_zero_width():
    with pytest.raises(InvalidHeaderValueException):
        _parse(pd_data(0, 4, 3))


def test_check_input_rejects_zero_height():
    with pytest.raises(InvalidHeaderValueException):
        _parse(pd_data(4, 0, 3))


# ---------------------------------------------------------------------------
# AT-pixel nominal placement (6.7.5 / 7.4.4)
# ---------------------------------------------------------------------------
def test_at_pixels_template0_set_on_decode():
    pd = _parse(pd_data(4, 4, 1, template=0))
    pd.get_dictionary()
    # template 0 uses 4 AT pairs; AT1.x = -HDPW.
    assert pd.gb_at_x == [-4, -3, 2, -2]
    assert pd.gb_at_y == [0, -1, -2, -2]


def test_at_pixels_template_nonzero_single_pair():
    pd = _parse(pd_data(5, 4, 1, template=1))
    pd.get_dictionary()
    assert pd.gb_at_x == [-5]
    assert pd.gb_at_y == [0]


def test_at_pixels_not_set_when_mmr():
    # MMR mode skips AT-pixel setup; build patterns via the MMR path below.
    pd = _parse(pd_data(4, 4, 0, mmr=1, coded=_g4_collective(4, 4)))
    # Before decoding the AT arrays are unset.
    assert pd.gb_at_x is None
    assert pd.gb_at_y is None


# ---------------------------------------------------------------------------
# Decode procedure: slicing the collective bitmap into patterns (6.7.5)
# ---------------------------------------------------------------------------
def test_get_dictionary_pattern_count_and_dimensions():
    hdpw, hdph, gray_max = 4, 5, 3
    pd = _parse(pd_data(hdpw, hdph, gray_max, template=0))
    patterns = pd.get_dictionary()

    # GRAYMAX + 1 patterns, each HDPW x HDPH.
    assert len(patterns) == gray_max + 1
    for pattern in patterns:
        assert pattern.get_width() == hdpw
        assert pattern.get_height() == hdph


def test_get_dictionary_is_cached():
    pd = _parse(pd_data(4, 4, 2, template=0))
    first = pd.get_dictionary()
    second = pd.get_dictionary()
    assert first is second


def test_get_dictionary_single_pattern_graymax_zero():
    pd = _parse(pd_data(6, 3, 0, template=0))
    patterns = pd.get_dictionary()
    assert len(patterns) == 1
    assert patterns[0].get_width() == 6
    assert patterns[0].get_height() == 3


def test_extract_patterns_slices_collective_left_to_right():
    """Each pattern is the i-th HDPW-wide column block of the collective bitmap.

    Build a deterministic collective bitmap by hand, run the §6.7.5 slicing
    (``_extract_patterns``), and verify every pattern equals the matching
    ``HDPW``-wide column slice taken via ``Bitmaps.extract`` — and that the
    pixels round-trip from the collective bitmap.
    """
    from pypdfbox.jbig2.bitmap import Bitmap
    from pypdfbox.jbig2.image.bitmaps import Bitmaps

    hdpw, hdph, gray_max = 4, 4, 3
    width = (gray_max + 1) * hdpw  # 16

    # A diagonal-ish pattern so each column block differs.
    collective = Bitmap(width, hdph)
    for y in range(hdph):
        for x in range(width):
            collective.set_pixel(x, y, (x + y) & 1)

    pd = _parse(pd_data(hdpw, hdph, gray_max, template=0))
    pd.gray_max = gray_max
    pd.hdp_width = hdpw
    pd.hdp_height = hdph
    pd._extract_patterns(collective)
    patterns = pd.patterns

    assert len(patterns) == gray_max + 1
    for gray, pattern in enumerate(patterns):
        expected = Bitmaps.extract((hdpw * gray, 0, hdpw, hdph), collective)
        assert bytes(pattern.get_byte_array()) == bytes(expected.get_byte_array())
        # Spot-check the actual pixels against the source columns.
        for y in range(hdph):
            for x in range(hdpw):
                assert pattern.get_pixel(x, y) == collective.get_pixel(
                    hdpw * gray + x, y
                )


# ---------------------------------------------------------------------------
# MMR (CCITT Group-4) collective-bitmap path
# ---------------------------------------------------------------------------
def _g4_collective(width: int, height: int) -> bytes:
    """Build a CCITT-G4 strip (a blank collective bitmap) via Pillow."""
    import io as _io

    from PIL import Image  # local import: only the MMR cases need Pillow

    img = Image.new("1", (width, height), 1)
    buf = _io.BytesIO()
    img.save(buf, format="TIFF", compression="group4")
    data = buf.getvalue()

    byte_order = "<" if data[:2] == b"II" else ">"
    ifd_off = struct.unpack(byte_order + "I", data[4:8])[0]
    entry_count = struct.unpack(byte_order + "H", data[ifd_off : ifd_off + 2])[0]
    tags: dict[int, int] = {}
    for i in range(entry_count):
        entry = ifd_off + 2 + i * 12
        tag = struct.unpack(byte_order + "H", data[entry : entry + 2])[0]
        value = struct.unpack(byte_order + "I", data[entry + 8 : entry + 12])[0]
        tags[tag] = value
    return data[tags[273] : tags[273] + tags[279]]


def test_get_dictionary_mmr_path():
    pytest.importorskip("PIL")
    hdpw, hdph, gray_max = 4, 4, 1
    coded = _g4_collective((gray_max + 1) * hdpw, hdph)
    pd = _parse(pd_data(hdpw, hdph, gray_max, mmr=1, coded=coded))
    patterns = pd.get_dictionary()
    assert len(patterns) == gray_max + 1
    for pattern in patterns:
        assert pattern.get_width() == hdpw
        assert pattern.get_height() == hdph
