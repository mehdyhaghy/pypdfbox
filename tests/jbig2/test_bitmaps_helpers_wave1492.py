"""Behaviour pins for the ``Bitmaps`` byte/region helpers (wave 1492).

``combine_bytes`` (the 5 JBIG2 logical operators, §6.x), ``extract`` (region of
interest copy), ``subsample_x`` / ``subsample_y`` (single-axis subsampling,
including the faithfully-reproduced upstream dimension quirk) and ``blit``
(composite one bitmap onto another, byte-aligned + unaligned + off-canvas) are
exercised here with hand-built bitmaps whose every set pixel is asserted on the
output. These complement the live-oracle raster tests (which only reach the
both-axes subsample + scaled paths) by pinning the primitive composition logic.
"""

from __future__ import annotations

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.image.bitmaps import Bitmaps
from pypdfbox.jbig2.jbig2_read_param import JBIG2ReadParam
from pypdfbox.jbig2.util.combination_operator import CombinationOperator


def _to_unsigned(b: int) -> int:
    return b & 0xFF


# --------------------------------------------------------------------------
# as_raster / subsample null-argument guards
# --------------------------------------------------------------------------


def test_as_raster_rejects_null_bitmap():
    with pytest.raises(ValueError, match="bitmap must not be null"):
        Bitmaps.as_raster(None, JBIG2ReadParam())


def test_as_raster_rejects_null_param():
    with pytest.raises(ValueError, match="param must not be null"):
        Bitmaps.as_raster(Bitmap(4, 4), None)


def test_subsample_rejects_null_args():
    with pytest.raises(ValueError, match="src must not be null"):
        Bitmaps.subsample(None, JBIG2ReadParam())
    with pytest.raises(ValueError, match="param must not be null"):
        Bitmaps.subsample(Bitmap(4, 4), None)


# --------------------------------------------------------------------------
# combine_bytes — all five operators
# --------------------------------------------------------------------------


def test_combine_bytes_or():
    assert _to_unsigned(Bitmaps.combine_bytes(0xF0, 0x0F, CombinationOperator.OR)) == 0xFF


def test_combine_bytes_and():
    assert _to_unsigned(Bitmaps.combine_bytes(0xF0, 0x3C, CombinationOperator.AND)) == 0x30


def test_combine_bytes_xor():
    assert _to_unsigned(Bitmaps.combine_bytes(0xFF, 0x0F, CombinationOperator.XOR)) == 0xF0


def test_combine_bytes_xnor():
    # ~(a ^ b) masked to a byte.
    assert _to_unsigned(
        Bitmaps.combine_bytes(0xFF, 0x0F, CombinationOperator.XNOR)
    ) == 0x0F


def test_combine_bytes_replace():
    assert _to_unsigned(
        Bitmaps.combine_bytes(0xFF, 0xAA, CombinationOperator.REPLACE)
    ) == 0xAA


# --------------------------------------------------------------------------
# extract — region of interest
# --------------------------------------------------------------------------


def test_extract_byte_aligned_region():
    src = Bitmap(16, 4)
    # set a diagonal in the right half.
    for i in range(4):
        src.set_pixel(8 + i, i, 1)
    dst = Bitmaps.extract((8, 0, 8, 4), src)
    assert dst.get_width() == 8
    assert dst.get_height() == 4
    for i in range(4):
        assert dst.get_pixel(i, i) == 1
    # a pixel not on the diagonal is clear.
    assert dst.get_pixel(0, 1) == 0


def test_extract_unaligned_region_copies_shifted_pixels():
    src = Bitmap(16, 2)
    src.set_pixel(3, 0, 1)
    src.set_pixel(5, 1, 1)
    dst = Bitmaps.extract((3, 0, 4, 2), src)
    assert dst.get_width() == 4
    # src(3,0) -> dst(0,0); src(5,1) -> dst(2,1).
    assert dst.get_pixel(0, 0) == 1
    assert dst.get_pixel(2, 1) == 1


# --------------------------------------------------------------------------
# subsample_x / subsample_y (single axis)
# --------------------------------------------------------------------------


def test_subsample_y_dimensions_and_visible_rows():
    # subsample_y derives dst *width* from src width//sampling (upstream quirk)
    # but keeps the full src height as dst height. To keep y_src in bounds the
    # source must be tall enough that height//1 stepped by `sampling` stays
    # inside it — i.e. a 1x-sampling pass is the safe, lossless case here.
    src = Bitmap(8, 4)
    for x in range(8):
        src.set_pixel(x, 0, 1)   # row 0 fully set
        src.set_pixel(x, 2, 1)   # row 2 fully set
    dst = Bitmaps.subsample_y(src, 1, 0)
    # dst width == (8 - 0)//1 == 8 ; height == src height 4.
    assert dst.get_width() == 8
    assert dst.get_height() == 4
    assert dst.get_pixel(0, 0) == 1
    assert dst.get_pixel(0, 2) == 1
    assert dst.get_pixel(0, 1) == 0


def test_subsample_y_sampling_gt_one_overflows_like_upstream():
    # The upstream dimension quirk: dst height stays == src height while y_src
    # steps by `sampling`, so a >1 vertical sampling walks off the source and
    # raises (mirrored as IndexError) — verified verbatim against 3.0.7.
    src = Bitmap(8, 8)
    with pytest.raises(IndexError):
        Bitmaps.subsample_y(src, 2, 0)


def test_subsample_x_dimensions_and_visible_cols():
    # subsample_x derives dst *height* from src width//sampling (upstream quirk)
    # but keeps the full src width. A 1x-sampling pass is the safe case.
    src = Bitmap(4, 8)
    for y in range(8):
        src.set_pixel(0, y, 1)   # col 0
        src.set_pixel(2, y, 1)   # col 2
    dst = Bitmaps.subsample_x(src, 1, 0)
    # dst height == (4 - 0)//1 == 4 ; width == src width 4.
    assert dst.get_width() == 4
    assert dst.get_height() == 4
    assert dst.get_pixel(0, 0) == 1
    assert dst.get_pixel(2, 0) == 1
    assert dst.get_pixel(1, 0) == 0


def test_subsample_x_sampling_gt_one_keeps_full_width():
    # subsample_x keeps src width and derives height == width//sampling, so a
    # 2x pass over 8x8 yields an 8x4 bitmap (the upstream dimension quirk; the
    # x_src stride stays inside the byte array here so it does not overflow).
    src = Bitmap(8, 8)
    dst = Bitmaps.subsample_x(src, 2, 0)
    assert dst.get_width() == 8
    assert dst.get_height() == 4


def test_subsample_x_none_src_raises():
    with pytest.raises(ValueError, match="src must not be null"):
        Bitmaps.subsample_x(None, 2, 0)


def test_subsample_y_none_src_raises():
    with pytest.raises(ValueError, match="src must not be null"):
        Bitmaps.subsample_y(None, 2, 0)


# --------------------------------------------------------------------------
# blit — composite one bitmap onto another
# --------------------------------------------------------------------------


def _filled(w, h):
    bm = Bitmap(w, h)
    for y in range(h):
        for x in range(w):
            bm.set_pixel(x, y, 1)
    return bm


def test_blit_byte_aligned_or():
    src = _filled(8, 2)
    dst = Bitmap(16, 4)
    Bitmaps.blit(src, dst, 0, 0, CombinationOperator.OR)
    for y in range(2):
        for x in range(8):
            assert dst.get_pixel(x, y) == 1
    # the rest of dst stays clear.
    assert dst.get_pixel(8, 0) == 0
    assert dst.get_pixel(0, 2) == 0


def test_blit_unaligned_x_pixel_path():
    src = _filled(3, 2)
    dst = Bitmap(16, 4)
    Bitmaps.blit(src, dst, 5, 1, CombinationOperator.OR)
    for y in range(2):
        for x in range(3):
            assert dst.get_pixel(5 + x, 1 + y) == 1
    assert dst.get_pixel(4, 1) == 0
    assert dst.get_pixel(8, 1) == 0


def test_blit_partly_off_canvas_clips():
    src = _filled(4, 4)
    dst = Bitmap(8, 8)
    # place so the left two columns and top two rows fall off-canvas.
    Bitmaps.blit(src, dst, -2, -2, CombinationOperator.OR)
    # only the bottom-right 2x2 of src lands at dst (0,0)-(1,1).
    assert dst.get_pixel(0, 0) == 1
    assert dst.get_pixel(1, 1) == 1
    # nothing past the clipped corner.
    assert dst.get_pixel(2, 2) == 0
