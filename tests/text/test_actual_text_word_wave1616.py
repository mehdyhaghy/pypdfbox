"""PDFBOX-6281: text taken from /ActualText is used as is.

Upstream flags the span's first glyph with ``setFromActualText(true)``;
``normalizeAdd`` then appends its unicode without visual reordering and
``createWord`` skips ``normalizeWord`` (presentation-form decomposition and
bidi reordering) for a word that starts with it. PDFBOX-6310 guards the
``wordPositions.get(0)`` read for a word separator that starts a line.
"""

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.documentinterchange.markedcontent import PDPropertyList
from pypdfbox.pdmodel.font import PDFontFactory, Standard14Fonts
from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.text import PDFTextStripper, TextPosition
from pypdfbox.text.pdf_text_stripper import _LineItem

_SPAN = COSName.get_pdf_name("Span")
# Hebrew "shalom" followed by digits: the bidi algorithm would reorder it.
_RTL = "שלום 123"


def _helvetica():
    return PDFontFactory.create_default_font(Standard14Fonts.FontName.HELVETICA.value)


def _actual_text(text: str) -> PDPropertyList:
    d = COSDictionary()
    d.set_string(COSName.get_pdf_name("ActualText"), text)
    return PDPropertyList.create(d)


def _stripper(cls: type[PDFTextStripper] = PDFTextStripper) -> PDFTextStripper:
    s = cls()
    s.set_line_separator("\n")
    s.set_page_end("\n")
    return s


def _doc_with_spans(*runs: tuple[str | None, str]) -> PDDocument:
    """One line; each run is ``(actual_text_or_None, shown_text)``."""
    doc = PDDocument()
    page = PDPage()
    cs = PDPageContentStream(doc, page)
    try:
        cs.begin_text()
        cs.set_font(_helvetica(), 12)
        cs.new_line_at_offset(50, 700)
        for actual, shown in runs:
            if actual is None:
                cs.show_text(shown)
            else:
                cs.begin_marked_content_with_dict(_SPAN, _actual_text(actual))
                cs.show_text(shown)
                cs.end_marked_content()
        cs.end_text()
    finally:
        cs.close()
    doc.add_page(page)
    return doc


class _SlowStripper(PDFTextStripper):
    """Overrides the hooks so the stock fast paths are bypassed."""

    def normalize_add(self, normalized, line_builder, word_positions, item):
        super().normalize_add(normalized, line_builder, word_positions, item)

    def create_word(self, word, word_positions):
        return super().create_word(word, word_positions)


# ---------- TextPosition accessors ----------


def test_text_position_from_actual_text_default_and_setter() -> None:
    tp = TextPosition(text="a", x=0.0, y=0.0, font_size=12.0)
    assert tp.is_from_actual_text() is False
    tp.set_from_actual_text(True)
    assert tp.is_from_actual_text() is True
    assert tp.from_actual_text is True
    tp.set_from_actual_text(False)
    assert not tp.is_from_actual_text()


def test_only_first_glyph_of_span_is_from_actual_text() -> None:
    captured: list[TextPosition] = []

    class _Capture(PDFTextStripper):
        def write_string_with_positions(self, text, positions, sink=None):
            captured.extend(positions)
            return super().write_string_with_positions(text, positions, sink)

    doc = _doc_with_spans(("XYZ", "abc"), (None, "def"))
    try:
        _stripper(_Capture).get_text(doc)
    finally:
        doc.close()
    flags = [(p.get_unicode(), p.is_from_actual_text(), p.in_actual_text_span) for p in captured]
    assert flags[0] == ("XYZ", True, True)
    assert all(not f[1] for f in flags[1:])
    # The rest of the span is empty and still inside the span.
    assert flags[1] == ("", False, True)
    assert flags[2] == ("", False, True)
    assert all(not f[2] for f in flags[3:])


# ---------- extraction ----------


@pytest.mark.parametrize("cls", [PDFTextStripper, _SlowStripper], ids=["fast", "hooks"])
def test_rtl_actual_text_is_not_reordered(cls) -> None:
    doc = _doc_with_spans((_RTL, "abcdefgh"))
    try:
        assert _stripper(cls).get_text(doc) == _RTL + "\n"
    finally:
        doc.close()


@pytest.mark.parametrize("cls", [PDFTextStripper, _SlowStripper], ids=["fast", "hooks"])
def test_presentation_form_actual_text_is_not_decomposed(cls) -> None:
    # U+FB01 (LATIN SMALL LIGATURE FI) would be NFKC-decomposed by normalizeWord.
    doc = _doc_with_spans(("ﬁ", "fi"))
    try:
        assert _stripper(cls).get_text(doc) == "ﬁ\n"
    finally:
        doc.close()


@pytest.mark.parametrize("cls", [PDFTextStripper, _SlowStripper], ids=["fast", "hooks"])
def test_word_after_actual_text_word_is_still_normalized(cls) -> None:
    # The plain word that follows a separator starts with a non-ActualText
    # glyph, so normalizeWord still runs on it (here a no-op for ASCII).
    doc = _doc_with_spans(("ﬁ", "fi"), (None, " plain"))
    try:
        assert _stripper(cls).get_text(doc) == "ﬁ plain\n"
    finally:
        doc.close()


def test_articles_on_same_line_with_actual_text() -> None:
    """PDFBOX-6310 with /ActualText: the second article starts with a word
    separator (empty word positions) and its first glyph carries
    /ActualText."""
    doc = PDDocument()
    try:
        page = PDPage()
        y = page.get_media_box().get_height() - 100
        cs = PDPageContentStream(doc, page)
        try:
            font = _helvetica()
            cs.begin_text()
            cs.set_font(font, 12)
            cs.new_line_at_offset(50, y)
            cs.show_text("LEFT")
            cs.end_text()
            cs.begin_text()
            cs.set_font(font, 12)
            cs.new_line_at_offset(350, y)
            cs.begin_marked_content_with_dict(_SPAN, _actual_text(_RTL))
            cs.show_text("RIGHT")
            cs.end_marked_content()
            cs.end_text()
        finally:
            cs.close()
        left = PDThreadBead()
        left.set_rectangle(PDRectangle.from_xywh(40, y - 50, 200, 100))
        right = PDThreadBead()
        right.set_rectangle(PDRectangle.from_xywh(340, y - 50, 200, 100))
        page.set_thread_beads([left, right])
        doc.add_page(page)
        for cls in (PDFTextStripper, _SlowStripper):
            assert _stripper(cls).get_text(doc) == "LEFT " + _RTL + "\n"
    finally:
        doc.close()


# ---------- create_word / normalize_add ----------


def test_create_word_empty_positions() -> None:
    word = PDFTextStripper().create_word("", [])
    assert word.get_text() == ""
    assert word.get_text_positions() == []


def test_create_word_skips_normalize_for_actual_text() -> None:
    tp = TextPosition(text=_RTL, x=0.0, y=0.0, font_size=12.0)
    stripper = PDFTextStripper()
    assert stripper.create_word(_RTL, [tp]).get_text() != _RTL
    tp.set_from_actual_text(True)
    assert stripper.create_word(_RTL, [tp]).get_text() == _RTL
    # Only the first position decides.
    plain = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0)
    assert stripper.create_word(_RTL, [plain, tp]).get_text() != _RTL


def test_normalize_add_uses_unicode_for_actual_text() -> None:
    tp = TextPosition(text="שלום", x=0.0, y=0.0, font_size=12.0)
    stripper = PDFTextStripper()
    builder: list[str] = []
    stripper.normalize_add([], builder, [], _LineItem(tp))
    assert builder == ["םולש"]
    tp.set_from_actual_text(True)
    builder = []
    positions: list[TextPosition] = []
    stripper.normalize_add([], builder, positions, _LineItem(tp))
    assert builder == ["שלום"]
    assert positions == [tp]


def test_flip_axes_path_keeps_actual_text() -> None:
    doc = _doc_with_spans((_RTL, "abcdefgh"))
    try:
        stripper = _stripper()
        stripper.set_should_flip_axes(True)
        assert _RTL in stripper.get_text(doc)
    finally:
        doc.close()
