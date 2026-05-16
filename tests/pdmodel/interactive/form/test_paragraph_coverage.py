"""Coverage-boost tests for ``pypdfbox.pdmodel.interactive.form.paragraph``.

Targets the line-wrap branch (trailing-whitespace overflow, flush + carry
over to a new line), the trailing-whitespace deduction inside
``Line.calculate_width``, the ``build_prefix_widths`` prefix-sum builder,
and the ``find_max_fitting_chars`` binary search (including the
single-char-overflow PDFBOX-6082 guard).
"""

from __future__ import annotations

from pypdfbox.pdmodel.interactive.form.paragraph import Line, Paragraph
from pypdfbox.pdmodel.interactive.form.word import Word


class _StubFont:
    """Width-per-char font stub mimicking PDFont.get_string_width.

    Upstream returns widths in 1/1000-em units; we just multiply by the
    width-per-char so callers know exactly what scale every call returns.
    """

    def __init__(self, width_per_char: float = 1000.0) -> None:
        self._w = float(width_per_char)

    def get_string_width(self, text: str) -> float:
        return self._w * len(text)


# ---------- Line.calculate_width trailing-whitespace branch ---------------


def test_line_calculate_width_strips_trailing_whitespace_on_last_word() -> None:
    """Last word's trailing space is subtracted from the laid-out width.

    scale = font_size / 1000 = 1.0; ``get_string_width(' ')`` returns
    ``1000 * 1 = 1000``; subtracted-back width is ``1000 * scale = 1000``.
    """
    line = Line()
    w1 = Word("hello ")
    w1.set_attributes({"WIDTH": 600.0})
    w2 = Word("world ")
    w2.set_attributes({"WIDTH": 600.0})
    line.add_word(w1)
    line.add_word(w2)
    font = _StubFont(1000.0)
    width = line.calculate_width(font, 1000.0)
    # 600 + 600 - 1000 (single space at scale 1.0) == 200
    assert width == 200.0


def test_line_calculate_width_keeps_trailing_non_whitespace() -> None:
    line = Line()
    w = Word("hi")  # no trailing whitespace
    w.set_attributes({"WIDTH": 200.0})
    line.add_word(w)
    assert line.calculate_width(_StubFont(1000.0), 1000.0) == 200.0


def test_line_inter_word_spacing() -> None:
    line = Line()
    for _ in range(3):
        w = Word("ab")
        w.set_attributes({"WIDTH": 100.0})
        line.add_word(w)
    line.set_width(300.0)
    # 2 gaps, need to distribute 60.0 more width -> 30.0 each
    assert line.get_inter_word_spacing(360.0) == 30.0


# ---------- Paragraph.get_lines wrap branch ------------------------------


def test_get_lines_wraps_when_overflow_carries_to_new_line() -> None:
    """Two long-enough words that overflow the requested width on the
    second word — Line 1 is flushed, Line 2 begins with the second word.
    """
    para = Paragraph("aaa bbb")
    # width_per_char=1000 with font_size=1000 -> per-char scale 1.0 -> each
    # 3-letter word ~3.0 units + trailing space ~1.0 unit = 4.0 units total.
    font = _StubFont(1000.0)
    # width=4.5 -> 'aaa ' fits (4.0); add 'bbb' (3.0) -> overflows -> flush + start new line.
    lines = para.get_lines(font, 1000.0, 4.5)
    assert len(lines) == 2
    # Line 1: just "aaa "
    assert [w.get_text() for w in lines[0].get_words()] == ["aaa "]
    # Line 2: "bbb"
    assert [w.get_text() for w in lines[1].get_words()] == ["bbb"]


def test_get_lines_trailing_whitespace_pushes_us_over_branch() -> None:
    """When a word + trailing space exceeds width, the trailing-ws width
    is subtracted back (covers lines 107-109).
    """
    para = Paragraph("aa bb")
    font = _StubFont(1000.0)
    # width = 2.5 -> 'aa ' is 3.0 with the space; subtract space (1.0) -> 2.0 fits
    # Then 'bb' (2.0) added -> line_width 4.0 -> overflow -> flush + new line.
    lines = para.get_lines(font, 1000.0, 2.5)
    assert len(lines) == 2


def test_get_lines_zero_width_returns_empty() -> None:
    para = Paragraph("hello world")
    assert para.get_lines(_StubFont(1000.0), 1000.0, 0.0) == []
    assert para.get_lines(_StubFont(1000.0), 1000.0, -10.0) == []


def test_get_lines_single_line_for_short_text() -> None:
    para = Paragraph("hi")
    lines = para.get_lines(_StubFont(1000.0), 1000.0, 1000.0)
    assert len(lines) == 1
    assert [w.get_text() for w in lines[0].get_words()] == ["hi"]


# ---------- Paragraph.build_prefix_widths -------------------------------


def test_build_prefix_widths_empty_string() -> None:
    out = Paragraph.build_prefix_widths("", _StubFont(1000.0), 1.0)
    assert out == [0.0]


def test_build_prefix_widths_monotonic_increasing() -> None:
    out = Paragraph.build_prefix_widths("abcd", _StubFont(500.0), 0.5)
    # Each char width = 500 * 0.5 = 250.0
    assert out == [0.0, 250.0, 500.0, 750.0, 1000.0]


def test_build_prefix_widths_unicode_codepoint_iteration() -> None:
    # BMP chars iterate one code point at a time.
    out = Paragraph.build_prefix_widths("éé", _StubFont(100.0), 1.0)
    assert out == [0.0, 100.0, 200.0]


# ---------- Paragraph.find_max_fitting_chars ----------------------------


def test_find_max_fitting_chars_basic() -> None:
    prefix = [0.0, 100.0, 200.0, 300.0, 400.0]
    # width=250 -> largest k with prefix[k] < 250 is k=2 (200 < 250)
    assert Paragraph.find_max_fitting_chars(prefix, 250.0) == 2


def test_find_max_fitting_chars_all_fit() -> None:
    prefix = [0.0, 10.0, 20.0, 30.0]
    assert Paragraph.find_max_fitting_chars(prefix, 1000.0) == 3


def test_find_max_fitting_chars_single_char_overflow_returns_one() -> None:
    """PDFBOX-6082: even when a single char overflows, return 1 rather
    than 0 so the caller still makes progress.
    """
    prefix = [0.0, 500.0, 1000.0]
    assert Paragraph.find_max_fitting_chars(prefix, 10.0) == 1


def test_find_max_fitting_chars_boundary_equality_excluded() -> None:
    """The binary search uses strict less-than, so a prefix exactly
    equal to the target width does not count as fitting.
    """
    prefix = [0.0, 100.0, 200.0, 300.0]
    assert Paragraph.find_max_fitting_chars(prefix, 200.0) == 1
