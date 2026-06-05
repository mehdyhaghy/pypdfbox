"""Hand-written unit tests for the JBIG2 generic-region decoder.

Covers ``GenericRegion`` parsing (region segment info + flags + AT pixels) and
decoding in both the arithmetic mode (templates 0-3, TPGDON typical-prediction,
AT-pixel override) and the MMR (CCITT Group-4) mode.

The crafted inputs are the EXACT segment-data part of an immediate
generic-region segment (everything after the segment header): the region
segment information field, the generic-region flags byte, the AT-pixel
coordinates (arithmetic mode only), then the coded data. Expected packed
bitmap bytes were captured from the upstream Apache PDFBox ``GenericRegion``
(3.0.7); the live oracle differential lives in
``tests/jbig2/segments/oracle/test_generic_region_oracle.py``.

Bit convention: pypdfbox's ``Bitmap`` packs MSB-first, 1 == set. The arithmetic
coded payload (``84c73b6a2100000000``) is an arbitrary but fixed byte string;
because the MQ decoder is deterministic, feeding identical coded bytes to both
the upstream and the ported decoder yields identical bitmaps — so the captured
expectations double as a bit-exact context-computation parity fixture.
"""

from __future__ import annotations

import io
import struct

import pytest

from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.generic_region import GenericRegion
from pypdfbox.jbig2.util.combination_operator import CombinationOperator

# Arbitrary but fixed arithmetic-coded payload used across the template cases.
CODED = bytes([0x84, 0xC7, 0x3B, 0x6A, 0x21, 0x00, 0x00, 0x00])

# Nominal AT-pixel coordinates per template (7.4.6.3 / Figures 4-7).
NOMINAL_AT = {
    0: [(3, -1), (-3, -1), (2, -2), (-2, -2)],
    1: [(3, -1)],
    2: [(2, -1)],
    3: [(2, -1)],
}


def _region_info(width: int, height: int, x: int = 0, y: int = 0) -> bytes:
    """Region segment information field, 7.4.1 (combination operator = OR=0)."""
    return struct.pack(">IIII", width, height, x, y) + bytes([0x00])


def _gen_flags(mmr: int = 0, template: int = 0, tpgdon: int = 0, ext: int = 0) -> bytes:
    """Generic region segment flags byte, 7.4.6.2.

    bit0=MMR, bit1-2=GBTEMPLATE, bit3=TPGDON, bit4=EXTTEMPLATE, bit5-7 reserved.
    """
    return bytes(
        [(mmr & 1) | ((template & 3) << 1) | ((tpgdon & 1) << 3) | ((ext & 1) << 4)]
    )


def _at(pairs: list[tuple[int, int]]) -> bytes:
    """Pack AT-pixel coordinates as signed bytes (x, y per pair)."""
    out = bytearray()
    for x, y in pairs:
        out.append(x & 0xFF)
        out.append(y & 0xFF)
    return bytes(out)


def _g4_strip(width: int, height: int, black_pixels) -> bytes:
    """Build a CCITT-G4 strip via Pillow; return its raw coded bytes.

    ``black_pixels`` is an iterable of ``(x, y)`` coordinates to set black.
    Needs Pillow at runtime (skipped if unavailable).
    """
    from PIL import Image  # local import: only the MMR cases need Pillow

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
    return data[tags[273] : tags[273] + tags[279]]


def _decode(segment_data: bytes) -> GenericRegion:
    """Drive ``GenericRegion.init`` + ``get_region_bitmap`` on a data buffer."""
    iis = ImageInputStream(segment_data)
    sis = SubInputStream(iis, 0, len(segment_data))
    region = GenericRegion()
    region.init(None, sis)
    region.get_region_bitmap()
    return region


def _decode_hex(segment_data: bytes) -> str:
    region = _decode(segment_data)
    return bytes(region.get_region_bitmap().get_byte_array()).hex()


# ---------------------------------------------------------------------------
# Header parsing
# ---------------------------------------------------------------------------
def test_parse_header_arithmetic_template0():
    data = _region_info(13, 6) + _gen_flags(template=0) + _at(NOMINAL_AT[0]) + CODED
    iis = ImageInputStream(data)
    sis = SubInputStream(iis, 0, len(data))
    region = GenericRegion()
    region.init(None, sis)

    assert region.is_mmr_encoded_flag() is False
    assert region.get_gb_template() == 0
    assert region.is_tpgdon_flag() is False
    assert region.use_ext_templates_flag() is False
    assert region.get_gb_at_x() == [3, -3, 2, -2]
    assert region.get_gb_at_y() == [-1, -1, -2, -2]

    info = region.get_region_info()
    assert info.get_bitmap_width() == 13
    assert info.get_bitmap_height() == 6
    assert info.get_combination_operator() == CombinationOperator.OR


def test_parse_header_template_nonzero_reads_single_at_pair():
    data = _region_info(8, 4) + _gen_flags(template=2) + _at([(2, -1)]) + CODED
    iis = ImageInputStream(data)
    sis = SubInputStream(iis, 0, len(data))
    region = GenericRegion()
    region.init(None, sis)

    assert region.get_gb_template() == 2
    # Only one AT pair for templates 1-3.
    assert region.get_gb_at_x() == [2]
    assert region.get_gb_at_y() == [-1]


def test_parse_header_mmr_reads_no_at_pixels():
    g4 = _g4_strip(16, 8, [(x, y) for y in range(2, 6) for x in range(4, 12)])
    data = _region_info(16, 8) + _gen_flags(mmr=1) + g4
    iis = ImageInputStream(data)
    sis = SubInputStream(iis, 0, len(data))
    region = GenericRegion()
    region.init(None, sis)

    assert region.is_mmr_encoded_flag() is True
    assert region.get_gb_at_x() is None
    assert region.get_gb_at_y() is None


def test_parse_header_tpgdon_flag():
    data = _region_info(10, 5) + _gen_flags(template=0, tpgdon=1) + _at(NOMINAL_AT[0]) + CODED
    iis = ImageInputStream(data)
    sis = SubInputStream(iis, 0, len(data))
    region = GenericRegion()
    region.init(None, sis)
    assert region.is_tpgdon_flag() is True


def test_parse_header_ext_templates_reads_twelve_at_pairs():
    pairs = [(-2, 0), (0, -2), (-2, -1), (-1, -2), (1, -2), (2, -1),
             (-3, 0), (-4, 0), (2, -2), (3, -1), (-2, -2), (-3, -1)]
    data = _region_info(8, 4) + _gen_flags(template=0, ext=1) + _at(pairs) + CODED
    iis = ImageInputStream(data)
    sis = SubInputStream(iis, 0, len(data))
    region = GenericRegion()
    region.init(None, sis)
    assert region.use_ext_templates_flag() is True
    assert len(region.get_gb_at_x()) == 12
    assert len(region.get_gb_at_y()) == 12


# ---------------------------------------------------------------------------
# Arithmetic decode — templates 0-3 (nominal AT), 13x6 (non-byte-aligned width)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("template", "expected"),
    [
        (0, "0000512081c84b38b4600458"),
        (1, "00005558aa30be9053e02838"),
        (2, "000055503cc83a7813e82a60"),
        (3, "0000512081c88050cbc03728"),
    ],
    ids=["template0", "template1", "template2", "template3"],
)
def test_arithmetic_decode_templates(template, expected):
    data = (
        _region_info(13, 6)
        + _gen_flags(template=template)
        + _at(NOMINAL_AT[template])
        + CODED
    )
    region = _decode(data)
    bitmap = region.get_region_bitmap()
    assert bitmap.get_width() == 13
    assert bitmap.get_height() == 6
    assert bitmap.get_row_stride() == 2
    assert bytes(bitmap.get_byte_array()).hex() == expected


def test_arithmetic_decode_tpgdon_typical_prediction():
    # With TPGDON on, the LTP toggles each line; for this coded payload every
    # line replicates, yielding a repeated row pattern.
    data = (
        _region_info(10, 5) + _gen_flags(template=0, tpgdon=1) + _at(NOMINAL_AT[0]) + CODED
    )
    assert _decode_hex(data) == "05c005c005c005c005c0"


@pytest.mark.parametrize(
    ("template", "pairs", "width", "expected"),
    [
        (0, [(4, -1), (-3, -1), (2, -2), (-2, -2)], 12, "0000289060702960"),
        (1, [(2, -1)], 9, "0000050003000f00"),
        (2, [(3, -1)], 9, "000005000b001780"),
        (3, [(3, -1)], 9, "0000050003000480"),
    ],
    ids=["template0", "template1", "template2", "template3"],
)
def test_arithmetic_decode_at_override(template, pairs, width, expected):
    # Non-nominal AT pixels trigger the override path in each template.
    data = _region_info(width, 4) + _gen_flags(template=template) + _at(pairs) + CODED
    region = _decode(data)
    assert region.override is True
    assert bytes(region.get_region_bitmap().get_byte_array()).hex() == expected


# Extended-template (EXTTEMPLATE=1) nominal AT pixels — §6.2.5.3 Figure 7.
NOMINAL_EXT_AT = [
    (-2, 0), (0, -2), (-2, -1), (-1, -2), (1, -2), (2, -1),
    (-3, 0), (-4, 0), (2, -2), (3, -1), (-2, -2), (-3, -1),
]


def test_ext_template_decode_nominal():
    # GBTEMPLATE 0 with EXTTEMPLATE=1 routes the decode through the 16-context
    # template0b body. Nominal AT pixels keep the override flags off. Bytes
    # captured from the upstream 3.0.7 GenericRegion (see the ext_template_*
    # oracle cases for the live differential).
    data = _region_info(13, 6) + _gen_flags(template=0, ext=1) + _at(NOMINAL_EXT_AT) + CODED
    region = _decode(data)
    bitmap = region.get_region_bitmap()
    assert bitmap.get_width() == 13
    assert bitmap.get_height() == 6
    assert region.use_ext_templates_flag() is True
    assert region.override is False
    assert bytes(bitmap.get_byte_array()).hex() == "0000512081c84b38b4600458"


def test_ext_template_decode_at_override():
    # Perturbing AT0 from (-2,0) to (-3,0) flips override on and exercises the
    # 12-pixel template0b override path.
    pairs = [(-3, 0)] + NOMINAL_EXT_AT[1:]
    data = _region_info(13, 6) + _gen_flags(template=0, ext=1) + _at(pairs) + CODED
    region = _decode(data)
    assert region.use_ext_templates_flag() is True
    assert region.override is True
    assert bytes(region.get_region_bitmap().get_byte_array()).hex() == (
        "00004200c280cf000c084be0"
    )


def test_decode_caches_bitmap():
    data = _region_info(13, 6) + _gen_flags(template=0) + _at(NOMINAL_AT[0]) + CODED
    region = _decode(data)
    first = region.get_region_bitmap()
    second = region.get_region_bitmap()
    assert first is second


# ---------------------------------------------------------------------------
# MMR (CCITT Group-4) decode
# ---------------------------------------------------------------------------
def test_mmr_decode_rectangle():
    black = [(x, y) for y in range(2, 6) for x in range(4, 12)]
    data = _region_info(16, 8) + _gen_flags(mmr=1) + _g4_strip(16, 8, black)
    region = _decode(data)
    bitmap = region.get_region_bitmap()
    assert bitmap.get_width() == 16
    assert bitmap.get_height() == 8
    assert bytes(bitmap.get_byte_array()).hex() == "fffffffff00ff00ff00ff00fffffffff"


def test_mmr_decode_stripes_non_byte_aligned():
    black = [(x, y) for y in range(5) for x in range(0, 13, 2)]
    data = _region_info(13, 5) + _gen_flags(mmr=1) + _g4_strip(13, 5, black)
    region = _decode(data)
    bitmap = region.get_region_bitmap()
    assert bitmap.get_width() == 13
    assert bitmap.get_height() == 5
    assert bitmap.get_row_stride() == 2
    assert bytes(bitmap.get_byte_array()).hex() == "55505550555055505550"


def test_mmr_pixel_values_match_source():
    # Verify against the source image at the pixel level. The G4 strip from
    # libtiff encodes Pillow "black" (set) source pixels as a CLEARED bit in the
    # decompressed bitmap and "white" source pixels as a SET bit (matching the
    # upstream MMRDecompressor output captured in the MMR unit tests), so the
    # decoded polarity is the inverse of the Pillow source.
    black = {(x, y) for y in range(2, 6) for x in range(4, 12)}
    data = _region_info(16, 8) + _gen_flags(mmr=1) + _g4_strip(16, 8, black)
    bitmap = _decode(data).get_region_bitmap()
    for y in range(8):
        for x in range(16):
            assert bitmap.get_pixel(x, y) == (0 if (x, y) in black else 1)
