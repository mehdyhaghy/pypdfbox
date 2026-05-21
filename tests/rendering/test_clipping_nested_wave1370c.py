"""Nested-clipping rendering tests for :class:`PDFRenderer`.

PDF 32000-1 §8.5.4: the ``W`` / ``W*`` operators stage a clip path which
is intersected with the current clipping region after the next paint or
``n``. Stacking ``q ... W n ... q ... W n ...`` therefore composes the
two clips (intersection). The non-zero (``W``) vs even-odd (``W*``)
fill-rule choice picks whether self-intersections and donut holes are
filled or left transparent.

These tests guard the four interesting cases:

1. Two nested rectangle clips intersect to the inner box.
2. Even-odd clip on a donut (outer rect ∪ inner rect drawn as one path)
   yields a hollow annulus.
3. Non-zero clip on the same donut path yields a solid (filled-through)
   rectangle (the inner rect lies inside the outer, both wind the same
   direction → non-zero rule keeps everything).
4. A clip stacked under ``q`` / ``Q`` resets to the outer clip after the
   restore, so a paint outside the inner box becomes visible again.
"""
from __future__ import annotations

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer


def _make_doc(width: float = 100.0, height: float = 100.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _is_close(
    actual: tuple[int, int, int],
    expected: tuple[int, int, int],
    tol: int = 12,
) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual[:3], expected, strict=True))


def _set_contents(page: PDPage, ops: bytes) -> None:
    contents = COSStream()
    contents.set_raw_data(ops)
    page.get_cos_object().set_item(COSName.CONTENTS, contents)


def test_nested_clip_intersection_keeps_only_overlap_visible() -> None:
    """Two rectangle clips stacked together restrict painting to their
    intersection. Outer clip: PDF (10..70, 10..70); inner clip: PDF
    (40..90, 40..90). A blue rect that spans the full page should only
    appear in the overlap PDF (40..70, 40..70)."""
    doc, page = _make_doc()
    _set_contents(
        page,
        b"q\n"
        # Outer clip — rectangle (10,10)-(70,70).
        b"10 10 60 60 re\n"
        b"W n\n"
        # Inner clip — rectangle (40,40)-(90,90).
        b"40 40 50 50 re\n"
        b"W n\n"
        # Paint a blue rectangle covering the full page.
        b"0 0 1 rg\n"
        b"0 0 100 100 re\n"
        b"f\n"
        b"Q\n",
    )
    img = PDFRenderer(doc).render_image(0)
    # PIL y flipped: PDF (40..70, 40..70) → PIL (40..70, 30..60).
    # Sample inside the intersection — should be blue.
    inside = img.getpixel((55, 45))
    assert _is_close(inside, (0, 0, 255), tol=20), inside
    # Sample just inside the outer clip but outside the inner clip
    # (PDF 20, 20 → PIL 20, 80). Should be white (clipped out).
    outside_inner = img.getpixel((20, 80))
    assert _is_close(outside_inner, (255, 255, 255), tol=8), outside_inner
    # Sample outside the outer clip (PDF 85, 85 → PIL 85, 15) — also
    # clipped out (the inner clip can't expand beyond the outer's scope
    # because intersection only shrinks).
    outside_outer = img.getpixel((85, 15))
    assert _is_close(outside_outer, (255, 255, 255), tol=8), outside_outer


def test_even_odd_clip_donut_leaves_hole_unclipped() -> None:
    """An even-odd clip path made of two nested rectangles (outer + inner)
    creates an annular (donut) clip. The hole in the centre is *not*
    clipped to the paint, so a fill that covers the whole page should
    appear only in the donut ring, with the page background showing
    through the hole."""
    doc, page = _make_doc()
    _set_contents(
        page,
        b"q\n"
        # Outer rect (10,10)-(90,90) then inner rect (30,30)-(70,70).
        b"10 10 80 80 re\n"
        b"30 30 40 40 re\n"
        b"W* n\n"
        # Paint the entire page red.
        b"1 0 0 rg\n"
        b"0 0 100 100 re\n"
        b"f\n"
        b"Q\n",
    )
    img = PDFRenderer(doc).render_image(0)
    # Sample inside the donut ring (PDF (20, 50) → PIL (20, 50)) — red.
    ring = img.getpixel((20, 50))
    assert _is_close(ring, (255, 0, 0), tol=20), ring
    # Sample inside the hole (PDF (50, 50) → PIL (50, 50)) — page background.
    hole = img.getpixel((50, 50))
    assert _is_close(hole, (255, 255, 255), tol=8), hole


def test_non_zero_clip_donut_fills_through_hole() -> None:
    """Same two-rectangle clip path but with the non-zero (``W``) rule:
    both rectangles wind the same direction (both clockwise as emitted
    by ``re``), so the non-zero winding count is non-zero everywhere
    inside the outer rectangle. The hole is *not* preserved — the entire
    outer rectangle is the clip region."""
    doc, page = _make_doc()
    _set_contents(
        page,
        b"q\n"
        b"10 10 80 80 re\n"
        b"30 30 40 40 re\n"
        b"W n\n"
        b"0 1 0 rg\n"
        b"0 0 100 100 re\n"
        b"f\n"
        b"Q\n",
    )
    img = PDFRenderer(doc).render_image(0)
    # Centre — should be green (filled through, non-zero rule).
    centre = img.getpixel((50, 50))
    assert _is_close(centre, (0, 255, 0), tol=20), centre
    # Inside the outer rect — also green.
    ring = img.getpixel((20, 50))
    assert _is_close(ring, (0, 255, 0), tol=20), ring
    # Outside the outer rect — white.
    outside = img.getpixel((5, 5))
    assert _is_close(outside, (255, 255, 255), tol=4), outside


def test_clip_restored_by_q_q_pair() -> None:
    """After ``Q`` the clip should revert to the value at the matching
    ``q``. A second paint *outside* the inner clip but within the page
    must show up post-restore."""
    doc, page = _make_doc()
    _set_contents(
        page,
        b"q\n"
        # Inner clip: PDF (40..60, 40..60).
        b"40 40 20 20 re\n"
        b"W n\n"
        # First red fill — only visible in the inner clip.
        b"1 0 0 rg\n"
        b"0 0 100 100 re\n"
        b"f\n"
        b"Q\n"
        # Outside the q/Q — clip reverts to full page. Paint blue.
        b"0 0 1 rg\n"
        b"10 10 20 20 re\n"
        b"f\n",
    )
    img = PDFRenderer(doc).render_image(0)
    # Inside the inner clip (PIL (50, 50)) — red.
    inner = img.getpixel((50, 50))
    assert _is_close(inner, (255, 0, 0), tol=20), inner
    # Outside the q/Q at PDF (15, 15) → PIL (15, 85) — blue (post-restore).
    outer = img.getpixel((15, 85))
    assert _is_close(outer, (0, 0, 255), tol=20), outer


def test_clip_followed_by_n_consumes_path_without_painting() -> None:
    """The ``n`` op ends the path without painting but still applies the
    pending clip. After ``n`` the path must be empty, so a subsequent
    paint outside the clip region must be clipped (not visible)."""
    doc, page = _make_doc()
    _set_contents(
        page,
        b"q\n"
        # Define clip = PDF (10..30, 10..30).
        b"10 10 20 20 re\n"
        b"W n\n"
        # Paint a yellow rectangle (45..65, 45..65) — outside the clip.
        b"1 1 0 rg\n"
        b"45 45 20 20 re\n"
        b"f\n"
        b"Q\n",
    )
    img = PDFRenderer(doc).render_image(0)
    # PIL (55, 45) maps to PDF (55, 55) — inside the yellow rect but
    # outside the clip. Should be white (clipped).
    outside_clip = img.getpixel((55, 45))
    assert _is_close(outside_clip, (255, 255, 255), tol=8), outside_clip


def test_three_levels_of_nested_clips_shrink_to_inner_most() -> None:
    """Three nested clips A ⊃ B ⊃ C — only the smallest survives."""
    doc, page = _make_doc()
    _set_contents(
        page,
        b"q\n"
        # A: 10..90, 10..90
        b"10 10 80 80 re\nW n\n"
        # B: 20..80, 20..80
        b"20 20 60 60 re\nW n\n"
        # C: 45..55, 45..55  (10x10 inner)
        b"45 45 10 10 re\nW n\n"
        b"0 0 0 rg\n"
        b"0 0 100 100 re\n"
        b"f\n"
        b"Q\n",
    )
    img = PDFRenderer(doc).render_image(0)
    # Inside the innermost — black.
    inside = img.getpixel((50, 50))
    assert inside[0] < 80 and inside[1] < 80 and inside[2] < 80, inside
    # Inside B but outside C — should be page background (clipped out).
    outside_c = img.getpixel((30, 30))
    assert _is_close(outside_c, (255, 255, 255), tol=8), outside_c
