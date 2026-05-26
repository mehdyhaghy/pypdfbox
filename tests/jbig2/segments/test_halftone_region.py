"""Hand-written unit tests for the JBIG2 halftone-region decoder.

Covers ``HalftoneRegion`` header parsing (region segment info + halftone flags +
grid position/size + grid vector) and the §6.6.5 decode procedure: the
grayscale image is decoded from ``bitsPerValue`` generic-region bit planes,
XOR-combined into a Gray code, turned into per-cell grayscale values, and each
cell's value indexes a pattern that is blitted onto the region bitmap at the
grid position.

The crafted input is the EXACT segment-data part of a halftone-region segment
(everything after the segment header): the region segment information field, the
halftone flags byte, HGW/HGH/HGX/HGY, HRX/HRY, then the arithmetic-coded
grayscale planes. Patterns are injected directly (mirroring how the live oracle
probe pre-seeds them) so the grayscale-decode + pattern-placement path is
exercised without fabricating a referred-to pattern-dictionary segment.

Bit convention: pypdfbox's ``Bitmap`` packs MSB-first, 1 == set.
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.io.image_input_stream import ImageInputStream
from pypdfbox.jbig2.io.sub_input_stream import SubInputStream
from pypdfbox.jbig2.segments.halftone_region import HalftoneRegion
from pypdfbox.jbig2.util.combination_operator import CombinationOperator

# Arbitrary but fixed arithmetic-coded payload (shared with the generic-region
# fixtures); the deterministic MQ decoder turns it into stable grayscale planes.
CODED = bytes([0x84, 0xC7, 0x3B, 0x6A, 0x21, 0x00, 0x00, 0x00])


def region_info(width: int, height: int, x: int = 0, y: int = 0) -> bytes:
    """Region segment information field, 7.4.1 (combination operator = OR=0)."""
    return struct.pack(">IIII", width, height, x, y) + bytes([0x00])


def ht_flags(
    defpix: int = 0,
    combop: int = 0,
    skip: int = 0,
    template: int = 0,
    mmr: int = 0,
) -> bytes:
    """Halftone region segment flags byte, 7.4.5.1.1.

    bit7=HDEFPIXEL, bit4-6=HCOMBOP, bit3=HENABLESKIP, bit1-2=HTEMPLATE, bit0=HMMR.
    """
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
    """Assemble a halftone-region segment-data buffer."""
    return (
        region_info(rw, rh)
        + ht_flags(**flags)
        + struct.pack(">II", hgw, hgh)  # HGW, HGH (unsigned)
        + struct.pack(">ii", hgx, hgy)  # HGX, HGY (signed)
        + struct.pack(">HH", hrx, hry)  # HRX, HRY
        + coded
    )


def _parse(segment_data: bytes) -> HalftoneRegion:
    iis = ImageInputStream(segment_data)
    sis = SubInputStream(iis, 0, len(segment_data))
    hr = HalftoneRegion()
    hr.init(None, sis)
    return hr


def _patterns(count: int, width: int, height: int) -> list[Bitmap]:
    """Build ``count`` distinct ``width`` x ``height`` patterns."""
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
# Header parsing
# ---------------------------------------------------------------------------
def test_parse_header_basic():
    hr = _parse(ht_data(rw=8, rh=8, hgw=2, hgh=3, hgx=5, hgy=-7, hrx=300, hry=12))
    info = hr.get_region_info()
    assert info.get_bitmap_width() == 8
    assert info.get_bitmap_height() == 8
    assert hr.get_h_grid_width() == 2
    assert hr.get_h_grid_height() == 3
    assert hr.get_h_grid_x() == 5
    assert hr.get_h_grid_y() == -7  # HGX/HGY are signed 32-bit
    assert hr.get_h_region_x() == 300
    assert hr.get_h_region_y() == 12


def test_parse_header_flags():
    hr = _parse(
        ht_data(
            rw=8, rh=8, hgw=2, hgh=2, defpix=1, combop=2, skip=1, template=3, mmr=1
        )
    )
    assert hr.get_h_default_pixel() == 1
    assert hr.get_combination_operator() == CombinationOperator.XOR
    assert hr.is_h_skip_enabled() is True
    assert hr.get_h_template() == 3
    assert hr.is_mmr_encoded_flag() is True


def test_parse_header_default_flags():
    hr = _parse(ht_data(rw=8, rh=8, hgw=2, hgh=2))
    assert hr.get_h_default_pixel() == 0
    assert hr.get_combination_operator() == CombinationOperator.OR
    assert hr.is_h_skip_enabled() is False
    assert hr.get_h_template() == 0
    assert hr.is_mmr_encoded_flag() is False


def test_parse_header_combination_operators():
    for code, op in [
        (0, CombinationOperator.OR),
        (1, CombinationOperator.AND),
        (2, CombinationOperator.XOR),
        (3, CombinationOperator.XNOR),
        (4, CombinationOperator.REPLACE),
    ]:
        hr = _parse(ht_data(rw=8, rh=8, hgw=2, hgh=2, combop=code))
        assert hr.get_combination_operator() == op


# ---------------------------------------------------------------------------
# computeX / computeY (6.6.5.2 grid placement)
# ---------------------------------------------------------------------------
def test_compute_x_y_grid_placement():
    hr = _parse(ht_data(rw=16, rh=16, hgw=2, hgh=2, hgx=0, hgy=0, hrx=256, hry=0))
    # x = (HGX + m*HRY + n*HRX) >> 8 ; with HRX=256, HRY=0 -> x = n, y = m.
    assert hr._compute_x(0, 0) == 0
    assert hr._compute_x(0, 1) == 1
    assert hr._compute_x(1, 1) == 1
    assert hr._compute_y(0, 0) == 0
    assert hr._compute_y(1, 0) == 1


def test_compute_x_y_with_offsets():
    hr = _parse(ht_data(rw=16, rh=16, hgw=2, hgh=2, hgx=512, hgy=256, hrx=256, hry=0))
    # x = (512 + 0 + n*256) >> 8 = 2 + n ; y = (256 + m*256 - 0) >> 8 = 1 + m.
    assert hr._compute_x(0, 0) == 2
    assert hr._compute_y(0, 0) == 1
    assert hr._compute_x(1, 1) == 3
    assert hr._compute_y(1, 1) == 2


# ---------------------------------------------------------------------------
# Decode procedure (6.6.5)
# ---------------------------------------------------------------------------
def test_get_region_bitmap_dimensions_and_cached():
    hr = _parse(ht_data(rw=8, rh=8, hgw=2, hgh=2))
    hr.patterns = _patterns(4, 4, 4)  # graymax 3 -> bitsPerValue 2
    bm = hr.get_region_bitmap()
    assert bm.get_width() == 8
    assert bm.get_height() == 8
    # Cached on subsequent calls.
    assert hr.get_region_bitmap() is bm


def test_default_pixel_fills_region_before_render():
    # HDEFPIXEL=1 fills the region with 0xff first; with OR combination and
    # all-set start, the result stays all-set regardless of patterns.
    hr = _parse(ht_data(rw=8, rh=8, hgw=2, hgh=2, defpix=1, combop=0))
    hr.patterns = _patterns(4, 4, 4)
    bm = hr.get_region_bitmap()
    assert all(b == 0xFF for b in bm.get_byte_array())


def test_render_places_patterns_at_grid_positions():
    """Render with a known single grayscale value forces a known pattern blit.

    Drive ``_render_pattern`` directly with a fixed grayScaleValues matrix so
    the placement (computeX/computeY + blit) is verified independently of the
    arithmetic grayscale decode.
    """
    # HRX = 4*256 so grid column n maps to region x = 4*n (HRY=0 -> y = m).
    hr = _parse(
        ht_data(rw=8, rh=8, hgw=2, hgh=2, hgx=0, hgy=0, hrx=4 * 256, hry=0)
    )
    hr.halftone_region_bitmap = Bitmap(8, 8)

    # Pattern 1 is a fully-set 4x4 block; pattern 0 is blank.
    blank = Bitmap(4, 4)
    full = Bitmap(4, 4)
    full.fill_bitmap(0xFF)
    hr.patterns = [blank, full]

    # Place the full pattern only at grid cell (m=0, n=1) -> region (x=4, y=0).
    gray = [[0, 1], [0, 0]]
    hr._render_pattern(gray)
    bm = hr.halftone_region_bitmap

    for y in range(8):
        for x in range(8):
            expected = 1 if (0 <= y < 4 and 4 <= x < 8) else 0
            assert bm.get_pixel(x, y) == expected


def test_grayscale_gray_code_combination():
    """Plane combination is a Gray-code XOR-decode (Annex C.5, step 3b).

    Build two known bit planes and verify ``_combine_gray_scale_planes`` and
    ``_compute_gray_scale_values`` reproduce the Gray-code -> value mapping.
    """
    hr = _parse(ht_data(rw=8, rh=8, hgw=8, hgh=1))
    # Two planes (bitsPerValue = 2), 8x1.
    plane0 = Bitmap(8, 1)  # GSPLANES[0]
    plane1 = Bitmap(8, 1)  # GSPLANES[1] (most significant)
    # Set distinct Gray-code bit patterns per column.
    # column x: plane1 bit = b1, plane0 bit = b0 (Gray code of value).
    bits = {0: (0, 0), 1: (0, 1), 2: (1, 1), 3: (1, 0)}  # gray codes for 0..3
    for x, (b1, b0) in bits.items():
        plane1.set_pixel(x, 0, b1)
        plane0.set_pixel(x, 0, b0)

    planes = [plane0, plane1]
    # Step 3b for j = 0: GSPLANES[0] ^= GSPLANES[1].
    planes = hr._combine_gray_scale_planes(planes, 0)
    values = hr._compute_gray_scale_values(planes, 2)

    # Gray code (b1,b0): 00->0, 01->1, 11->2, 10->3.
    assert values[0][0] == 0
    assert values[0][1] == 1
    assert values[0][2] == 2
    assert values[0][3] == 3


def test_get_region_bitmap_deterministic_arithmetic_decode():
    """Full decode through the arithmetic grayscale path is deterministic."""
    hr = _parse(ht_data(rw=8, rh=8, hgw=2, hgh=2, hgx=0, hgy=0, hrx=256, hry=0))
    hr.patterns = _patterns(4, 4, 4)
    first = bytes(hr.get_region_bitmap().get_byte_array())

    hr2 = _parse(ht_data(rw=8, rh=8, hgw=2, hgh=2, hgx=0, hgy=0, hrx=256, hry=0))
    hr2.patterns = _patterns(4, 4, 4)
    second = bytes(hr2.get_region_bitmap().get_byte_array())

    assert first == second


# ---------------------------------------------------------------------------
# HSKIP (6.6.5.1)
# ---------------------------------------------------------------------------
def test_compute_h_skip_marks_cells_outside_region():
    # Grid cells whose pattern lands entirely outside the region get HSKIP=1.
    hr = _parse(ht_data(rw=8, rh=8, hgw=4, hgh=4, hgx=0, hgy=0, hrx=256, hry=0))
    hr.halftone_region_bitmap = Bitmap(8, 8)
    skip = hr._compute_h_skip(4, 4)
    # With HRX=256/HRY=0, cell (m,n) -> region (x=n*1? actually x=n, y=m) >> 8.
    # x = n, y = m. Cells with x>=8 (n>=8) or y>=8 (m>=8) skipped; here grid is
    # 4x4 so all cells map to x=n in 0..3, y=m in 0..3 -> none skipped.
    for m in range(4):
        for n in range(4):
            assert skip.get_pixel(n, m) == 0


def test_compute_h_skip_with_grid_extending_past_region():
    # Push the grid stride so some cells fall outside the region bitmap.
    # With HRX=3*256, HRY=0: x = 3*n, y = 3*m (both >> 8).
    hr = _parse(
        ht_data(rw=8, rh=8, hgw=4, hgh=4, hgx=0, hgy=0, hrx=256 * 3, hry=0)
    )
    hr.halftone_region_bitmap = Bitmap(8, 8)
    skip = hr._compute_h_skip(4, 4)
    pw = ph = 4
    for m in range(4):
        for n in range(4):
            x = hr._compute_x(m, n)
            y = hr._compute_y(m, n)
            outside = x + pw <= 0 or x >= 8 or y + ph <= 0 or y >= 8
            assert skip.get_pixel(n, m) == (1 if outside else 0)


def test_skip_enabled_decode_runs():
    pytest.importorskip("PIL")  # not needed, but keep parity with mmr cases
    hr = _parse(
        ht_data(rw=8, rh=8, hgw=2, hgh=2, hgx=0, hgy=0, hrx=256, hry=0, skip=1)
    )
    hr.patterns = _patterns(4, 4, 4)
    bm = hr.get_region_bitmap()
    assert bm.get_width() == 8
    assert bm.get_height() == 8
