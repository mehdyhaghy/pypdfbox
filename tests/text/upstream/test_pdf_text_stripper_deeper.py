"""Upstream-shaped tests for the Wave 41 deeper-edge round-out of
:class:`PDFTextStripper`.

The upstream Java surface this file pins:

  - ``setShouldFlipAxes`` / ``isShouldFlipAxes``
  - ``setShouldSeparateByBeads`` actually buckets glyphs by thread beads
  - ``shouldSkipGlyph`` filters individual glyphs
  - ``isParagraphSeparation`` heuristic (drop + indent prongs)
  - ``writeStringWithPositions`` invariants (non-empty text + positions)

Synthetic content streams stand in for the upstream test fixtures so the
lite stripper can drive each path end-to-end.
"""

from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead
from pypdfbox.text import PDFTextStripper, TextPosition


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


# ---------------------------------------------------------------------------
# upstream: PDFTextStripper#setShouldFlipAxes
# ---------------------------------------------------------------------------


def test_set_should_flip_axes_round_trip() -> None:
    s = PDFTextStripper()
    assert s.is_should_flip_axes() is False
    s.set_should_flip_axes(True)
    assert s.is_should_flip_axes() is True


# ---------------------------------------------------------------------------
# upstream: PDFTextStripper#setShouldSeparateByBeads (bead bucketing)
# ---------------------------------------------------------------------------


def test_set_should_separate_by_beads_orders_by_bead_chain() -> None:
    """Per upstream: with ``setShouldSeparateByBeads(true)``, glyphs in
    each bead's rectangle are emitted in bead-chain order even when the
    content stream paints them out of order."""
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"1 0 0 1 400 700 Tm (right) Tj "  # column 2, painted first
            b"1 0 0 1 100 700 Tm (left) Tj "   # column 1
            b"ET"
        ),
    )
    beads = []
    # Bead order: column 1, then column 2 — so "left" should come first.
    for r in (
        PDRectangle(50.0, 600.0, 250.0, 750.0),
        PDRectangle(350.0, 600.0, 550.0, 750.0),
    ):
        b = PDThreadBead()
        b.set_page(page)
        b.set_rectangle(r)
        beads.append(b)
    page.set_thread_beads(beads)
    out = PDFTextStripper().get_text(doc)
    assert out.index("left") < out.index("right")


# ---------------------------------------------------------------------------
# upstream: PDFTextStripper#shouldSkipGlyph
# ---------------------------------------------------------------------------


def test_should_skip_glyph_default_keeps_run() -> None:
    pos = TextPosition(text="x", x=0.0, y=0.0, font_size=10.0)
    assert PDFTextStripper().should_skip_glyph(pos) is False


def test_should_skip_glyph_override_drops_filtered_run() -> None:
    class DropX(PDFTextStripper):
        def should_skip_glyph(self, text: TextPosition) -> bool:  # type: ignore[override]
            return text.text == "x"

    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf "
            b"100 700 Td (a) Tj "
            b"50 0 Td (x) Tj "
            b"50 0 Td (b) Tj "
            b"ET"
        ),
    )
    out = DropX().get_text(doc)
    assert "a" in out and "b" in out
    assert out.count("x") == 0


# ---------------------------------------------------------------------------
# upstream: PDFTextStripper#isParagraphSeparation
# ---------------------------------------------------------------------------


def test_is_paragraph_separation_drop_prong() -> None:
    s = PDFTextStripper()
    prev = TextPosition(text="a", x=100.0, y=700.0, font_size=12.0)
    pos = TextPosition(text="b", x=100.0, y=300.0, font_size=12.0)
    assert s.is_paragraph_separation(pos, prev) is True


def test_is_paragraph_separation_indent_prong() -> None:
    s = PDFTextStripper()
    prev = TextPosition(
        text="a", x=100.0, y=700.0, font_size=12.0, width_of_space=4.0
    )
    pos = TextPosition(
        text="b", x=140.0, y=700.0, font_size=12.0, width_of_space=4.0
    )
    assert s.is_paragraph_separation(pos, prev) is True


# ---------------------------------------------------------------------------
# upstream: PDFTextStripper#writeString(String, List<TextPosition>)
# ---------------------------------------------------------------------------


def test_write_string_with_positions_invariant_empty_text_is_noop() -> None:
    out: list[str] = []
    s = PDFTextStripper()
    s.write_string_with_positions(
        "", [TextPosition(text="", x=0.0, y=0.0, font_size=10.0)], out.append
    )
    assert out == []


def test_write_string_with_positions_invariant_empty_positions_is_noop() -> None:
    out: list[str] = []
    PDFTextStripper().write_string_with_positions("hi", [], out.append)
    assert out == []


def test_write_string_with_positions_routes_to_write_string() -> None:
    seen: list[str] = []

    class Capturing(PDFTextStripper):
        def write_string(self, text, text_positions, sink) -> None:  # type: ignore[override]
            seen.append(text)
            sink(text)

    out: list[str] = []
    Capturing().write_string_with_positions(
        "hi", [TextPosition(text="hi", x=0.0, y=0.0, font_size=10.0)], out.append
    )
    assert seen == ["hi"]
    assert out == ["hi"]
