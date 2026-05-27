"""Wave 1370 — region-clipping accuracy + multi-region word distribution.

Tightens the contract for :class:`PDFTextStripperByArea`'s boundary
behaviour and multi-region routing:

  - Edge-of-rectangle clipping is inclusive (a position whose origin
    falls exactly on the boundary is included).
  - A glyph that falls inside *no* region is dropped entirely (no
    spillover into the document-level extraction).
  - Position routing into multiple overlapping regions reproduces the
    *same* ``TextPosition`` in each region (not a copy — the bin entry
    is the same object).
  - Removing a region after extraction wipes the per-region buffer
    so a re-read of the same name returns the empty default.
  - ``setLineSeparator("")`` flows through to region text (upstream's
    parity behaviour from ``PDFTextStripperByAreaTest.testSomeMethod``).
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripperByArea


def _make_page(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


# ---------------------------------------------------------------------------
# Edge-of-rectangle inclusivity
# ---------------------------------------------------------------------------


def test_region_left_and_top_edge_inclusive() -> None:
    """A position on the rectangle's left edge (``min_x``) and top edge
    (``max_y`` in user space) is included.

    Mirrors Java ``Rectangle2D.contains`` after the user-space y-flip:
    the *left* x bound and the *upper* (user-space ``max_y``) y bound are
    inclusive. Verified against the live PDFBox oracle in
    ``tests/text/oracle/test_text_sort_area_oracle.py``.
    """
    doc = PDDocument()
    page = _make_page(doc, b"BT /F0 12 Tf 100 700 Td (edge) Tj ET")
    s = PDFTextStripperByArea()
    # Origin (100, 700) sits on the region's left edge (x == min_x) and
    # its top edge (y == max_y == 700 + 50 - 50). Use a rect whose
    # max_y == 700 so the top edge is exactly the origin's y.
    s.add_region("r", (100.0, 650.0, 200.0, 50.0))  # x[100,300] y[650,700]
    s.extract_regions(page)
    assert "edge" in s.get_text_for_region("r")


def test_region_right_edge_exclusive() -> None:
    """A position exactly on the rectangle's right edge (``max_x``) is
    *excluded* — Java ``Rectangle2D.contains`` is half-open on the right
    (``x < rx + rw``). Oracle-verified."""
    doc = PDDocument()
    page = _make_page(doc, b"BT /F0 12 Tf 100 700 Td (edge) Tj ET")
    s = PDFTextStripperByArea()
    # Right edge (max_x) lands exactly on the origin's x (100).
    s.add_region("r", (0.0, 650.0, 100.0, 100.0))  # x[0,100] y[650,750]
    s.extract_regions(page)
    assert s.get_text_for_region("r").strip() == ""


def test_region_bottom_edge_exclusive() -> None:
    """A position exactly on the rectangle's bottom edge (user-space
    ``min_y``) is *excluded*. The Java y-flip turns the half-open
    bottom (``y < ry + rh`` in device space) into an exclusive
    user-space ``min_y``. Oracle-verified."""
    doc = PDDocument()
    page = _make_page(doc, b"BT /F0 12 Tf 100 700 Td (edge) Tj ET")
    s = PDFTextStripperByArea()
    # min_y lands exactly on the origin's y (700).
    s.add_region("r", (50.0, 700.0, 200.0, 50.0))  # x[50,250] y[700,750]
    s.extract_regions(page)
    assert s.get_text_for_region("r").strip() == ""


def test_region_just_outside_lower_left_drops_text() -> None:
    """One unit below the rectangle's lower-left corner — the position
    falls outside, so it must not be captured."""
    doc = PDDocument()
    page = _make_page(doc, b"BT /F0 12 Tf 100 700 Td (out) Tj ET")
    s = PDFTextStripperByArea()
    # Region starts at (101, 701) -> position (100, 700) is below+left.
    s.add_region("r", (101.0, 701.0, 200.0, 50.0))
    s.extract_regions(page)
    assert s.get_text_for_region("r").strip() == ""


# ---------------------------------------------------------------------------
# Multi-region distribution: each region gets its own slice
# ---------------------------------------------------------------------------


def test_multi_region_distribution_independent() -> None:
    """Four glyphs across two distinct rectangles — each region sees
    only the glyphs whose origin falls inside its rectangle."""
    doc = PDDocument()
    page = _make_page(
        doc,
        b"BT /F0 12 Tf 100 700 Td (one) Tj ET "
        b"BT /F0 12 Tf 100 600 Td (two) Tj ET "
        b"BT /F0 12 Tf 100 500 Td (three) Tj ET "
        b"BT /F0 12 Tf 100 400 Td (four) Tj ET ",
    )
    s = PDFTextStripperByArea()
    # Two non-overlapping rectangles, each catching exactly two rows.
    s.add_region("top", (50.0, 550.0, 500.0, 200.0))    # catches y in [550,750]
    s.add_region("bot", (50.0, 350.0, 500.0, 200.0))    # catches y in [350,550]
    s.extract_regions(page)
    top_text = s.get_text_for_region("top")
    bot_text = s.get_text_for_region("bot")
    assert "one" in top_text and "two" in top_text
    assert "three" in bot_text and "four" in bot_text
    # And no cross-contamination.
    assert "three" not in top_text and "four" not in top_text
    assert "one" not in bot_text and "two" not in bot_text


def test_multi_region_overlapping_shares_position_objects() -> None:
    """Two overlapping rectangles capturing the same position get the
    SAME ``TextPosition`` (not a copy) inserted into both bins."""
    doc = PDDocument()
    page = _make_page(doc, b"BT /F0 12 Tf 100 700 Td (shared) Tj ET")
    s = PDFTextStripperByArea()
    s.add_region("a", (50.0, 680.0, 500.0, 30.0))
    s.add_region("b", (90.0, 695.0, 200.0, 10.0))
    s.extract_regions(page)
    a_bin = s._region_character_list["a"]
    b_bin = s._region_character_list["b"]
    assert len(a_bin) == 1 and len(b_bin) == 1
    # Same instance, not a clone.
    assert a_bin[0] is b_bin[0]


def test_glyph_outside_every_region_is_dropped() -> None:
    """A glyph whose origin falls in NO region is silently dropped —
    region-strippers do not emit an "out-of-region" bucket."""
    doc = PDDocument()
    page = _make_page(
        doc,
        b"BT /F0 12 Tf 100 700 Td (inside) Tj ET "
        b"BT /F0 12 Tf 100 100 Td (orphan) Tj ET ",
    )
    s = PDFTextStripperByArea()
    s.add_region("r", (50.0, 690.0, 500.0, 30.0))  # catches (100, 700)
    s.extract_regions(page)
    captured = s.get_text_for_region("r")
    assert "inside" in captured
    assert "orphan" not in captured
    # No hidden bucket for orphans.
    assert "orphan" not in str(s._region_character_list)


# ---------------------------------------------------------------------------
# Re-extract on a different page clears prior text but keeps region defs
# ---------------------------------------------------------------------------


def test_reextract_clears_prior_bin_keeps_region_defs() -> None:
    doc = PDDocument()
    page1 = _make_page(doc, b"BT /F0 12 Tf 100 700 Td (p1) Tj ET")
    page2 = _make_page(doc, b"BT /F0 12 Tf 100 700 Td (p2) Tj ET")
    s = PDFTextStripperByArea()
    s.add_region("r", (50.0, 690.0, 500.0, 30.0))
    s.extract_regions(page1)
    assert "p1" in s.get_text_for_region("r")

    s.extract_regions(page2)
    captured = s.get_text_for_region("r")
    assert "p2" in captured
    assert "p1" not in captured
    # Region def is untouched.
    assert s.get_regions() == ["r"]


def test_extract_with_no_registered_regions_is_silent_noop() -> None:
    """No regions configured -> extract_regions doesn't raise and the
    per-region buffer stays empty."""
    doc = PDDocument()
    page = _make_page(doc, b"BT /F0 12 Tf 100 700 Td (any) Tj ET")
    s = PDFTextStripperByArea()
    # No add_region calls.
    s.extract_regions(page)
    # Nothing recorded.
    assert s.get_regions() == []
    assert s.get_text_for_region("any-name") == ""


# ---------------------------------------------------------------------------
# Line-separator override at the by-area level
# ---------------------------------------------------------------------------


def test_line_separator_override_applies_inside_region() -> None:
    """``set_line_separator("|")`` replaces the default newline used for
    the line-break separator inside region-formatted text. Mirrors
    upstream's PDFTextStripperByAreaTest.testSomeMethod override (it
    used ``""`` to collapse runs onto one logical line)."""
    doc = PDDocument()
    page = _make_page(
        doc,
        # Two runs at very different y -> stripper inserts a line break.
        b"BT /F0 12 Tf 100 700 Td (top) Tj ET "
        b"BT /F0 12 Tf 100 600 Td (mid) Tj ET ",
    )
    s = PDFTextStripperByArea()
    s.set_line_separator("|")
    # Also collapse paragraph terminators so the lite stripper's
    # default "\n" paragraph_end doesn't sneak past the assertion.
    s.set_paragraph_end("")
    s.add_region("r", (0.0, 0.0, 612.0, 792.0))
    s.extract_regions(page)
    out = s.get_text_for_region("r")
    # No raw newlines — they were replaced by "|".
    assert "\n" not in out
    assert "|" in out
    assert "top" in out and "mid" in out


# ---------------------------------------------------------------------------
# Region rejected when rect is not a recognised shape — fails fast
# ---------------------------------------------------------------------------


def test_add_region_rejects_3_element_tuple() -> None:
    s = PDFTextStripperByArea()
    with pytest.raises(TypeError):
        s.add_region("r", (1.0, 2.0, 3.0))  # type: ignore[arg-type]


def test_add_region_rejects_dict() -> None:
    s = PDFTextStripperByArea()
    with pytest.raises(TypeError):
        s.add_region("r", {"x": 1.0})  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Sort-by-position interacts correctly with region extraction
# ---------------------------------------------------------------------------


def test_sort_by_position_does_not_leak_across_regions() -> None:
    """Each region is sorted independently — content-stream order in
    one region must not perturb the other region's reading order."""
    doc = PDDocument()
    page = _make_page(
        doc,
        # Region A (top half): two glyphs in reverse stream order.
        b"BT /F0 12 Tf 100 700 Td (a-low) Tj ET "
        b"BT /F0 12 Tf 100 750 Td (a-high) Tj ET "
        # Region B (bot half): two glyphs in reverse stream order.
        b"BT /F0 12 Tf 100 300 Td (b-low) Tj ET "
        b"BT /F0 12 Tf 100 350 Td (b-high) Tj ET ",
    )
    s = PDFTextStripperByArea()
    s.set_sort_by_position(True)
    s.add_region("top", (50.0, 690.0, 500.0, 80.0))
    s.add_region("bot", (50.0, 290.0, 500.0, 80.0))
    s.extract_regions(page)
    top = s.get_text_for_region("top")
    bot = s.get_text_for_region("bot")
    # Within top, high-y appears before low-y (descending y -> reading order).
    assert top.index("a-high") < top.index("a-low")
    # Same independence for bot.
    assert bot.index("b-high") < bot.index("b-low")
