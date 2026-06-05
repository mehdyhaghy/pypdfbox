"""Unit coverage for the upstream-faithful paragraph-separation classifier.

Wave 1492 ported ``isParagraphSeparation`` (PDFTextStripper.java:1611-1683)
into the lite stripper as ``_classify_paragraph_separation``. Unlike the
public 2-arg :meth:`PDFTextStripper.is_paragraph_separation` (which keeps the
legacy prev-only indent test for the flip-axes path and the existing unit
API), the classifier measures the indent / hanging-indent / list-item prongs
against the previous *line start* (``lastLineStartPosition``) and mutates the
``PositionWrapper`` flags rather than returning a bool. These tests drive it
directly with hand-built wrappers.

Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

from pypdfbox.text import PDFTextStripper, TextPosition
from pypdfbox.text.position_wrapper import PositionWrapper


def _wrap(
    x: float,
    y: float,
    *,
    text: str = "x",
    width: float = 10.0,
    font_size: float = 12.0,
    width_of_space: float = 5.0,
) -> PositionWrapper:
    return PositionWrapper(
        TextPosition(
            text=text,
            x=x,
            y=y,
            font_size=font_size,
            width=width,
            width_of_space=width_of_space,
        )
    )


def _classify(
    s: PDFTextStripper,
    cur: PositionWrapper,
    last: PositionWrapper,
    line_start: PositionWrapper | None,
    max_height: float = 12.0,
) -> None:
    s._classify_paragraph_separation(cur, last, line_start, max_height)


# ---------------------------------------------------------------------------
# Null last-line-start: upstream returns paragraph start unconditionally.
# ---------------------------------------------------------------------------


def test_null_line_start_is_paragraph_start() -> None:
    s = PDFTextStripper()
    cur = _wrap(40.0, 300.0)
    last = _wrap(40.0, 320.0)
    _classify(s, cur, last, None)
    assert cur.is_paragraph_start() is True


# ---------------------------------------------------------------------------
# Drop prong: y-gap vs the immediately-previous glyph.
# ---------------------------------------------------------------------------


def test_drop_prong_fires_on_large_y_gap() -> None:
    s = PDFTextStripper()
    line_start = _wrap(40.0, 360.0)
    last = _wrap(40.0, 360.0)
    # default drop_threshold 2.5 * max_height 12 = 30; 40 > 30.
    cur = _wrap(40.0, 320.0)
    _classify(s, cur, last, line_start)
    assert cur.is_paragraph_start() is True


def test_drop_prong_quiet_on_small_y_gap() -> None:
    s = PDFTextStripper()
    line_start = _wrap(40.0, 360.0)
    last = _wrap(40.0, 360.0)
    cur = _wrap(40.0, 345.0)  # 15 < 30
    _classify(s, cur, last, line_start)
    assert cur.is_paragraph_start() is False


# ---------------------------------------------------------------------------
# Indent prong: x-gap measured against the *line start*, not prev glyph.
# ---------------------------------------------------------------------------


def test_indent_vs_line_start_not_prev_glyph() -> None:
    s = PDFTextStripper()
    # line start at x=40; previous glyph drifted to x=200 mid-line.
    line_start = _wrap(40.0, 360.0)
    last = _wrap(200.0, 360.0)
    # current at x=80: 40 past the LINE START (> indent_threshold 2.0 * 5 = 10)
    # but 120 LEFT of the prev glyph — the legacy prev-only test would miss it.
    cur = _wrap(80.0, 340.0, width_of_space=5.0)
    _classify(s, cur, last, line_start)
    assert cur.is_paragraph_start() is True


def test_no_indent_when_aligned_with_line_start() -> None:
    s = PDFTextStripper()
    line_start = _wrap(40.0, 360.0)
    last = _wrap(40.0, 360.0)
    cur = _wrap(40.0, 340.0)  # flush with line start, small drop
    _classify(s, cur, last, line_start)
    assert cur.is_paragraph_start() is False


# ---------------------------------------------------------------------------
# Hanging indent: indented under a paragraph-start line stays in-paragraph.
# ---------------------------------------------------------------------------


def test_hanging_indent_under_paragraph_start() -> None:
    s = PDFTextStripper()
    line_start = _wrap(40.0, 360.0)
    line_start.set_paragraph_start()
    last = _wrap(40.0, 360.0)
    cur = _wrap(80.0, 340.0, width_of_space=5.0)  # indented past line start
    _classify(s, cur, last, line_start)
    # Indented under a paragraph start -> hanging indent, NOT a new paragraph.
    assert cur.is_hanging_indent() is True
    assert cur.is_paragraph_start() is False


def test_aligned_under_hanging_indent_inherits_hanging() -> None:
    s = PDFTextStripper()
    line_start = _wrap(40.0, 360.0)
    line_start.set_hanging_indent()
    last = _wrap(40.0, 360.0)
    cur = _wrap(40.0, 340.0)  # within 1/4 char of line start
    _classify(s, cur, last, line_start)
    assert cur.is_hanging_indent() is True
    assert cur.is_paragraph_start() is False


# ---------------------------------------------------------------------------
# List-item prong: aligned line sharing a list-item regex opens a paragraph.
# ---------------------------------------------------------------------------


def test_list_item_alignment_opens_paragraph() -> None:
    s = PDFTextStripper()
    line_start = _wrap(40.0, 360.0, text="1.")
    line_start.set_paragraph_start()
    last = _wrap(40.0, 360.0)
    cur = _wrap(40.0, 340.0, text="2.")  # aligned, both list items
    _classify(s, cur, last, line_start)
    assert cur.is_paragraph_start() is True


def test_aligned_non_list_under_paragraph_start_stays_in_paragraph() -> None:
    s = PDFTextStripper()
    line_start = _wrap(40.0, 360.0, text="Hello")
    line_start.set_paragraph_start()
    last = _wrap(40.0, 360.0)
    cur = _wrap(40.0, 340.0, text="world")  # aligned, no list pattern
    _classify(s, cur, last, line_start)
    assert cur.is_paragraph_start() is False


def test_left_of_line_start_without_hanging_is_paragraph() -> None:
    s = PDFTextStripper()
    # line start at x=40, NOT a paragraph start (so a leftward jump opens one).
    line_start = _wrap(40.0, 360.0)
    last = _wrap(40.0, 360.0)
    cur = _wrap(20.0, 340.0, width_of_space=5.0)  # 20 left, > one space (5)
    _classify(s, cur, last, line_start)
    assert cur.is_paragraph_start() is True
