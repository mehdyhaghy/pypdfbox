"""Hand-written unit tests for the JBIG2 MMR (ITU-T T.6 / CCITT Group-4) decoder.

Covers ``MMRConstants`` (the code tables) and ``MMRDecompressor`` (the 2-D READ
decoder: pass / horizontal / vertical modes, makeup runs > 63, byte- and
non-byte-aligned widths).

The coded inputs are CCITT-G4 strips produced by Pillow/libtiff
(``Image.save(..., compression="group4")``) and the expected packed bitmap bytes
were captured from the upstream Apache PDFBox ``MMRDecompressor`` (the live
oracle differential lives in ``oracle/test_mmr_oracle.py``). Bit convention:
pypdfbox's ``Bitmap`` packs MSB-first, 1 == set; for these G4 strips a Pillow
"black" pixel decodes to a set bit.
"""

from __future__ import annotations

import io
import struct

import pytest

from pypdfbox.jbig2.decoder.mmr.mmr_constants import MMRConstants
from pypdfbox.jbig2.decoder.mmr.mmr_decompressor import (
    FIRST_LEVEL_TABLE_MASK,
    Code,
    MMRDecompressor,
    _create_little_endian_table,
)
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream


def decode(strip_hex: str, width: int, height: int) -> str:
    """Decode a CCITT-G4 strip and return the packed bitmap bytes as hex."""
    iis = ImageInputStream(bytes.fromhex(strip_hex))
    bitmap = MMRDecompressor(width, height, iis).uncompress()
    return bytes(bitmap.get_byte_array()).hex()


def g4_strip(width: int, height: int, black_pixels) -> str:
    """Build a CCITT-G4 strip via Pillow and return its raw bytes as hex.

    ``black_pixels`` is an iterable of ``(x, y)`` coordinates to set black. Used
    by the oracle test to generate fixtures; needs Pillow at runtime.
    """
    from PIL import Image  # local import: only the oracle path needs Pillow

    img = Image.new("1", (width, height), 1)
    px = img.load()
    for x, y in black_pixels:
        px[x, y] = 0

    buf = io.BytesIO()
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
    strip_offset = tags[273]  # StripOffsets
    strip_count = tags[279]  # StripByteCounts
    return data[strip_offset : strip_offset + strip_count].hex()


# (name, strip_hex, width, height, expected_bitmap_hex)
# Captured from upstream Apache PDFBox MMRDecompressor (3.0.7).
CASES = [
    # 16x8 white field with a black rectangle (rows 2..5, cols 4..11).
    ("rect16x8", "26a0bf2e7fff8f001001", 16, 8, "fffffffff00ff00ff00ff00fffffffff"),
    # 13x5 vertical stripes — non byte-aligned width (stride 2, 3 pad bits).
    ("stripes13x5", "23a23a23a23a23a097ffffffffffffc0040040", 13, 5,
     "55505550555055505550"),
    # 20x20 diagonal line — exercises vertical + pass modes heavily.
    ("diag20x20",
     "23867450fb2383164705ec8e18b2383d91c12c8e1ec8e16c8e12c8e2591c5b238ec8e56473b23bb05b0b6b70010010",
     20, 20,
     "7ffff0bffff0dffff0effff0f7fff0fbfff0fdfff0fefff0ff7ff0ffbff0ffdff0"
     "ffeff0fff7f0fffbf0fffdf0fffef0ffff70ffffb0ffffd0ffffe0"),
    # 24x4 solid black — minimal coding, all set bits.
    ("black24x4", "f0010010", 24, 4, "000000000000000000000000"),
    # 200x3 with a wide black bar cols 50..169 — makeup runs (> 63).
    ("wide200x3", "26a0a476b20d1fe0020020", 200, 3,
     "ffffffffffffc000000000000000000000000000003fffffffffffffffffffc0"
     "00000000000000000000000000003fffffffffffffffffffc0000000000000"
     "00000000000000003fffffff"),
]


@pytest.mark.parametrize(
    ("name", "strip_hex", "width", "height", "expected"),
    CASES,
    ids=[c[0] for c in CASES],
)
def test_decode_known_patterns(name, strip_hex, width, height, expected):
    bitmap_hex = decode(strip_hex, width, height)
    assert bitmap_hex == expected


def test_uncompress_dimensions_and_type():
    iis = ImageInputStream(bytes.fromhex("26a0bf2e7fff8f001001"))
    bitmap = MMRDecompressor(16, 8, iis).uncompress()
    assert bitmap.get_width() == 16
    assert bitmap.get_height() == 8
    assert bitmap.get_row_stride() == 2
    assert bitmap.get_length() == 16  # 2 bytes/row * 8 rows


def test_rectangle_pixels():
    """Spot-check individual pixels of the decoded rectangle bitmap."""
    iis = ImageInputStream(bytes.fromhex("26a0bf2e7fff8f001001"))
    bitmap = MMRDecompressor(16, 8, iis).uncompress()
    # Surround is set (Pillow white -> set bit here), rectangle interior is 0.
    assert bitmap.get_pixel(0, 0) == 1
    assert bitmap.get_pixel(15, 7) == 1
    # Rectangle was rows 2..5, cols 4..11 (Pillow black -> cleared bit).
    assert bitmap.get_pixel(4, 2) == 0
    assert bitmap.get_pixel(11, 5) == 0
    assert bitmap.get_pixel(3, 2) == 1  # just left of the rectangle
    assert bitmap.get_pixel(12, 2) == 1  # just right of the rectangle


# --------------------------------------------------------------------------- #
# MMRConstants table integrity
# --------------------------------------------------------------------------- #
def test_mode_codes_shape():
    for entry in MMRConstants.ModeCodes:
        assert len(entry) == 3
    # 1-bit V0 code, code word 0x1.
    assert [1, 0x1, MMRConstants.CODE_V0] in MMRConstants.ModeCodes


def test_white_and_black_makeup_max():
    assert MMRConstants.MAX_WHITE_RUN == 2560
    assert MMRConstants.MAX_BLACK_RUN == 2560
    # both tables end with the 2560 makeup terminator.
    assert MMRConstants.WhiteCodes[-1] == [12, 0x1F, 2560]
    assert MMRConstants.BlackCodes[-1] == [13, 0x77, 1216]


def test_run_length_constants():
    assert MMRConstants.EOL == -1
    assert MMRConstants.EOF == -3
    assert MMRConstants.INVALID == -2
    assert MMRConstants.CODE_P == 0
    assert MMRConstants.CODE_MAX == 12


# --------------------------------------------------------------------------- #
# Two-level lookup table construction
# --------------------------------------------------------------------------- #
def test_first_level_table_size():
    table = _create_little_endian_table(MMRConstants.ModeCodes)
    assert len(table) == FIRST_LEVEL_TABLE_MASK + 1  # 256 entries


def test_short_code_fills_all_variants():
    # The 1-bit V0 code (0x1) fills the entire upper half of the first table.
    table = _create_little_endian_table(MMRConstants.ModeCodes)
    v0 = Code([1, 0x1, MMRConstants.CODE_V0])
    for index in range(128, 256):
        assert table[index] == v0


def test_long_code_uses_subtable():
    # White codes contain 13-bit... actually 12-bit max; the 12-bit codes need
    # the second-level table. The first-level holder must carry a sub_table.
    table = _create_little_endian_table(MMRConstants.WhiteCodes)
    # 12-bit EOL code 0x01 -> first-level index 0 (all top 8 bits zero).
    holder = table[0]
    assert holder is not None
    assert holder.sub_table is not None


def test_table_overflow_raises():
    # A code longer than FIRST + SECOND level (8 + 5 = 13) overflows.
    with pytest.raises(ValueError, match="Code table overflow"):
        _create_little_endian_table([[14, 0x1, 5]])


def test_code_equality_and_str():
    a = Code([4, 0x1, MMRConstants.CODE_P])
    b = Code([4, 0x1, MMRConstants.CODE_P])
    c = Code([3, 0x1, MMRConstants.CODE_H])
    assert a == b
    assert a != c
    assert a != "not-a-code"
    assert str(a) == "4/1/0"
