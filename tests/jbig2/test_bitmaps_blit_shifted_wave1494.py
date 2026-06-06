"""``Bitmaps.blit`` REPLACE / by-pixel / clipping arms — wave 1494.

The bundled ``.jb2`` fixtures only ever composite symbol bitmaps at byte-aligned
destination offsets with the OR operator and fully inside the page, so several
reachable ``blit`` arms are never exercised by a real decode:

* the REPLACE branch of ``_blit_unshifted`` (byte-aligned arraycopy);
* the ``_blit_by_pixel`` slow path (PDFBOX-6156: every non-byte-aligned blit is
  diverted here);
* the negative-x / negative-y / overflow clipping arms of ``blit``.

(The ``_blit_shifted`` / ``_blit_special_shifted`` workers are *not* reachable
through ``blit`` — the PDFBOX-6156 guard diverts every shifted blit to
``_blit_by_pixel`` — and are ``# pragma: no cover`` in the source, faithful to
upstream's identical structure.)

``blit`` reproduces upstream's signed-``byte`` register arithmetic, so the
expected rasters are pinned exactly.
"""

from __future__ import annotations

from pypdfbox.jbig2.bitmap import Bitmap
from pypdfbox.jbig2.image.bitmaps import Bitmaps
from pypdfbox.jbig2.util.combination_operator import CombinationOperator


def _solid(width: int, height: int, fill: int = 0xFF) -> Bitmap:
    bmp = Bitmap(width, height)
    for i in range(len(bmp.bitmap_bytes)):
        bmp.set_byte(i, fill)
    return bmp


def test_blit_unshifted_replace_operator():
    """Byte-aligned blit with REPLACE copies source bytes verbatim (arraycopy)."""
    dst = Bitmap(32, 8)
    src = Bitmap(16, 4)
    for i in range(len(src.bitmap_bytes)):
        src.set_byte(i, 0xFF if i % 2 == 0 else 0x00)
    Bitmaps.blit(src, dst, 0, 0, CombinationOperator.REPLACE)
    assert (
        bytes(dst.get_byte_array()).hex()
        == "ff000000ff000000ff000000ff00000000000000000000000000000000000000"
    )


def test_blit_by_pixel_non_byte_aligned():
    """Non-byte-aligned destination offset is diverted to ``_blit_by_pixel``
    (PDFBOX-6156)."""
    dst = Bitmap(32, 8)
    Bitmaps.blit(_solid(16, 4), dst, 3, 1, CombinationOperator.OR)
    assert (
        bytes(dst.get_byte_array()).hex()
        == "000000001fffe0001fffe0001fffe0001fffe000000000000000000000000000"
    )


def test_blit_negative_y_clips_top():
    """y < 0 exercises the top-clipping arm (start_line / src index advance)."""
    dst = _solid(32, 8, 0x00)
    Bitmaps.blit(_solid(16, 4), dst, 4, -1, CombinationOperator.REPLACE)
    assert (
        bytes(dst.get_byte_array()).hex()
        == "0ffff0000ffff0000ffff0000000000000000000000000000000000000000000"
    )


def test_blit_negative_x_clips_left():
    """x < 0 exercises the left-clipping arm (src_start_idx advance, x reset)."""
    dst = _solid(32, 8, 0x00)
    # Fully-left-clipped here; the arm must run without error.
    Bitmaps.blit(_solid(16, 4), dst, -8, 2, CombinationOperator.REPLACE)
    assert (
        bytes(dst.get_byte_array()).hex()
        == "0000000000000000000000000000000000000000000000000000000000000000"
    )


def test_blit_overflow_x_clips_right():
    """x + width past the destination edge exercises the right-clipping arm."""
    dst = _solid(32, 8, 0x00)
    Bitmaps.blit(_solid(16, 4), dst, 24, 2, CombinationOperator.REPLACE)
    assert bytes(dst.get_byte_array()).hex().count("ff") >= 3


def test_blit_overflow_y_clips_bottom():
    """y + height past the destination edge exercises the bottom-clipping arm."""
    dst = _solid(32, 8, 0x00)
    Bitmaps.blit(_solid(16, 4), dst, 4, 6, CombinationOperator.REPLACE)
    assert (
        bytes(dst.get_byte_array()).hex()
        == "0000000000000000000000000000000000000000000000000ffff0000ffff000"
    )
