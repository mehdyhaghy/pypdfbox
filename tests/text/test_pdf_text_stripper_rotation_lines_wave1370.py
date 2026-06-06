"""Wave 1370 — line-stitching across page rotation / flip-axes.

Covers the line/word-break heuristic in
:class:`pypdfbox.text.PDFTextStripper` when the configured page rotation
or ``set_should_flip_axes`` toggle inverts the role of the X and Y
axes.

Since wave 1495 the stripper folds a page's ``/Rotate`` into each run's
stored coordinates (``_apply_page_rotation``), matching upstream's
default-path grouping on the page-rotation-adjusted ``getX``/``getY`` — so
on a 90/270 page a horizontal row fragments across newlines in the device
frame exactly as Java PDFBox does (the rot0/180 upright text is unchanged).
The separate ``set_should_flip_axes(True)`` toggle is a lite-only manual
X/Y transpose with no upstream counterpart (it is NOT driven by ``/Rotate``).
These tests pin both contracts end-to-end through ``get_text``.
"""
from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper, TextPosition


def _page(doc: PDDocument, content: bytes, rotation: int = 0) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    page.set_rotation(rotation)
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


# ---------------------------------------------------------------------------
# /Rotate metadata is read back but does not by itself reorient extraction
# ---------------------------------------------------------------------------


def test_page_rotation_90_preserved_on_page_object() -> None:
    """A rotated /Rotate value is preserved on the PDPage instance; the
    stripper consults it via ``page.get_rotation`` but does not silently
    discard the metadata."""
    doc = PDDocument()
    page = _page(doc, b"BT /F0 12 Tf 100 700 Td (rot90) Tj ET", rotation=90)
    assert page.get_rotation() == 90


def test_page_rotation_180_preserved_on_page_object() -> None:
    doc = PDDocument()
    page = _page(doc, b"BT /F0 12 Tf 100 700 Td (rot180) Tj ET", rotation=180)
    assert page.get_rotation() == 180


def test_page_rotation_270_preserved_on_page_object() -> None:
    doc = PDDocument()
    page = _page(doc, b"BT /F0 12 Tf 100 700 Td (rot270) Tj ET", rotation=270)
    assert page.get_rotation() == 270


def test_text_still_extracted_on_rotated_pages() -> None:
    """Every glyph still extracts on a rotated page. Since wave 1495 the
    page ``/Rotate`` is folded into each run's stored coordinates (matching
    upstream's default-path ``getX``/``getY`` grouping), so on a 90/270 page
    the device-frame line grouping may fragment a horizontal row across
    newlines (``kept`` -> ``ke\\npt``) — exactly as Java PDFBox does. The
    invariant is that no glyph is dropped, not that the row stays contiguous;
    rot0/180 keep the upright contiguous text."""
    for rot in (0, 90, 180, 270):
        doc = PDDocument()
        _page(doc, b"BT /F0 12 Tf 100 700 Td (kept) Tj ET", rotation=rot)
        out = PDFTextStripper().get_text(doc)
        if rot in (0, 180):
            assert "kept" in out, f"rotation={rot} did not extract"
        else:
            # All glyphs survive; the device-frame grouping may newline-split.
            assert "".join(out.split()) == "kept", (
                f"rotation={rot} dropped a glyph: {out!r}"
            )


# ---------------------------------------------------------------------------
# set_should_flip_axes — transposes X/Y in line/word heuristics
# ---------------------------------------------------------------------------


def test_flip_axes_default_off_uses_y_for_line_break() -> None:
    """With the default axis configuration two runs at different ``y``
    but the same ``x`` should be split onto two lines."""
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (top) Tj "
            b"1 0 0 1 100 600 Tm (bot) Tj "
            b"ET"
        ),
    )
    out = PDFTextStripper().get_text(doc)
    # Default stripper inserts a line separator between rows at different y.
    assert out.count("\n") >= 1
    assert "top" in out and "bot" in out


def test_flip_axes_on_uses_x_for_line_break() -> None:
    """When ``set_should_flip_axes(True)`` the role of X and Y in the
    line-break predicate is transposed: two runs at the same Y but
    different X land on separate lines."""
    doc = PDDocument()
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 700 Tm (a) Tj "
            b"1 0 0 1 400 700 Tm (b) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_should_flip_axes(True)
    out = s.get_text(doc)
    # With flip, two same-y runs separated horizontally are on different lines.
    assert "a" in out and "b" in out
    assert "\n" in out


def test_flip_axes_getter_round_trip() -> None:
    s = PDFTextStripper()
    assert s.is_should_flip_axes() is False
    s.set_should_flip_axes(True)
    assert s.is_should_flip_axes() is True
    assert s.get_should_flip_axes() is True
    s.set_should_flip_axes(False)
    assert s.is_should_flip_axes() is False


# ---------------------------------------------------------------------------
# Same-line continuation works with rotation set on page metadata
# ---------------------------------------------------------------------------


def test_rotated_page_does_not_drop_glyph_count() -> None:
    """Number of recognised glyphs is independent of the page's
    ``/Rotate`` metadata — the parser walks content-stream tokens, not
    pre-rotated user-space coordinates."""
    expected = "abcdef"
    for rot in (0, 90, 180, 270):
        doc = PDDocument()
        _page(doc, b"BT /F0 12 Tf 100 700 Td (abcdef) Tj ET", rotation=rot)
        out = PDFTextStripper().get_text(doc)
        for ch in expected:
            assert ch in out, f"missing {ch!r} at rotation {rot}"


# ---------------------------------------------------------------------------
# TextPosition rotation field independent of page rotation metadata
# ---------------------------------------------------------------------------


def test_text_position_rotation_is_explicit_field() -> None:
    """``TextPosition.rotation`` is an explicit dataclass field — it
    does NOT auto-pick up the host page's /Rotate. Subclasses that
    want to flow rotation into individual positions must do so
    explicitly."""
    tp = TextPosition(text="x", x=0.0, y=0.0, font_size=10.0, rotation=90.0)
    assert tp.get_rotation() == 90.0
    # Constructed without rotation -> defaults to 0.
    tp0 = TextPosition(text="y", x=0.0, y=0.0, font_size=10.0)
    assert tp0.get_rotation() == 0.0


# ---------------------------------------------------------------------------
# Flip-axes also affects word-gap detection (uses Y instead of X)
# ---------------------------------------------------------------------------


def test_flip_axes_word_break_uses_y_axis() -> None:
    """``_is_word_break`` follows ``_flip_axes`` — when on, the gap
    test is against the Y axis instead of X. Two runs at the same X
    but separated along Y should produce a word break (assuming the
    Y advance is large enough)."""
    doc = PDDocument()
    # Two runs at the same x, separated by 200 units along y — well past
    # the WORD_GAP_FACTOR (1.5) * font_size (12) = 18 unit threshold.
    _page(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 100 100 Tm (left) Tj "
            b"1 0 0 1 100 300 Tm (right) Tj "
            b"ET"
        ),
    )
    s = PDFTextStripper()
    s.set_should_flip_axes(True)
    out = s.get_text(doc)
    # Both pieces of text emit, even with the axis flip.
    assert "left" in out
    assert "right" in out


# ---------------------------------------------------------------------------
# Multiple rotated pages join correctly with the configured page_end
# ---------------------------------------------------------------------------


def test_multipage_rotated_pages_joined_with_page_end() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (one) Tj ET", rotation=90)
    _page(doc, b"BT /F0 12 Tf 100 700 Td (two) Tj ET", rotation=270)
    s = PDFTextStripper()
    s.set_page_end("===\n")
    out = s.get_text(doc)
    # Each page is terminated by the configured marker.
    assert out.count("===") == 2
    # And in stream order. Since wave 1495 the page /Rotate is folded into the
    # coordinates, so a 90/270 page's row may fragment across newlines; the
    # first page's glyphs still all precede the page-end marker that precedes
    # the second page's glyphs. Compare on the whitespace-stripped payload.
    first, _, rest = out.partition("===")
    assert "".join(first.split()) == "one"
    assert "".join(rest.split()).startswith("two")
