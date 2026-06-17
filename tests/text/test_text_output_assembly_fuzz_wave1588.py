"""Wave 1588 — text-output assembly fuzz for ``PDFTextStripper``.

Hammers the OUTPUT-ASSEMBLY surface of ``PDFTextStripper`` (not the
position sorting, which earlier waves covered):

  - ``write_string`` / ``write_string_with_positions`` emit the run text.
  - ``write_line`` inserts the word separator *between* words, never at the
    ends (mirrors upstream's private ``writeLine``).
  - line-separator insertion *between* lines on a page (default ``"\n"``).
  - word-separator insertion *between* word-broken runs (default ``" "``).
  - ``set_line_separator`` / ``set_word_separator`` custom values.
  - paragraph-start / paragraph-end markers (both default empty).
  - article-start / article-end separators (both default empty).
  - the suppress-duplicate-overlapping-text behaviour (fake-bold dedup).
  - an empty / glyph-free page.

Each case is checked against the upstream Apache PDFBox 3.0.7
``PDFTextStripper`` output-assembly contract:

  * ``writeLine`` emits the separator only for ``i < n-1`` — no leading or
    trailing word separator.
  * ``writeString(String, List<TextPosition>)`` writes ``text`` regardless
    of the position list (the default overload ignores positions).
  * default ``lineSeparator`` is ``"\n"``, default ``wordSeparator`` is
    ``" "``, default ``paragraphStart`` / ``paragraphEnd`` /
    ``articleStart`` / ``articleEnd`` are all ``""``.
"""
from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper
from pypdfbox.text.pdf_text_stripper import WordWithTextPositions


def _page(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


def _line_words(*texts: str) -> list[WordWithTextPositions]:
    return [WordWithTextPositions(t, []) for t in texts]


def _collect(method, *args) -> str:
    chunks: list[str] = []
    method(*args, chunks.append)
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Defaults (upstream PDFTextStripper constructor values)
# ---------------------------------------------------------------------------


def test_default_line_separator_is_newline() -> None:
    assert PDFTextStripper().get_line_separator() == "\n"


def test_default_word_separator_is_space() -> None:
    assert PDFTextStripper().get_word_separator() == " "


def test_default_paragraph_markers_are_empty() -> None:
    s = PDFTextStripper()
    assert s.get_paragraph_start() == ""
    assert s.get_paragraph_end() == ""


def test_default_article_markers_are_empty() -> None:
    s = PDFTextStripper()
    assert s.get_article_start() == ""
    assert s.get_article_end() == ""


def test_default_page_end_is_newline() -> None:
    assert PDFTextStripper().get_page_end() == "\n"


def test_default_page_start_is_empty() -> None:
    assert PDFTextStripper().get_page_start() == ""


def test_default_suppress_duplicates_enabled() -> None:
    # Upstream defaults suppressDuplicateOverlappingText = true.
    assert PDFTextStripper().is_suppress_duplicate_overlapping_text() is True


def test_default_should_separate_by_beads_enabled() -> None:
    assert PDFTextStripper().get_should_separate_by_beads() is True


# ---------------------------------------------------------------------------
# write_line — separator strictly BETWEEN words (no leading/trailing)
# ---------------------------------------------------------------------------


def test_write_line_inserts_separator_between_words() -> None:
    s = PDFTextStripper()
    out = _collect(s.write_line, _line_words("foo", "bar", "baz"))
    assert out == "foo bar baz"


def test_write_line_single_word_no_separator() -> None:
    s = PDFTextStripper()
    out = _collect(s.write_line, _line_words("solo"))
    assert out == "solo"


def test_write_line_empty_line_emits_nothing() -> None:
    s = PDFTextStripper()
    out = _collect(s.write_line, [])
    assert out == ""


def test_write_line_no_trailing_separator() -> None:
    s = PDFTextStripper()
    out = _collect(s.write_line, _line_words("a", "b"))
    assert not out.endswith(s.get_word_separator() + s.get_word_separator())
    assert out == "a b"
    assert not out.endswith(" ")


def test_write_line_custom_word_separator() -> None:
    s = PDFTextStripper()
    s.set_word_separator("::")
    out = _collect(s.write_line, _line_words("x", "y", "z"))
    assert out == "x::y::z"


def test_write_line_count_separators_is_n_minus_one() -> None:
    s = PDFTextStripper()
    s.set_word_separator("|")
    out = _collect(s.write_line, _line_words("a", "b", "c", "d", "e"))
    assert out.count("|") == 4


def test_write_line_words_with_empty_positions_still_written() -> None:
    # Upstream writeString(text, positions) ignores the position list and
    # always writes the text; words with no backing glyphs must survive.
    s = PDFTextStripper()
    out = _collect(s.write_line, _line_words("alpha", "beta"))
    assert out == "alpha beta"


def test_write_line_empty_word_text_is_noop_but_separators_fire() -> None:
    # An empty word's text contributes nothing (writeString("") is a no-op)
    # but the surrounding separators still fire — matching Java writeLine.
    s = PDFTextStripper()
    out = _collect(s.write_line, _line_words("a", "", "c"))
    assert out == "a  c"


# ---------------------------------------------------------------------------
# write_string / write_string_with_positions
# ---------------------------------------------------------------------------


def test_write_string_emits_text() -> None:
    s = PDFTextStripper()
    out = _collect(lambda sink: s.write_string("hello", [], sink))
    assert out == "hello"


def test_write_string_with_positions_writes_text_for_empty_positions() -> None:
    s = PDFTextStripper()
    out = _collect(lambda sink: s.write_string_with_positions("kept", [], sink))
    assert out == "kept"


def test_write_string_with_positions_empty_text_is_noop() -> None:
    s = PDFTextStripper()
    out = _collect(lambda sink: s.write_string_with_positions("", [], sink))
    assert out == ""


# ---------------------------------------------------------------------------
# Per-hook emitters round-trip the configured marker
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "setter,getter,emitter",
    [
        ("set_word_separator", "get_word_separator", "write_word_separator"),
        ("set_line_separator", "get_line_separator", "write_line_separator"),
        ("set_paragraph_start", "get_paragraph_start", "write_paragraph_start"),
        ("set_paragraph_end", "get_paragraph_end", "write_paragraph_end"),
        ("set_page_start", "get_page_start", "write_page_start"),
        ("set_page_end", "get_page_end", "write_page_end"),
        ("set_article_start", "get_article_start", "write_article_start"),
        ("set_article_end", "get_article_end", "write_article_end"),
    ],
)
def test_emitter_writes_configured_marker(setter, getter, emitter) -> None:
    s = PDFTextStripper()
    getattr(s, setter)("<MARK>")
    assert getattr(s, getter)() == "<MARK>"
    out = _collect(getattr(s, emitter))
    assert out == "<MARK>"


def test_write_paragraph_separator_is_end_then_start() -> None:
    s = PDFTextStripper()
    s.set_paragraph_end("<PE>")
    s.set_paragraph_start("<PS>")
    out = _collect(s.write_paragraph_separator)
    assert out == "<PE><PS>"


# ---------------------------------------------------------------------------
# get_text — full assembly on synthetic content streams
# ---------------------------------------------------------------------------


def test_words_on_one_line_separated_by_word_separator() -> None:
    doc = PDDocument()
    _page(
        doc,
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (foo) Tj "
        b"1 0 0 1 200 700 Tm (bar) Tj "
        b"1 0 0 1 300 700 Tm (baz) Tj ET",
    )
    s = PDFTextStripper()
    out = s.get_text(doc)
    assert "foo bar baz" in out
    # No leading/trailing word separator around the line body.
    assert not out.startswith(" ")


def test_lines_separated_by_line_separator() -> None:
    doc = PDDocument()
    _page(
        doc,
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (top) Tj "
        b"1 0 0 1 100 600 Tm (bot) Tj ET",
    )
    s = PDFTextStripper()
    s.set_page_end("")
    out = s.get_text(doc)
    assert out == "top\nbot"


def test_custom_line_separator_in_get_text() -> None:
    doc = PDDocument()
    _page(
        doc,
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (top) Tj "
        b"1 0 0 1 100 600 Tm (bot) Tj ET",
    )
    s = PDFTextStripper()
    s.set_line_separator("~~")
    s.set_page_end("")
    out = s.get_text(doc)
    assert out == "top~~bot"


def test_custom_word_separator_in_get_text() -> None:
    doc = PDDocument()
    _page(
        doc,
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (foo) Tj "
        b"1 0 0 1 300 700 Tm (bar) Tj ET",
    )
    s = PDFTextStripper()
    s.set_word_separator("_")
    s.set_page_end("")
    out = s.get_text(doc)
    assert out == "foo_bar"


def test_empty_word_separator_collapses() -> None:
    doc = PDDocument()
    _page(
        doc,
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (foo) Tj "
        b"1 0 0 1 300 700 Tm (bar) Tj ET",
    )
    s = PDFTextStripper()
    s.set_word_separator("")
    s.set_page_end("")
    out = s.get_text(doc)
    assert out == "foobar"


def test_empty_line_separator_collapses() -> None:
    doc = PDDocument()
    _page(
        doc,
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (top) Tj "
        b"1 0 0 1 100 600 Tm (bot) Tj ET",
    )
    s = PDFTextStripper()
    s.set_line_separator("")
    s.set_page_end("")
    out = s.get_text(doc)
    assert out == "topbot"


def test_no_trailing_word_separator_on_line() -> None:
    doc = PDDocument()
    _page(
        doc,
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (aa) Tj "
        b"1 0 0 1 300 700 Tm (bb) Tj ET",
    )
    s = PDFTextStripper()
    s.set_word_separator("@")
    s.set_page_end("")
    out = s.get_text(doc)
    # One separator only (between the two words), none after.
    assert out.count("@") == 1
    assert not out.endswith("@")


def test_default_paragraph_markers_emit_nothing_visible() -> None:
    # With both markers empty, a paragraph break collapses to a single
    # line separator (no doubled newline / blank line).
    doc = PDDocument()
    _page(
        doc,
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (alpha) Tj "
        # large y-drop -> paragraph separation fires
        b"1 0 0 1 100 100 Tm (beta) Tj ET",
    )
    s = PDFTextStripper()
    s.set_page_end("")
    out = s.get_text(doc)
    assert out == "alpha\nbeta"
    assert "\n\n" not in out


def test_paragraph_markers_observable_on_drop() -> None:
    doc = PDDocument()
    _page(
        doc,
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (alpha) Tj "
        b"1 0 0 1 100 100 Tm (beta) Tj ET",
    )
    s = PDFTextStripper()
    s.set_paragraph_start("<PS>")
    s.set_paragraph_end("<PE>")
    out = s.get_text(doc)
    assert "<PS>" in out
    assert "<PE>" in out


# ---------------------------------------------------------------------------
# Article markers (default empty)
# ---------------------------------------------------------------------------


def test_article_markers_default_empty_no_wrap() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (body) Tj ET")
    s = PDFTextStripper()
    s.set_page_start("")
    s.set_page_end("")
    out = s.get_text(doc)
    assert out == "body"


def test_article_markers_wrap_when_set() -> None:
    doc = PDDocument()
    _page(doc, b"BT /F0 12 Tf 100 700 Td (body) Tj ET")
    s = PDFTextStripper()
    s.set_article_start("<A>")
    s.set_article_end("</A>")
    s.set_page_start("")
    s.set_page_end("")
    out = s.get_text(doc)
    # A page with no beads is a single article -> wrapped once.
    assert out == "<A>body</A>"


def test_empty_page_with_article_markers_emits_wrap() -> None:
    # A glyph-free page still emits the article wrap so the per-page
    # markers survive (matches upstream startArticle/endArticle).
    doc = PDDocument()
    _page(doc, b"")
    s = PDFTextStripper()
    s.set_article_start("<A>")
    s.set_article_end("</A>")
    s.set_page_start("")
    s.set_page_end("")
    out = s.get_text(doc)
    assert out == "<A></A>"


# ---------------------------------------------------------------------------
# Empty / glyph-free page
# ---------------------------------------------------------------------------


def test_empty_page_default_markers_is_page_end_only() -> None:
    doc = PDDocument()
    _page(doc, b"")
    s = PDFTextStripper()
    out = s.get_text(doc)
    # Default page_end is "\n"; no body text.
    assert out == "\n"


def test_empty_page_all_markers_empty_is_empty() -> None:
    doc = PDDocument()
    _page(doc, b"")
    s = PDFTextStripper()
    s.set_page_start("")
    s.set_page_end("")
    out = s.get_text(doc)
    assert out == ""


def test_no_pages_returns_empty() -> None:
    doc = PDDocument()
    s = PDFTextStripper()
    assert s.get_text(doc) == ""


# ---------------------------------------------------------------------------
# Suppress-duplicate-overlapping-text (fake-bold dedup)
# ---------------------------------------------------------------------------


def test_fake_bold_duplicate_suppressed_by_default() -> None:
    # Same glyph painted twice at (essentially) the same origin — the
    # second is a fake-bold duplicate and must be dropped by default.
    doc = PDDocument()
    _page(
        doc,
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (X) Tj "
        b"1 0 0 1 100.2 700 Tm (X) Tj ET",
    )
    s = PDFTextStripper()
    s.set_page_end("")
    out = s.get_text(doc)
    assert out == "X"


def test_duplicate_kept_when_suppression_disabled() -> None:
    doc = PDDocument()
    _page(
        doc,
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (X) Tj "
        b"1 0 0 1 100.2 700 Tm (X) Tj ET",
    )
    s = PDFTextStripper()
    s.set_suppress_duplicate_overlapping_text(False)
    s.set_page_end("")
    out = s.get_text(doc)
    # Both glyphs survive (concatenated; near-coincident -> no word break).
    assert out == "XX"


def test_distinct_adjacent_glyphs_not_treated_as_duplicates() -> None:
    # Genuine adjacent glyphs advance by ~their own width; they must not
    # be dedup'd even with suppression on.
    doc = PDDocument()
    _page(
        doc,
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (A) Tj "
        b"1 0 0 1 110 700 Tm (B) Tj ET",
    )
    s = PDFTextStripper()
    s.set_page_end("")
    out = s.get_text(doc)
    assert "A" in out and "B" in out


# ---------------------------------------------------------------------------
# Setters are independent (no cross-talk)
# ---------------------------------------------------------------------------


def test_separators_independent() -> None:
    s = PDFTextStripper()
    s.set_word_separator("W")
    s.set_line_separator("L")
    s.set_paragraph_start("PS")
    s.set_paragraph_end("PE")
    s.set_article_start("AS")
    s.set_article_end("AE")
    assert s.get_word_separator() == "W"
    assert s.get_line_separator() == "L"
    assert s.get_paragraph_start() == "PS"
    assert s.get_paragraph_end() == "PE"
    assert s.get_article_start() == "AS"
    assert s.get_article_end() == "AE"
    # Re-setting one leaves the others untouched.
    s.set_word_separator("W2")
    assert s.get_line_separator() == "L"
    assert s.get_article_start() == "AS"


# ---------------------------------------------------------------------------
# write_text streams identically to get_text
# ---------------------------------------------------------------------------


def test_write_text_matches_get_text_with_custom_separators() -> None:
    doc = PDDocument()
    _page(
        doc,
        b"BT /F0 12 Tf "
        b"1 0 0 1 100 700 Tm (foo) Tj "
        b"1 0 0 1 100 600 Tm (bar) Tj ET",
    )
    s = PDFTextStripper()
    s.set_word_separator(" | ")
    s.set_line_separator(" // ")
    buf = io.StringIO()
    s.write_text(doc, buf)
    assert buf.getvalue() == s.get_text(doc)
