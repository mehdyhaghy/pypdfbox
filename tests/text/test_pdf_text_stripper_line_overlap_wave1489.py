"""Wave 1489 — vertical-span ``overlap`` line grouping in the lite
``PDFTextStripper``.

Upstream ``PDFTextStripper.writePage`` groups TextPositions into lines via
a running vertical-overlap test (``maxYForLine`` / ``maxHeightForLine`` +
``overlap``) rather than a flat per-glyph baseline-delta test. These tests
exercise the ported helpers (``_overlaps_line``, ``_compute_font_height``)
and the multi-column-table line-grouping behaviour they enable, using
synthetic TextPositions so they run without the live Java oracle.
"""

from __future__ import annotations

from pypdfbox.text import PDFTextStripper, TextPosition


def _pos(text: str, x: float, y: float, *, font_size: float, height: float) -> TextPosition:
    return TextPosition(
        text=text, x=x, y=y, font_size=font_size, height=height, width=len(text) * 5.0
    )


def test_overlaps_line_shared_baseline() -> None:
    # within(.1) clause — effectively identical baselines.
    assert PDFTextStripper._overlaps_line(100.0, 8.0, 100.05, 8.0)  # noqa: SLF001
    assert not PDFTextStripper._overlaps_line(100.0, 8.0, 200.0, 8.0)  # noqa: SLF001


def test_overlaps_line_yup_span_containment() -> None:
    # y-up frame: glyph baseline 105 sits within the line span [100, 108].
    assert PDFTextStripper._overlaps_line(105.0, 8.0, 100.0, 8.0)  # noqa: SLF001
    # line baseline 100 sits within the glyph span [98, 106].
    assert PDFTextStripper._overlaps_line(98.0, 8.0, 100.0, 8.0)  # noqa: SLF001
    # disjoint spans (gap exceeds both heights) — not on the same line.
    assert not PDFTextStripper._overlaps_line(100.0, 5.0, 110.0, 5.0)  # noqa: SLF001


def test_overlaps_line_reset_sentinels_open_first_line() -> None:
    # The reset sentinels (max_y = -inf, max_height = -1) must report no
    # overlap so the very first glyph opens the line.
    assert not PDFTextStripper._overlaps_line(  # noqa: SLF001
        100.0, 8.0, float("-inf"), -1.0
    )


def test_value_cell_groups_with_wrapped_label() -> None:
    """The eu-001 pattern in miniature: a wrapped label continuation and a
    value cell on a slightly different baseline (Y-delta < glyph height)
    group onto ONE logical line — not split, as the old flat 0.5·fontSize
    test did."""
    stripper = PDFTextStripper()
    # font_size 8, real glyph height ~5.6 (0.7·em). Label continuation at
    # y=344.78, value cell at y=349.64 (delta 4.86 < height 5.6).
    positions = [
        _pos("(as HCl)", x=100.0, y=344.78, font_size=8.0, height=5.6),
        _pos("10 000 - -", x=300.0, y=349.64, font_size=8.0, height=5.6),
    ]
    out = stripper._format_positions(positions)  # noqa: SLF001
    assert "\n" not in out.strip()
    assert out.startswith("(as HCl)")
    assert "10 000 - -" in out


def test_distinct_lines_split_with_real_height() -> None:
    """Two glyphs a full line apart (delta 36, real glyph height ~33 for a
    48pt font) are vertically disjoint and DO break — the regression the
    full-font-size height proxy caused (PDFBOX-3062 title block)."""
    stripper = PDFTextStripper()
    positions = [
        _pos("First", x=100.0, y=366.72, font_size=48.0, height=33.0),
        _pos("among", x=100.0, y=330.72, font_size=48.0, height=33.0),
    ]
    out = stripper._format_positions(positions)  # noqa: SLF001
    assert out.splitlines()[:2] == ["First", "among"]


def test_height_accessor_falls_back_to_font_size() -> None:
    # A synthetic position with no threaded height keeps the legacy proxy.
    p = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0)
    assert p.get_height() == 12.0
    assert p.get_height_dir() == 12.0
    # A threaded height is returned verbatim.
    p2 = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0, height=8.4)
    assert p2.get_height() == 8.4
    assert p2.get_height_dir() == 8.4


def test_compute_font_height_none_font_is_half_em() -> None:
    assert PDFTextStripper()._compute_font_height(None) == 0.5  # noqa: SLF001
