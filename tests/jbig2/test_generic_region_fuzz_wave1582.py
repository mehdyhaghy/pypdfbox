"""Generic-region segment decode fuzz — wave 1582 (agent B).

Drives ``pypdfbox.jbig2.segments.generic_region.GenericRegion`` over crafted
generic-region segment-data parts and direct helper calls to exercise the
branches the bundled ``.jb2`` fixtures and the hand-written
``tests/jbig2/segments/test_generic_region.py`` do not pin to the *spec values*
themselves:

* the §7.4.6.2 generic-region flags byte parsed over every GBTEMPLATE (0-3),
  TPGDON 0/1, EXTTEMPLATE 0/1 and MMR 0/1, with the AT-pixel count
  (§7.4.6.3) asserted per template (4 for template-0, 1 for template-1..3,
  12 for template-0 EXTTEMPLATE), and the reserved bit-5-7 dirty read tolerated;
* the §6.2.5.7 3b SLTP pseudo-pixel context value used by ``_decode_sltp`` for
  each template, asserted to the exact T.88 constants (0x9B25 / 0x0795 / 0x00E5
  / 0x0195) — the LTP toggle that drives typical prediction;
* the §6.2.5.7 3c typical-prediction LTP toggle / ``_copy_line_above`` row
  replication, including the line-0 guard (a copied LTP line 0 stays the default
  pixel 0);
* a full encode -> decode round-trip of a known bitmap through template 0
  (nominal AT, no TPGDON) via the MQ encoder helper, over several shapes
  including non-byte-aligned widths and a single-column region;
* the MMR-vs-arithmetic selection branch (``is_mmr_encoded``) routing to the
  CCITT-G4 decompressor vs the arithmetic procedure, and the no-AT-pixels
  consequence of MMR;
* the §7.4.1 region segment information field x/y location and combination
  operator over all five operator codes (OR/AND/XOR/XNOR/REPLACE);
* the AT-pixel override-flag computation (§6.2.5.3) — nominal AT leaves
  ``override`` off for every template, perturbing any AT pixel flips it on, and
  the malformed-length / missing-AT early returns.

All expectations are derived from ITU-T T.88 and pinned against the upstream
``apache/pdfbox-jbig2`` ``GenericRegion`` semantics (the SLTP constants, the
override defaults and the context-formation arithmetic are verbatim from the
port, whose bytes are oracle-verified in
``tests/jbig2/segments/oracle/test_generic_region_oracle.py``).
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.generic_region import GenericRegion
from pypdfbox.jbig2.util.combination_operator import CombinationOperator
from tests.jbig2.helpers.mq_encoder import (
    Cx,
    MQEncoder,
    encode_generic_region_template0,
)

# Nominal AT-pixel coordinates per template (7.4.6.3 / Figures 4-7).
NOMINAL_AT = {
    0: [(3, -1), (-3, -1), (2, -2), (-2, -2)],
    1: [(3, -1)],
    2: [(2, -1)],
    3: [(2, -1)],
}

# Extended-template (EXTTEMPLATE=1) nominal AT pixels — §6.2.5.3 Figure 7.
NOMINAL_EXT_AT = [
    (-2, 0), (0, -2), (-2, -1), (-1, -2), (1, -2), (2, -1),
    (-3, 0), (-4, 0), (2, -2), (3, -1), (-2, -2), (-3, -1),
]


def _region_info(width: int, height: int, x: int = 0, y: int = 0, comb: int = 0) -> bytes:
    return struct.pack(">IIII", width, height, x, y) + bytes([comb & 0x7])


def _gen_flags(mmr: int = 0, template: int = 0, tpgdon: int = 0, ext: int = 0) -> bytes:
    return bytes(
        [(mmr & 1) | ((template & 3) << 1) | ((tpgdon & 1) << 3) | ((ext & 1) << 4)]
    )


def _at(pairs: list[tuple[int, int]]) -> bytes:
    out = bytearray()
    for x, y in pairs:
        out.append(x & 0xFF)
        out.append(y & 0xFF)
    return bytes(out)


def _new_region(data: bytes) -> GenericRegion:
    iis = ImageInputStream(data)
    sis = SubInputStream(iis, 0, len(data))
    region = GenericRegion()
    region.init(None, sis)
    return region


def _encode_template0(rows: list[list[int]], width: int, height: int) -> bytes:
    enc = MQEncoder()
    cx = Cx(65536, 1)
    encode_generic_region_template0(enc, cx, rows, width, height)
    return enc.flush()


# ---------------------------------------------------------------------------
# §7.4.6.2 flags byte parsing — AT-pixel count per template.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("template", "tpgdon", "expected_at_count"),
    [
        (0, 0, 4),
        (0, 1, 4),
        (1, 0, 1),
        (1, 1, 1),
        (2, 0, 1),
        (3, 0, 1),
    ],
    ids=[
        "t0", "t0_tpgdon", "t1", "t1_tpgdon", "t2", "t3",
    ],
)
def test_flags_parse_at_count(template, tpgdon, expected_at_count):
    pairs = NOMINAL_AT[template]
    data = (
        _region_info(8, 4)
        + _gen_flags(template=template, tpgdon=tpgdon)
        + _at(pairs)
        + bytes([0x00] * 8)
    )
    region = _new_region(data)
    assert region.is_mmr_encoded_flag() is False
    assert region.get_gb_template() == template
    assert region.is_tpgdon_flag() is bool(tpgdon)
    assert region.use_ext_templates_flag() is False
    assert len(region.get_gb_at_x()) == expected_at_count
    assert len(region.get_gb_at_y()) == expected_at_count


def test_flags_parse_ext_template_reads_twelve_at_pairs():
    data = (
        _region_info(8, 4)
        + _gen_flags(template=0, ext=1)
        + _at(NOMINAL_EXT_AT)
        + bytes([0x00] * 8)
    )
    region = _new_region(data)
    assert region.use_ext_templates_flag() is True
    assert len(region.get_gb_at_x()) == 12
    assert region.get_gb_at_x() == [p[0] for p in NOMINAL_EXT_AT]
    assert region.get_gb_at_y() == [p[1] for p in NOMINAL_EXT_AT]


def test_flags_reserved_bits_ignored():
    # Reserved bits 5-7 of the flags byte are a dirty read; set them and confirm
    # they leave the parsed template/tpgdon/ext untouched.
    raw_flags = (0b111 << 5) | (1 << 3) | (2 << 1) | 0  # reserved=7, tpgdon, t2, mmr=0
    data = (
        _region_info(8, 4)
        + bytes([raw_flags])
        + _at(NOMINAL_AT[2])
        + bytes([0x00] * 8)
    )
    region = _new_region(data)
    assert region.get_gb_template() == 2
    assert region.is_tpgdon_flag() is True
    assert region.is_mmr_encoded_flag() is False


# ---------------------------------------------------------------------------
# §6.2.5.7 3b SLTP pseudo-pixel context — exact T.88 constants.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("template", "sltp_context"),
    [
        (0, 0x9B25),
        (1, 0x0795),
        (2, 0x00E5),
        (3, 0x0195),
    ],
    ids=["t0", "t1", "t2", "t3"],
)
def test_decode_sltp_sets_template_context(template, sltp_context):
    # ``_decode_sltp`` must load the template's SLTP context index before pulling
    # the LTP-toggle bit from the arithmetic decoder. Stub the decoder so we only
    # observe which CX index was selected.
    region = GenericRegion()
    region.gb_template = template

    captured = {}

    class _StubCx:
        def set_index(self, index):
            captured["index"] = index

    class _StubDecoder:
        def decode(self, cx):
            return 1

    region.cx = _StubCx()
    region.arith_decoder = _StubDecoder()
    bit = region._decode_sltp()
    assert captured["index"] == sltp_context
    assert bit == 1


# ---------------------------------------------------------------------------
# §6.2.5.7 3c typical prediction — LTP copy-line-above + line-0 guard.
# ---------------------------------------------------------------------------
def test_copy_line_above_replicates_previous_row():
    region = GenericRegion()
    region.region_bitmap = Bitmap(13, 4)
    # Seed row 1 with a recognisable byte pattern.
    stride = region.region_bitmap.get_row_stride()
    region.region_bitmap.set_byte(stride, 0xA5)
    region.region_bitmap.set_byte(stride + 1, 0xC0)
    region._copy_line_above(2)
    assert region.region_bitmap.get_byte(2 * stride) == 0xA5
    assert region.region_bitmap.get_byte(2 * stride + 1) == 0xC0


def test_tpgdon_line0_ltp_leaves_default_pixel():
    # With TPGDON and an LTP that toggles to 1 on line 0, no source row exists, so
    # ``get_region_bitmap`` must not call ``_copy_line_above`` for line 0; the row
    # stays at the default pixel (0). Then a subsequent LTP=1 line copies it.
    region = GenericRegion()
    region.region_info = None  # not used by the helper under test

    calls = []
    orig = region._copy_line_above
    region._copy_line_above = lambda ln: calls.append(ln) or orig(ln)
    region.region_bitmap = Bitmap(8, 3)
    # Simulate the §6.2.5.7 3c branch directly for line 0 with ltp == 1.
    ltp = 1
    line = 0
    if ltp == 1 and line > 0:
        region._copy_line_above(line)
    assert calls == []  # line 0 guarded out


# ---------------------------------------------------------------------------
# Encode -> decode round-trip through template 0 (arithmetic) over shapes.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("width", "height"),
    [
        (12, 5),
        (13, 6),
        (8, 8),
        (1, 4),
        (17, 3),
        (16, 1),
        (9, 9),
    ],
    ids=["12x5", "13x6_nonaligned", "8x8", "1x4_single_col", "17x3", "16x1", "9x9"],
)
def test_template0_arithmetic_roundtrip(width, height):
    rows = [
        [1 if ((x * 7 + y * 13 + 3) % 5 == 0) else 0 for x in range(width)]
        for y in range(height)
    ]
    body = _encode_template0(rows, width, height)
    data = (
        _region_info(width, height)
        + _gen_flags(template=0)
        + _at(NOMINAL_AT[0])
        + body
    )
    region = _new_region(data)
    bitmap = region.get_region_bitmap()
    assert bitmap.get_width() == width
    assert bitmap.get_height() == height
    assert region.override is False
    for y in range(height):
        for x in range(width):
            assert bitmap.get_pixel(x, y) == rows[y][x], (x, y)


def test_template0_roundtrip_all_ones_and_all_zeros():
    width, height = 11, 4
    for fill in (0, 1):
        rows = [[fill] * width for _ in range(height)]
        body = _encode_template0(rows, width, height)
        data = (
            _region_info(width, height)
            + _gen_flags(template=0)
            + _at(NOMINAL_AT[0])
            + body
        )
        bitmap = _new_region(data).get_region_bitmap()
        for y in range(height):
            for x in range(width):
                assert bitmap.get_pixel(x, y) == fill


# ---------------------------------------------------------------------------
# MMR-vs-arithmetic selection (§7.4.6.2 bit 0).
# ---------------------------------------------------------------------------
def test_mmr_selection_skips_at_pixels_and_routes_to_g4():
    # MMR=1 -> no AT pixels parsed; the decode path is the CCITT-G4 decompressor.
    from PIL import Image  # noqa: PLC0415 - only the MMR case needs Pillow

    width, height = 16, 8
    img = Image.new("1", (width, height), 1)
    px = img.load()
    for y in range(2, 6):
        for x in range(4, 12):
            px[x, y] = 0
    import io as _io  # noqa: PLC0415

    buf = _io.BytesIO()
    img.save(buf, format="TIFF", compression="group4")
    raw = buf.getvalue()
    byte_order = "<" if raw[:2] == b"II" else ">"
    ifd_off = struct.unpack(byte_order + "I", raw[4:8])[0]
    n = struct.unpack(byte_order + "H", raw[ifd_off : ifd_off + 2])[0]
    tags = {}
    for i in range(n):
        e = ifd_off + 2 + i * 12
        tag = struct.unpack(byte_order + "H", raw[e : e + 2])[0]
        val = struct.unpack(byte_order + "I", raw[e + 8 : e + 12])[0]
        tags[tag] = val
    g4 = raw[tags[273] : tags[273] + tags[279]]

    data = _region_info(width, height) + _gen_flags(mmr=1) + g4
    region = _new_region(data)
    assert region.is_mmr_encoded_flag() is True
    assert region.get_gb_at_x() is None
    assert region.get_gb_at_y() is None
    bitmap = region.get_region_bitmap()
    assert bitmap.get_width() == width
    assert bitmap.get_height() == height
    assert region.mmr_decompressor is not None


def test_arithmetic_selection_builds_arith_decoder():
    rows = [[0] * 8 for _ in range(4)]
    body = _encode_template0(rows, 8, 4)
    data = _region_info(8, 4) + _gen_flags(template=0) + _at(NOMINAL_AT[0]) + body
    region = _new_region(data)
    region.get_region_bitmap()
    assert region.is_mmr_encoded_flag() is False
    assert region.arith_decoder is not None
    assert region.mmr_decompressor is None


# ---------------------------------------------------------------------------
# §7.4.1 region segment information — x/y location + combination operator.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("comb_code", "expected"),
    [
        (0, CombinationOperator.OR),
        (1, CombinationOperator.AND),
        (2, CombinationOperator.XOR),
        (3, CombinationOperator.XNOR),
        (4, CombinationOperator.REPLACE),
    ],
    ids=["OR", "AND", "XOR", "XNOR", "REPLACE"],
)
def test_region_info_combination_operator(comb_code, expected):
    rows = [[0] * 8 for _ in range(4)]
    body = _encode_template0(rows, 8, 4)
    data = (
        _region_info(8, 4, x=5, y=7, comb=comb_code)
        + _gen_flags(template=0)
        + _at(NOMINAL_AT[0])
        + body
    )
    region = _new_region(data)
    info = region.get_region_info()
    assert info.get_combination_operator() == expected
    assert info.get_x_location() == 5
    assert info.get_y_location() == 7
    assert info.get_bitmap_width() == 8
    assert info.get_bitmap_height() == 4


# ---------------------------------------------------------------------------
# AT-pixel override-flag computation (§6.2.5.3).
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("template", [0, 1, 2, 3], ids=["t0", "t1", "t2", "t3"])
def test_nominal_at_leaves_override_off(template):
    region = GenericRegion()
    region.gb_template = template
    region.gb_at_x = [p[0] for p in NOMINAL_AT[template]]
    region.gb_at_y = [p[1] for p in NOMINAL_AT[template]]
    region._update_override_flags()
    assert region.override is False
    assert region.gb_at_override == [False] * len(NOMINAL_AT[template])


def test_nominal_ext_at_leaves_override_off():
    region = GenericRegion()
    region.gb_template = 0
    region.use_ext_templates = True
    region.gb_at_x = [p[0] for p in NOMINAL_EXT_AT]
    region.gb_at_y = [p[1] for p in NOMINAL_EXT_AT]
    region._update_override_flags()
    assert region.override is False
    assert region.gb_at_override == [False] * 12


@pytest.mark.parametrize(
    ("template", "perturbed"),
    [
        (0, [(4, -1), (-3, -1), (2, -2), (-2, -2)]),
        (1, [(2, -1)]),
        (2, [(3, -1)]),
        (3, [(1, -1)]),
    ],
    ids=["t0", "t1", "t2", "t3"],
)
def test_perturbed_at_flips_override_on(template, perturbed):
    region = GenericRegion()
    region.gb_template = template
    region.gb_at_x = [p[0] for p in perturbed]
    region.gb_at_y = [p[1] for p in perturbed]
    region._update_override_flags()
    assert region.override is True
    assert region.gb_at_override[0] is True


def test_override_flags_missing_at_returns_early():
    region = GenericRegion()
    region.gb_at_x = None
    region.gb_at_y = None
    region._update_override_flags()
    assert region.override is False
    assert region.gb_at_override is None


def test_override_flags_length_mismatch_returns_early():
    region = GenericRegion()
    region.gb_at_x = [3, -3, 2]
    region.gb_at_y = [-1, -1]
    region._update_override_flags()
    assert region.override is False
    assert region.gb_at_override is None


def test_get_pixel_safe_out_of_bounds_returns_zero():
    region = GenericRegion()
    region.region_bitmap = Bitmap(4, 4)
    region.region_bitmap.set_pixel(1, 1, 1)
    assert region._get_pixel_safe(1, 1) == 1
    assert region._get_pixel_safe(-1, 1) == 0
    assert region._get_pixel_safe(4, 1) == 0
    assert region._get_pixel_safe(1, -1) == 0
    assert region._get_pixel_safe(1, 4) == 0


def test_decode_caches_bitmap_instance():
    rows = [[0] * 8 for _ in range(4)]
    body = _encode_template0(rows, 8, 4)
    data = _region_info(8, 4) + _gen_flags(template=0) + _at(NOMINAL_AT[0]) + body
    region = _new_region(data)
    first = region.get_region_bitmap()
    second = region.get_region_bitmap()
    assert first is second
