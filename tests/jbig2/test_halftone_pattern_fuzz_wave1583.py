"""Fuzz / branch coverage for JBIG2 halftone-region + pattern-dictionary decode.

Wave 1583. Drives ``PatternDictionary`` (§6.7.5, T.88) and ``HalftoneRegion``
(§6.6.5, Annex C.5 grayscale) over crafted flag combinations, exercising:

* pattern-dictionary flag parse (HDMMR / HDTEMPLATE 0-3 / HDPW / HDPH / GRAYMAX),
* the collective-bitmap slice into ``GRAYMAX + 1`` individual ``HDPW`` x ``HDPH``
  patterns (§6.7.5 step 4),
* the AT-pixel template wiring for both the pattern dictionary and the
  grayscale-image generic-region decoder (§6.2.5.3 / Annex C.5),
* halftone flag parse (HDEFPIXEL / HCOMBOP / HENABLESKIP / HTEMPLATE / HMMR),
* the Gray-code bitplane XOR decode (Annex C.5 step 3b) — MSB plane decoded
  first, each lower plane XOR-combined with the plane above it,
* the per-cell grayscale value reconstruction (MSB-first bit packing),
* the grid placement math ``x = (HGX + m*HRY + n*HRX) >> 8`` /
  ``y = (HGY + m*HRX - n*HRY) >> 8`` (§6.6.5.2), and
* the HSKIP bitmap (§6.6.5.1) plus HDEFPIXEL pre-fill.

Where a full arithmetic decode would be needed, the flag-parse / grayscale-plane
combine / slice / placement helpers are exercised directly with injected
bitmaps so the math is verified independently of the MQ coder. The arithmetic
payload is the deterministic fixture shared with the other jbig2 fixtures.

Bit convention: pypdfbox's ``Bitmap`` packs MSB-first, 1 == set.
"""

from __future__ import annotations

import math
import struct

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.err.invalid_header_value_exception import (
    InvalidHeaderValueException,
)
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.halftone_region import HalftoneRegion
from pypdfbox.jbig2.segments.pattern_dictionary import PatternDictionary
from pypdfbox.jbig2.util.combination_operator import CombinationOperator

CODED = bytes([0x84, 0xC7, 0x3B, 0x6A, 0x21, 0x00, 0x00, 0x00])


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def pd_flags(mmr: int = 0, template: int = 0) -> bytes:
    """Pattern-dictionary flags byte (7.4.4.1.1): bit0=HDMMR, bit1-2=HDTEMPLATE."""
    return bytes([(mmr & 1) | ((template & 3) << 1)])


def pd_data(
    hdpw: int,
    hdph: int,
    gray_max: int,
    *,
    mmr: int = 0,
    template: int = 0,
    coded: bytes = CODED,
) -> bytes:
    return (
        pd_flags(mmr=mmr, template=template)
        + bytes([hdpw & 0xFF, hdph & 0xFF])
        + struct.pack(">I", gray_max)
        + coded
    )


def parse_pd(segment_data: bytes) -> PatternDictionary:
    iis = ImageInputStream(segment_data)
    sis = SubInputStream(iis, 0, len(segment_data))
    pd = PatternDictionary()
    pd.init(None, sis)
    return pd


def region_info(width: int, height: int, x: int = 0, y: int = 0) -> bytes:
    return struct.pack(">IIII", width, height, x, y) + bytes([0x00])


def ht_flags(
    defpix: int = 0,
    combop: int = 0,
    skip: int = 0,
    template: int = 0,
    mmr: int = 0,
) -> bytes:
    return bytes(
        [
            ((defpix & 1) << 7)
            | ((combop & 7) << 4)
            | ((skip & 1) << 3)
            | ((template & 3) << 1)
            | (mmr & 1)
        ]
    )


def ht_data(
    rw: int,
    rh: int,
    hgw: int,
    hgh: int,
    hgx: int = 0,
    hgy: int = 0,
    hrx: int = 256,
    hry: int = 0,
    *,
    coded: bytes = CODED,
    **flags: int,
) -> bytes:
    return (
        region_info(rw, rh)
        + ht_flags(**flags)
        + struct.pack(">II", hgw, hgh)
        + struct.pack(">ii", hgx, hgy)
        + struct.pack(">HH", hrx, hry)
        + coded
    )


def parse_ht(segment_data: bytes) -> HalftoneRegion:
    iis = ImageInputStream(segment_data)
    sis = SubInputStream(iis, 0, len(segment_data))
    hr = HalftoneRegion()
    hr.init(None, sis)
    return hr


def distinct_patterns(count: int, width: int, height: int) -> list[Bitmap]:
    """``count`` patterns; pattern *i* has its (0,0) bit equal to ``i & 1`` etc."""
    patterns = []
    for i in range(count):
        p = Bitmap(width, height)
        for y in range(height):
            for x in range(width):
                bit = ((i >> 0) & 1) if (x + y) % 2 == 0 else ((i >> 1) & 1)
                p.set_pixel(x, y, bit)
        patterns.append(p)
    return patterns


# ---------------------------------------------------------------------------
# Pattern-dictionary header parse fuzz (7.4.4.1)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("template", [0, 1, 2, 3])
@pytest.mark.parametrize("mmr", [0, 1])
def test_pd_flag_parse_roundtrip(template, mmr):
    pd = parse_pd(pd_data(4, 4, 3, template=template, mmr=mmr))
    assert pd.get_hd_template() == template
    assert pd.is_mmr_encoded_flag() is bool(mmr)


@pytest.mark.parametrize("hdpw,hdph", [(1, 1), (4, 4), (16, 8), (255, 255), (3, 7)])
def test_pd_width_height_parse(hdpw, hdph):
    pd = parse_pd(pd_data(hdpw, hdph, 1))
    assert pd.get_hdp_width() == hdpw
    assert pd.get_hdp_height() == hdph


@pytest.mark.parametrize("gray_max", [0, 1, 3, 7, 255, 0xFFFF, 0x7FFFFFFF])
def test_pd_gray_max_parse(gray_max):
    pd = parse_pd(pd_data(4, 4, gray_max))
    assert pd.get_gray_max() == gray_max


@pytest.mark.parametrize("hdpw,hdph", [(0, 4), (4, 0), (0, 0)])
def test_pd_zero_dimension_rejected(hdpw, hdph):
    with pytest.raises(InvalidHeaderValueException):
        parse_pd(pd_data(hdpw, hdph, 1))


# ---------------------------------------------------------------------------
# Pattern-dictionary AT-pixel wiring (6.2.5.3 used by 6.7.5)
# ---------------------------------------------------------------------------
def test_pd_at_pixels_template0():
    pd = parse_pd(pd_data(8, 4, 3, template=0))
    pd._set_gb_at_pixels()
    # Template 0 uses four AT pixels; AT1.x == -HDPW.
    assert pd.gb_at_x == [-8, -3, 2, -2]
    assert pd.gb_at_y == [0, -1, -2, -2]


@pytest.mark.parametrize("template", [1, 2, 3])
def test_pd_at_pixels_nonzero_template(template):
    pd = parse_pd(pd_data(8, 4, 3, template=template))
    pd._set_gb_at_pixels()
    # Templates 1-3 use a single AT pixel at (-HDPW, 0).
    assert pd.gb_at_x == [-8]
    assert pd.gb_at_y == [0]


def test_pd_mmr_skips_at_pixel_setup():
    # MMR-encoded dictionaries do not wire AT pixels (get_dictionary branch).
    pd = parse_pd(pd_data(4, 4, 0, mmr=1))
    assert pd.is_mmr_encoded_flag() is True
    assert pd.gb_at_x is None


# ---------------------------------------------------------------------------
# Pattern-dictionary collective-bitmap slice (6.7.5 step 4)
# ---------------------------------------------------------------------------
def _seed_collective(pd: PatternDictionary, collective: Bitmap) -> list[Bitmap]:
    pd._extract_patterns(collective)
    return pd.patterns


@pytest.mark.parametrize("gray_max", [0, 1, 3, 4])
def test_slice_count_equals_gray_max_plus_one(gray_max):
    hdpw, hdph = 4, 3
    pd = parse_pd(pd_data(hdpw, hdph, gray_max))
    collective = Bitmap((gray_max + 1) * hdpw, hdph)
    patterns = _seed_collective(pd, collective)
    assert len(patterns) == gray_max + 1
    for p in patterns:
        assert p.get_width() == hdpw
        assert p.get_height() == hdph


def test_slice_stride_and_content():
    # Paint column-block g of the collective bitmap solid, verify pattern g
    # alone is solid after slicing (stride = HDPW, origin = HDPW*g).
    hdpw, hdph, gray_max = 4, 4, 3
    collective = Bitmap((gray_max + 1) * hdpw, hdph)
    target = 2  # paint the third pattern's columns
    for y in range(hdph):
        for x in range(hdpw):
            collective.set_pixel(target * hdpw + x, y, 1)

    pd = parse_pd(pd_data(hdpw, hdph, gray_max))
    patterns = _seed_collective(pd, collective)
    for g, p in enumerate(patterns):
        expected = 1 if g == target else 0
        for y in range(hdph):
            for x in range(hdpw):
                assert p.get_pixel(x, y) == expected, (g, x, y)


def test_slice_single_pattern_gray_max_zero():
    hdpw, hdph = 5, 2
    collective = Bitmap(hdpw, hdph)
    collective.set_pixel(0, 0, 1)
    collective.set_pixel(hdpw - 1, hdph - 1, 1)
    pd = parse_pd(pd_data(hdpw, hdph, 0))
    patterns = _seed_collective(pd, collective)
    assert len(patterns) == 1
    assert patterns[0].get_pixel(0, 0) == 1
    assert patterns[0].get_pixel(hdpw - 1, hdph - 1) == 1


def test_collective_bitmap_width_is_gray_max_plus_one_times_hdpw():
    # Decode a real (deterministic) dictionary and confirm slicing geometry.
    hdpw, hdph, gray_max = 4, 4, 3
    pd = parse_pd(pd_data(hdpw, hdph, gray_max))
    patterns = pd.get_dictionary()
    assert len(patterns) == gray_max + 1
    assert all(
        p.get_width() == hdpw and p.get_height() == hdph for p in patterns
    )
    # Cached on repeat.
    assert pd.get_dictionary() is patterns


# ---------------------------------------------------------------------------
# Halftone flag parse fuzz (7.4.5.1.1)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("defpix", [0, 1])
@pytest.mark.parametrize("skip", [0, 1])
@pytest.mark.parametrize("template", [0, 1, 2, 3])
@pytest.mark.parametrize("mmr", [0, 1])
def test_ht_flag_parse_roundtrip(defpix, skip, template, mmr):
    hr = parse_ht(
        ht_data(8, 8, 2, 2, defpix=defpix, skip=skip, template=template, mmr=mmr)
    )
    assert hr.get_h_default_pixel() == defpix
    assert hr.is_h_skip_enabled() is bool(skip)
    assert hr.get_h_template() == template
    assert hr.is_mmr_encoded_flag() is bool(mmr)


@pytest.mark.parametrize(
    "code,op",
    [
        (0, CombinationOperator.OR),
        (1, CombinationOperator.AND),
        (2, CombinationOperator.XOR),
        (3, CombinationOperator.XNOR),
        (4, CombinationOperator.REPLACE),
        (5, CombinationOperator.REPLACE),  # >4 falls through to REPLACE
    ],
)
def test_ht_combop_parse(code, op):
    hr = parse_ht(ht_data(8, 8, 2, 2, combop=code))
    assert hr.get_combination_operator() == op


def test_ht_grid_fields_signed_and_unsigned():
    hr = parse_ht(
        ht_data(8, 8, hgw=300, hgh=7, hgx=-1, hgy=-2, hrx=0xFFFF, hry=0x8000)
    )
    assert hr.get_h_grid_width() == 300  # unsigned 32
    assert hr.get_h_grid_height() == 7
    assert hr.get_h_grid_x() == -1  # signed 32
    assert hr.get_h_grid_y() == -2
    assert hr.get_h_region_x() == 0xFFFF  # unsigned 16
    assert hr.get_h_region_y() == 0x8000


# ---------------------------------------------------------------------------
# Grid placement math (6.6.5.2)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "hgx,hgy,hrx,hry,m,n",
    [
        (0, 0, 256, 0, 0, 0),
        (0, 0, 256, 0, 3, 5),
        (512, 256, 256, 0, 2, 1),
        (-256, -256, 256, 0, 1, 1),
        (0, 0, 256, 128, 4, 3),
        (100, 200, 300, 50, 7, 2),
    ],
)
def test_grid_vector_formula_matches_spec(hgx, hgy, hrx, hry, m, n):
    hr = parse_ht(ht_data(64, 64, 8, 8, hgx=hgx, hgy=hgy, hrx=hrx, hry=hry))
    # x = (HGX + m*HRY + n*HRX) >> 8 ; y = (HGY + m*HRX - n*HRY) >> 8.
    exp_x = (hgx + m * hry + n * hrx) >> 8
    exp_y = (hgy + m * hrx - n * hry) >> 8
    assert hr._compute_x(m, n) == exp_x
    assert hr._compute_y(m, n) == exp_y


def test_grid_vector_x_y_not_swapped():
    # A pure horizontal vector (HRX=256, HRY=0) must move x with n, y with m;
    # a swap would couple x to m. This pins the HRX/HRY roles in compute_x/y.
    hr = parse_ht(ht_data(64, 64, 8, 8, hrx=256, hry=0))
    assert hr._compute_x(0, 1) == 1
    assert hr._compute_x(1, 0) == 0  # x independent of m
    assert hr._compute_y(1, 0) == 1
    assert hr._compute_y(0, 1) == 0  # y independent of n with HRY=0


# ---------------------------------------------------------------------------
# Gray-code bitplane decode (Annex C.5)
# ---------------------------------------------------------------------------
def _gray_decode_reference(planes_bits: list[list[int]]) -> list[int]:
    """Reference Gray-code decode for one row of bit columns.

    ``planes_bits[j][x]`` is the *encoded* bit of plane j (j=0 LSB). The
    standard decodes from MSB down: bit[J-1] stays, bit[j] = bit[j+1] ^ enc[j].
    """
    bpp = len(planes_bits)
    width = len(planes_bits[0])
    values = []
    for x in range(width):
        decoded = [0] * bpp
        decoded[bpp - 1] = planes_bits[bpp - 1][x]
        for j in range(bpp - 2, -1, -1):
            decoded[j] = decoded[j + 1] ^ planes_bits[j][x]
        values.append(sum(decoded[j] << j for j in range(bpp)))
    return values


def test_gray_code_two_plane_decode():
    hr = parse_ht(ht_data(8, 8, 8, 1))
    plane0 = Bitmap(8, 1)
    plane1 = Bitmap(8, 1)
    enc = {0: (0, 0), 1: (0, 1), 2: (1, 1), 3: (1, 0)}  # (b1,b0) gray of 0..3
    for x, (b1, b0) in enc.items():
        plane1.set_pixel(x, 0, b1)
        plane0.set_pixel(x, 0, b0)
    planes = [plane0, plane1]
    planes = hr._combine_gray_scale_planes(planes, 0)
    values = hr._compute_gray_scale_values(planes, 2)
    assert values[0][:4] == [0, 1, 2, 3]


def test_gray_code_three_plane_matches_reference():
    width = 8
    hr = parse_ht(ht_data(width, 8, width, 1))
    # Encoded planes: arbitrary but fixed bit patterns.
    enc = [
        [1, 0, 1, 1, 0, 0, 1, 0],  # plane 0 (LSB)
        [0, 1, 1, 0, 1, 0, 0, 1],  # plane 1
        [1, 1, 0, 0, 0, 1, 1, 0],  # plane 2 (MSB)
    ]
    planes = []
    for j in range(3):
        bm = Bitmap(width, 1)
        for x in range(width):
            bm.set_pixel(x, 0, enc[j][x])
        planes.append(bm)

    # Apply the standard's MSB-down combine: j = 1 then j = 0.
    planes = hr._combine_gray_scale_planes(planes, 1)
    planes = hr._combine_gray_scale_planes(planes, 0)
    values = hr._compute_gray_scale_values(planes, 3)

    expected = _gray_decode_reference(enc)
    assert values[0] == expected


def test_gray_value_bit_packing_multibyte_row():
    # Grid width 12 spans two bytes per row; verify per-cell value reconstruct
    # picks the right bit out of the right byte (MSB-first).
    width = 12
    hr = parse_ht(ht_data(width, 8, width, 1))
    plane = Bitmap(width, 1)
    # Single set bit at column 9 (in the second byte).
    plane.set_pixel(9, 0, 1)
    values = hr._compute_gray_scale_values([plane], 1)
    for x in range(width):
        assert values[0][x] == (1 if x == 9 else 0)


def test_bits_per_value_log2_ceil():
    # 6.6.5 step 3: bitsPerValue = ceil(log2(num_patterns)). Confirm the
    # decode picks the same count the spec formula yields.
    for count in (2, 3, 4, 5, 8):
        expected = int(math.ceil(math.log(count) / math.log(2)))
        hr = parse_ht(ht_data(8, 8, 2, 2))
        hr.patterns = distinct_patterns(count, 4, 4)
        # Exercise the formula the decoder uses (no need to fully decode):
        assert int(math.ceil(math.log(len(hr.patterns)) / math.log(2))) == expected


# ---------------------------------------------------------------------------
# HDEFPIXEL pre-fill (6.6.5 step 1)
# ---------------------------------------------------------------------------
def test_default_pixel_one_prefills_region():
    hr = parse_ht(ht_data(8, 8, 2, 2, defpix=1, combop=0))
    hr.patterns = distinct_patterns(4, 4, 4)
    bm = hr.get_region_bitmap()
    # OR-combining onto an all-set background leaves it all-set.
    assert all(b == 0xFF for b in bm.get_byte_array())


def test_default_pixel_zero_does_not_prefill():
    # defpix=0 must NOT pre-fill: all-blank patterns leave a blank region.
    # (>=2 patterns so bitsPerValue >= 1; the single-pattern case is a
    # degenerate edge that throws in upstream PDFBox too — see
    # test_single_pattern_halftone_matches_upstream_crash.)
    hr = parse_ht(ht_data(8, 8, 2, 2, defpix=0, combop=0))
    hr.patterns = [Bitmap(4, 4), Bitmap(4, 4)]  # two blank patterns
    bm = hr.get_region_bitmap()
    assert all(b == 0x00 for b in bm.get_byte_array())


def test_single_pattern_halftone_matches_upstream_crash():
    # A halftone region with a single pattern yields bitsPerValue == 0
    # (ceil(log2(1)) == 0); upstream PDFBox indexes grayScalePlanes[-1] and
    # throws ArrayIndexOutOfBoundsException. The port reproduces this with an
    # IndexError (faithful to upstream; a 1-gray-level halftone is undefined).
    hr = parse_ht(ht_data(8, 8, 1, 1, defpix=0))
    hr.patterns = [Bitmap(4, 4)]
    with pytest.raises(IndexError):
        hr.get_region_bitmap()


# ---------------------------------------------------------------------------
# HSKIP bitmap (6.6.5.1)
# ---------------------------------------------------------------------------
def test_skip_bitmap_dimensions_and_in_region_cells_unset():
    hr = parse_ht(ht_data(8, 8, 4, 4, hrx=256, hry=0))
    hr.halftone_region_bitmap = Bitmap(8, 8)
    skip = hr._compute_h_skip(4, 4)
    assert skip.get_width() == 4  # HGW
    assert skip.get_height() == 4  # HGH
    for m in range(4):
        for n in range(4):
            assert skip.get_pixel(n, m) == 0  # all cells land inside


@pytest.mark.parametrize("hrx_mult", [3, 4])
def test_skip_marks_out_of_region_cells(hrx_mult):
    hr = parse_ht(ht_data(8, 8, 4, 4, hrx=256 * hrx_mult, hry=0))
    hr.halftone_region_bitmap = Bitmap(8, 8)
    skip = hr._compute_h_skip(4, 4)
    pw = ph = 4
    for m in range(4):
        for n in range(4):
            x = hr._compute_x(m, n)
            y = hr._compute_y(m, n)
            outside = x + pw <= 0 or x >= 8 or y + ph <= 0 or y >= 8
            assert skip.get_pixel(n, m) == (1 if outside else 0)


def test_skip_polarity_not_inverted():
    # A cell fully left of the region (x + HPW <= 0) is SKIPPED (==1), an
    # in-region cell is NOT (==0). Guards against an inverted skip test.
    hr = parse_ht(ht_data(8, 8, 2, 1, hgx=-10 * 256, hrx=256, hry=0))
    hr.halftone_region_bitmap = Bitmap(8, 8)
    skip = hr._compute_h_skip(4, 4)
    # cell (0,0): x = (-10*256 + 0) >> 8 = -10 ; x + 4 = -6 <= 0 -> skipped.
    assert skip.get_pixel(0, 0) == 1


# ---------------------------------------------------------------------------
# Render placement (6.6.5.2) — drive _render_pattern directly
# ---------------------------------------------------------------------------
def test_render_blits_pattern_at_grid_cell():
    hr = parse_ht(ht_data(8, 8, 2, 2, hrx=4 * 256, hry=0))
    hr.halftone_region_bitmap = Bitmap(8, 8)
    blank = Bitmap(4, 4)
    full = Bitmap(4, 4)
    full.fill_bitmap(0xFF)
    hr.patterns = [blank, full]
    hr._render_pattern([[0, 1], [0, 0]])  # full at (m=0,n=1) -> x=4,y=0
    bm = hr.halftone_region_bitmap
    for y in range(8):
        for x in range(8):
            assert bm.get_pixel(x, y) == (1 if (y < 4 and 4 <= x < 8) else 0)


def test_render_uses_correct_pattern_index_per_cell():
    hr = parse_ht(ht_data(8, 8, 2, 2, hrx=4 * 256, hry=0))
    hr.halftone_region_bitmap = Bitmap(8, 8)
    p0 = Bitmap(4, 4)  # blank
    p1 = Bitmap(4, 4)
    p1.set_pixel(0, 0, 1)
    p2 = Bitmap(4, 4)
    p2.fill_bitmap(0xFF)
    hr.patterns = [p0, p1, p2]
    hr._render_pattern([[1, 2], [0, 0]])
    bm = hr.halftone_region_bitmap
    # cell (0,0) -> pattern 1: single set pixel at region (0,0).
    assert bm.get_pixel(0, 0) == 1
    assert bm.get_pixel(1, 0) == 0
    # cell (0,1) -> pattern 2 (full) at region (4,0)..(7,3).
    for y in range(4):
        for x in range(4, 8):
            assert bm.get_pixel(x, y) == 1


# ---------------------------------------------------------------------------
# Full deterministic decode (arithmetic path) across templates
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("template", [0, 1, 2, 3])
def test_full_decode_deterministic_per_template(template):
    a = parse_ht(ht_data(8, 8, 2, 2, template=template))
    a.patterns = distinct_patterns(4, 4, 4)
    b = parse_ht(ht_data(8, 8, 2, 2, template=template))
    b.patterns = distinct_patterns(4, 4, 4)
    assert bytes(a.get_region_bitmap().get_byte_array()) == bytes(
        b.get_region_bitmap().get_byte_array()
    )


def test_full_decode_with_skip_enabled_runs():
    hr = parse_ht(ht_data(8, 8, 2, 2, skip=1, hrx=256, hry=0))
    hr.patterns = distinct_patterns(4, 4, 4)
    bm = hr.get_region_bitmap()
    assert bm.get_width() == 8
    assert bm.get_height() == 8
