"""Wave 1370 — word-detection heuristics on :class:`PDFTextStripper`.

Targets the four configurable thresholds that gate the line/word
predicates:

  - ``drop_threshold``       — vertical gap > drop_threshold * line_height
                               counts as a paragraph drop.
  - ``indent_threshold``     — horizontal indent > indent_threshold *
                               space_width counts as an indented paragraph
                               start (only consulted after a line break).
  - ``spacing_tolerance``    — round-trip only; the lite stripper holds
                               the value for upstream parity.
  - ``average_char_tolerance`` — same.

Behavioural checks drive ``is_paragraph_separation`` and
``is_para_break_indented`` directly with hand-built ``TextPosition``
objects so the heuristic stays disentangled from PDF parsing quirks.
"""
from __future__ import annotations

from pypdfbox.text import PDFTextStripper, TextPosition


def _tp(x: float, y: float, *, width: float = 10.0, font_size: float = 12.0,
        width_of_space: float = 0.0) -> TextPosition:
    return TextPosition(
        text="x",
        x=x,
        y=y,
        font_size=font_size,
        width=width,
        width_of_space=width_of_space,
    )


# ---------------------------------------------------------------------------
# is_paragraph_separation — drop prong
# ---------------------------------------------------------------------------


def test_drop_prong_fires_when_y_gap_exceeds_drop_threshold() -> None:
    s = PDFTextStripper()
    # Default drop_threshold is 2.5 and font_size 12 -> gap > 30.
    prev = _tp(x=100.0, y=700.0)
    pos = _tp(x=100.0, y=665.0)  # 35 below
    assert s.is_paragraph_separation(pos, prev) is True


def test_drop_prong_does_not_fire_when_y_gap_under_threshold() -> None:
    s = PDFTextStripper()
    prev = _tp(x=100.0, y=700.0)
    # Within the threshold (20 < 30 = 2.5 * 12).
    pos = _tp(x=100.0, y=680.0)
    assert s.is_paragraph_separation(pos, prev) is False


def test_drop_threshold_can_be_tightened() -> None:
    """A tighter drop_threshold makes smaller gaps register as a
    paragraph drop."""
    s = PDFTextStripper()
    s.set_drop_threshold(1.0)
    prev = _tp(x=100.0, y=700.0)
    pos = _tp(x=100.0, y=685.0)  # 15 below, > 1.0 * 12 = 12
    assert s.is_paragraph_separation(pos, prev) is True


def test_drop_threshold_can_be_loosened() -> None:
    """A loose drop_threshold means a large gap doesn't trigger a drop."""
    s = PDFTextStripper()
    s.set_drop_threshold(10.0)
    prev = _tp(x=100.0, y=700.0)
    pos = _tp(x=100.0, y=600.0)  # 100 < 120 = 10 * 12
    # Indent prong might still fire — clamp x.
    assert s.is_paragraph_separation(pos, prev) is False


# ---------------------------------------------------------------------------
# is_paragraph_separation — indent prong (only after a line break)
# ---------------------------------------------------------------------------


def test_indent_prong_fires_when_x_jumps_right() -> None:
    """A rightward x-jump larger than indent_threshold * space_width
    counts as an indented paragraph start."""
    s = PDFTextStripper()
    # space_width fallback = 0.25 * font_size = 3 units. indent_threshold
    # default = 2.0 -> 6 unit threshold.
    prev = _tp(x=100.0, y=700.0)
    pos = _tp(x=110.0, y=700.0)  # +10 > 6
    # Drop prong won't fire because y gap is 0.
    assert s.is_paragraph_separation(pos, prev) is True


def test_indent_prong_does_not_fire_for_aligned_lines() -> None:
    s = PDFTextStripper()
    prev = _tp(x=100.0, y=700.0)
    pos = _tp(x=101.0, y=700.0)  # tiny right shift, under threshold
    assert s.is_paragraph_separation(pos, prev) is False


def test_is_para_break_indented_isolates_indent_prong() -> None:
    """``is_para_break_indented`` ignores the drop prong — only the
    indent test should drive the result."""
    s = PDFTextStripper()
    prev = _tp(x=100.0, y=700.0)
    # Huge drop AND no indent — indent prong returns False even though
    # the combined is_paragraph_separation would also return True via
    # the drop prong.
    pos = _tp(x=100.0, y=100.0)
    assert s.is_para_break_indented(pos, prev) is False
    assert s.is_paragraph_separation(pos, prev) is True


def test_indent_threshold_uses_width_of_space_when_set() -> None:
    """When the previous position carries a non-zero ``width_of_space``
    the indent prong scales against that value instead of the 0.25 *
    font_size fallback."""
    s = PDFTextStripper()
    prev = _tp(x=100.0, y=700.0, width_of_space=8.0)
    # threshold = 2.0 * 8 = 16. 17-unit indent fires; 15-unit does not.
    pos_hit = _tp(x=117.0, y=700.0)
    pos_miss = _tp(x=115.0, y=700.0)
    assert s.is_para_break_indented(pos_hit, prev) is True
    assert s.is_para_break_indented(pos_miss, prev) is False


# ---------------------------------------------------------------------------
# start_of_paragraph alias
# ---------------------------------------------------------------------------


def test_start_of_paragraph_aliases_is_paragraph_separation() -> None:
    s = PDFTextStripper()
    prev = _tp(x=100.0, y=700.0)
    pos = _tp(x=100.0, y=600.0)  # large drop
    # Both names dispatch to the same body.
    assert s.start_of_paragraph(pos, prev) == s.is_paragraph_separation(pos, prev)


# ---------------------------------------------------------------------------
# spacing_tolerance / average_char_tolerance — round-trip only today,
# but the values must survive a get_text walk
# ---------------------------------------------------------------------------


def test_spacing_tolerance_survives_get_text_walk() -> None:
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle

    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(b"BT /F0 12 Tf 100 700 Td (x) Tj ET")
    page.set_contents(stream)
    doc.add_page(page)

    s = PDFTextStripper()
    s.set_spacing_tolerance(0.8)
    s.get_text(doc)
    # The stored value is unchanged by the walk (it's an inert holder).
    assert s.get_spacing_tolerance() == 0.8


def test_average_char_tolerance_survives_get_text_walk() -> None:
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle

    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(b"BT /F0 12 Tf 100 700 Td (x) Tj ET")
    page.set_contents(stream)
    doc.add_page(page)

    s = PDFTextStripper()
    s.set_average_char_tolerance(0.66)
    s.get_text(doc)
    assert s.get_average_char_tolerance() == 0.66


# ---------------------------------------------------------------------------
# Line-collision suppression: suppress_duplicate_overlapping_text
# (upstream calls the same heuristic "maxNumberOfLineCollisions" via
# its line-walker; the lite stripper folds it into the duplicate-drop pass)
# ---------------------------------------------------------------------------


def test_duplicate_overlapping_text_dropped_by_default() -> None:
    """Two glyphs with the same unicode painted at the same location
    are collapsed into one — the "fake bold" trick where a producer
    paints the same glyph twice for emphasis."""
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle

    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    # Two Tj at the same Tm — duplicate-suppression should keep only one.
    stream.set_data(
        b"BT /F0 12 Tf 1 0 0 1 100 700 Tm (D) Tj "
        b"1 0 0 1 100 700 Tm (D) Tj ET"
    )
    page.set_contents(stream)
    doc.add_page(page)

    s = PDFTextStripper()
    assert s.is_suppress_duplicate_overlapping_text() is True
    out = s.get_text(doc)
    # Exactly one "D" — duplicate-overlap suppression dropped the second.
    assert out.count("D") == 1


def test_duplicate_overlapping_text_kept_when_suppression_off() -> None:
    """Disabling duplicate suppression lets both copies through."""
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle

    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(
        b"BT /F0 12 Tf 1 0 0 1 100 700 Tm (D) Tj "
        b"1 0 0 1 100 700 Tm (D) Tj ET"
    )
    page.set_contents(stream)
    doc.add_page(page)

    s = PDFTextStripper()
    s.set_suppress_duplicate_overlapping_text(False)
    out = s.get_text(doc)
    # Both glyphs survive.
    assert out.count("D") == 2
