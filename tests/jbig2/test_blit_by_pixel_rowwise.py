"""Row-wise ``_blit_by_pixel`` matches the original per-pixel loop."""

from __future__ import annotations

import random

import pytest

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.image.bitmaps import Bitmaps, _blit_by_pixel
from pypdfbox.jbig2.util.combination_operator import CombinationOperator


def _reference(src, dst, xo, yo, op):
    y = 0
    while y < src.get_height() and yo + y < dst.get_height():
        if yo + y < 0:
            y += 1
            continue
        x = 0
        while x < src.get_width() and xo + x < dst.get_width():
            if xo + x < 0:
                x += 1
                continue
            bit = Bitmaps.combine_bytes(
                dst.get_pixel(xo + x, yo + y), src.get_pixel(x, y), op
            )
            dst.set_pixel(xo + x, yo + y, bit)
            x += 1
        y += 1


def _random_bitmap(rng: random.Random, width: int, height: int) -> Bitmap:
    bm = Bitmap(width, height)
    for i in range(len(bm.bitmap_bytes)):
        bm.bitmap_bytes[i] = rng.randrange(256)
    return bm


@pytest.mark.parametrize("op", list(CombinationOperator), ids=lambda o: o.name)
def test_rowwise_blit_matches_per_pixel_loop(op: CombinationOperator) -> None:
    rng = random.Random(op.value)
    for _ in range(300):
        sw, sh = rng.randint(1, 37), rng.randint(1, 9)
        dw, dh = rng.randint(1, 45), rng.randint(1, 11)
        xo = rng.randint(-sw - 2, dw + 2)
        yo = rng.randint(-sh - 2, dh + 2)
        src = _random_bitmap(rng, sw, sh)
        dst = _random_bitmap(rng, dw, dh)
        expected = Bitmap(dw, dh)
        expected.bitmap_bytes[:] = dst.bitmap_bytes
        _reference(src, expected, xo, yo, op)
        _blit_by_pixel(src, dst, xo, yo, op)
        assert dst.bitmap_bytes == expected.bitmap_bytes, (sw, sh, dw, dh, xo, yo)
