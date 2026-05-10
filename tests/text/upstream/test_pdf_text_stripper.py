"""Upstream-parity tests for :class:`pypdfbox.text.PDFTextStripper`.

The upstream JUnit suite ``TestTextStripper.java`` is a corpus-driven
diff harness against PDFBox's bundled fixtures and is not portable
verbatim — those tests would require the entire upstream
``src/test/resources/input`` tree. This file pins the upstream-named
helper methods (``within``, ``overlap``, ``multiplyFloat``,
``hasFontOrSizeChanged``, ``removeContainedSpaces``, ``normalizeWord``,
``handleDirection``, ``parseBidiFile``) added in wave 1258 for 1:1
parity with PDFTextStripper.java. Each test maps to the upstream Java
line referenced inline so the intent stays diff-able against future
re-syncs.
"""

from __future__ import annotations

import io

from pypdfbox.text import PDFTextStripper, TextPosition, WordWithTextPositions
from pypdfbox.text.pdf_text_stripper import _LineItem
from pypdfbox.text.position_wrapper import PositionWrapper

# ---------------------------------------------------------------------------
# within (PDFTextStripper.java:857)
# ---------------------------------------------------------------------------


def test_within_strict_lower_and_upper_bound() -> None:
    """``second < first + variance && second > first - variance`` —
    strict ``<`` on both sides per the upstream sources."""
    assert PDFTextStripper.within(5.0, 5.05, 0.1)
    assert not PDFTextStripper.within(5.0, 5.1, 0.1)  # equal-to-upper excluded
    assert not PDFTextStripper.within(5.0, 4.9, 0.1)  # equal-to-lower excluded
    assert PDFTextStripper.within(5.0, 5.0, 0.1)  # exact center is within


# ---------------------------------------------------------------------------
# overlap (PDFTextStripper.java:762)
# ---------------------------------------------------------------------------


def test_overlap_returns_true_for_within_tolerance() -> None:
    """First branch: ``within(y1, y2, .1f)``."""
    assert PDFTextStripper.overlap(10.0, 5.0, 10.05, 5.0)


def test_overlap_returns_true_for_y2_inside_first_span() -> None:
    """Second branch: ``y2 <= y1 && y2 >= y1 - height1``."""
    assert PDFTextStripper.overlap(10.0, 5.0, 8.0, 1.0)


def test_overlap_returns_true_for_y1_inside_second_span() -> None:
    """Third branch: ``y1 <= y2 && y1 >= y2 - height2``."""
    assert PDFTextStripper.overlap(8.0, 1.0, 10.0, 5.0)


def test_overlap_returns_false_for_disjoint_spans() -> None:
    assert not PDFTextStripper.overlap(0.0, 1.0, 100.0, 1.0)


# ---------------------------------------------------------------------------
# multiplyFloat (PDFTextStripper.java:1685)
# ---------------------------------------------------------------------------


def test_multiply_float_truncates_to_three_decimals() -> None:
    """Mirrors ``Math.round(value1 * value2 * 1000) / 1000f``."""
    assert PDFTextStripper.multiply_float(2.5, 4.0) == 10.0
    # 0.3333 * 3 = 0.9999 -> *1000 = 999.9 -> round = 1000 -> /1000 = 1.0
    assert PDFTextStripper.multiply_float(0.3333, 3.0) == 1.0
    assert PDFTextStripper.multiply_float(0.001, 1.0) == 0.001
    # 1.2345 * 1.0 truncates to 1.234 (Python round() banker's-rounding tie).
    assert PDFTextStripper.multiply_float(1.2345, 1.0) == 1.234


# ---------------------------------------------------------------------------
# hasFontOrSizeChanged (PDFTextStripper.java:730)
# ---------------------------------------------------------------------------


def test_has_font_or_size_changed_null_last_returns_false() -> None:
    """Upstream: ``if (last == null) return false;`` — short-circuit."""
    cur = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0)
    assert PDFTextStripper.has_font_or_size_changed(cur, None) is False


def test_has_font_or_size_changed_size_difference() -> None:
    a = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0)
    b = TextPosition(text="x", x=0.0, y=0.0, font_size=13.0)
    assert PDFTextStripper.has_font_or_size_changed(b, a) is True


def test_has_font_or_size_changed_same_font_no_change() -> None:
    a = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0)
    b = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0)
    assert PDFTextStripper.has_font_or_size_changed(b, a) is False


# ---------------------------------------------------------------------------
# removeContainedSpaces (PDFTextStripper.java:771 — PDFBOX-5487)
# ---------------------------------------------------------------------------


def test_remove_contained_spaces_drops_inside_space() -> None:
    big = TextPosition(text="ab", x=0.0, y=0.0, font_size=12.0, width=24.0)
    inside = TextPosition(text=" ", x=4.0, y=0.0, font_size=12.0, width=2.0)
    after = TextPosition(text="c", x=40.0, y=0.0, font_size=12.0, width=10.0)
    text_list = [big, inside, after]
    PDFTextStripper.remove_contained_spaces(text_list)
    assert [p.text for p in text_list] == ["ab", "c"]


def test_remove_contained_spaces_empty_input_no_op() -> None:
    text_list: list[TextPosition] = []
    PDFTextStripper.remove_contained_spaces(text_list)
    assert text_list == []


def test_remove_contained_spaces_single_position_no_op() -> None:
    only = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0, width=8.0)
    text_list = [only]
    PDFTextStripper.remove_contained_spaces(text_list)
    assert text_list == [only]


# ---------------------------------------------------------------------------
# normalizeWord (PDFTextStripper.java:2047)
# ---------------------------------------------------------------------------


def test_normalize_word_basic_latin_unchanged() -> None:
    assert PDFTextStripper().normalize_word("hello") == "hello"


def test_normalize_word_decomposes_fi_ligature() -> None:
    """U+FB01 -> "fi" via NFKC."""
    assert PDFTextStripper().normalize_word("aﬁrm") == "afirm"


def test_normalize_word_decomposes_ffi_ligature() -> None:
    """U+FB03 -> "ffi" via NFKC."""
    assert PDFTextStripper().normalize_word("ﬃ") == "ffi"


# ---------------------------------------------------------------------------
# handleDirection (PDFTextStripper.java:1903)
# ---------------------------------------------------------------------------


def test_handle_direction_pure_ltr_passthrough() -> None:
    assert PDFTextStripper().handle_direction("hello") == "hello"


def test_handle_direction_pure_rtl_reversed() -> None:
    """Hebrew text in logical order is reversed for visual order."""
    # aleph + bet -> bet + aleph
    assert PDFTextStripper().handle_direction("אב") == "בא"


def test_handle_direction_empty_string() -> None:
    assert PDFTextStripper().handle_direction("") == ""


# ---------------------------------------------------------------------------
# parseBidiFile (PDFTextStripper.java:1992)
# ---------------------------------------------------------------------------


def test_parse_bidi_file_skips_comment_lines() -> None:
    sample = b"# header comment\n0028; 0029 # opening paren\n0029; 0028\n"
    out = PDFTextStripper.parse_bidi_file(io.BytesIO(sample))
    assert out["("] == ")"
    assert out[")"] == "("


def test_parse_bidi_file_handles_empty_input() -> None:
    assert PDFTextStripper.parse_bidi_file(io.BytesIO(b"")) == {}


def test_parse_bidi_file_skips_malformed_entries() -> None:
    """Non-hex tokens or wrong field counts must not crash the parser."""
    sample = b"not a hex line\n0028\n0028; 0029; 002A\n0028; 0029\n"
    out = PDFTextStripper.parse_bidi_file(io.BytesIO(sample))
    assert out == {"(": ")"}


# ---------------------------------------------------------------------------
# matchListItemPattern (PDFTextStripper.java:1763)
# ---------------------------------------------------------------------------


def test_match_list_item_pattern_returns_pattern_for_numbered_item() -> None:
    s = PDFTextStripper()
    wrapper = PositionWrapper(TextPosition(text="42.", x=0.0, y=0.0, font_size=12.0))
    matched = s.match_list_item_pattern(wrapper)
    assert matched is not None
    assert matched.pattern == r"\d+\."


def test_match_list_item_pattern_returns_none_for_unrelated_text() -> None:
    s = PDFTextStripper()
    wrapper = PositionWrapper(TextPosition(text="lorem", x=0.0, y=0.0, font_size=12.0))
    assert s.match_list_item_pattern(wrapper) is None


# ---------------------------------------------------------------------------
# normalize / normalizeAdd / createWord (PDFTextStripper.java:1874+)
# ---------------------------------------------------------------------------


def test_normalize_groups_text_positions_into_words() -> None:
    """``normalize`` walks a line of items, splitting at WORD_SEPARATOR
    sentinels and producing one ``WordWithTextPositions`` per word."""
    s = PDFTextStripper()
    a = TextPosition(text="he", x=0.0, y=0.0, font_size=12.0)
    b = TextPosition(text="llo", x=10.0, y=0.0, font_size=12.0)
    c = TextPosition(text="wrld", x=40.0, y=0.0, font_size=12.0)
    line = [
        _LineItem(a),
        _LineItem(b),
        _LineItem.get_word_separator(),
        _LineItem(c),
    ]
    out = s.normalize(line)
    assert [w.get_text() for w in out] == ["hello", "wrld"]
    assert [len(w.get_text_positions()) for w in out] == [2, 1]


def test_create_word_calls_normalize_word() -> None:
    """``createWord`` returns ``WordWithTextPositions(normalizeWord(word), positions)``."""
    s = PDFTextStripper()
    out = s.create_word("ﬃx", [])
    assert isinstance(out, WordWithTextPositions)
    assert out.get_text() == "ffix"


# ---------------------------------------------------------------------------
# writeParagraphSeparator (PDFTextStripper.java:1697)
# ---------------------------------------------------------------------------


def test_write_paragraph_separator_writes_end_then_start() -> None:
    chunks: list[str] = []
    s = PDFTextStripper()
    s.set_paragraph_start("[P]")
    s.set_paragraph_end("[/P]")
    s.write_paragraph_separator(chunks.append)
    assert chunks == ["[/P]", "[P]"]


# ---------------------------------------------------------------------------
# writeLine (PDFTextStripper.java:1853)
# ---------------------------------------------------------------------------


def test_write_line_inserts_separator_between_words() -> None:
    s = PDFTextStripper()
    s.set_word_separator("|")
    chunks: list[str] = []
    p1 = TextPosition(text="a", x=0.0, y=0.0, font_size=12.0)
    p2 = TextPosition(text="b", x=10.0, y=0.0, font_size=12.0)
    p3 = TextPosition(text="c", x=20.0, y=0.0, font_size=12.0)
    line = [
        WordWithTextPositions("a", [p1]),
        WordWithTextPositions("b", [p2]),
        WordWithTextPositions("c", [p3]),
    ]
    s.write_line(line, chunks.append)
    assert "".join(chunks) == "a|b|c"


def test_write_line_single_word_no_separator() -> None:
    s = PDFTextStripper()
    s.set_word_separator(" ")
    chunks: list[str] = []
    p = TextPosition(text="solo", x=0.0, y=0.0, font_size=12.0)
    s.write_line([WordWithTextPositions("solo", [p])], chunks.append)
    assert "".join(chunks) == "solo"
