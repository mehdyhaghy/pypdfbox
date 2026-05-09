from __future__ import annotations

from collections.abc import Callable

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper, TextPosition


def _make_page_with_stream(doc: PDDocument, content: bytes | None) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    if content is not None:
        stream = COSStream()
        stream.set_data(content)
        page.set_contents(stream)
    doc.add_page(page)
    return page


def test_wave540_should_skip_glyph_filters_before_processing_or_output() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (keep) Tj 40 0 Td (drop) Tj ET",
    )
    processed: list[str] = []

    class FilteringStripper(PDFTextStripper):
        def should_skip_glyph(self, text: TextPosition) -> bool:
            return text.text == "drop"

        def process_text_position(self, text: TextPosition) -> None:
            processed.append(text.text)

    try:
        assert FilteringStripper().get_text(doc) == "keep\n"
        assert processed == ["keep"]
    finally:
        doc.close()


def test_wave540_write_string_with_empty_payload_is_not_dispatched() -> None:
    calls: list[str] = []

    class RecordingStripper(PDFTextStripper):
        def write_string(
            self,
            text: str,
            text_positions: list[TextPosition],
            sink: Callable[[str], None],
        ) -> None:
            calls.append(text)
            sink(text)

    stripper = RecordingStripper()
    sinked: list[str] = []
    pos = TextPosition(text="x", x=0.0, y=0.0, font_size=10.0)

    stripper.write_string_with_positions("", [pos], sinked.append)
    stripper.write_string_with_positions("x", [], sinked.append)

    assert calls == []
    assert sinked == []


def test_wave540_ignore_space_glyphs_all_spaces_advances_without_positions() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 10 Tf 100 700 Td (   ) Tj ET")

    stripper = PDFTextStripper()
    stripper.set_ignore_content_stream_space_glyphs(True)

    try:
        assert stripper.get_text(doc) == "\n"
        assert stripper.get_characters_by_article() == [[]]
    finally:
        doc.close()


def test_wave540_drop_overlapping_duplicates_uses_recent_window_only() -> None:
    original = TextPosition(text="same", x=10.0, y=10.0, font_size=8.0)
    duplicate = TextPosition(text="same", x=11.0, y=11.0, font_size=8.0)
    later_same_text = TextPosition(text="same", x=10.5, y=10.5, font_size=8.0)
    positions = [
        original,
        duplicate,
        TextPosition(text="a", x=100.0, y=10.0, font_size=8.0),
        TextPosition(text="b", x=110.0, y=10.0, font_size=8.0),
        TextPosition(text="c", x=120.0, y=10.0, font_size=8.0),
        TextPosition(text="d", x=130.0, y=10.0, font_size=8.0),
        later_same_text,
    ]

    assert PDFTextStripper._drop_overlapping_duplicates(positions) == [
        original,
        positions[2],
        positions[3],
        positions[4],
        positions[5],
        later_same_text,
    ]


def test_wave540_word_break_uses_font_size_fallback_when_previous_width_is_zero() -> None:
    stripper = PDFTextStripper()
    prev = TextPosition(text="wide", x=10.0, y=20.0, font_size=8.0, width=0.0)
    close = TextPosition(text="close", x=37.9, y=20.0, font_size=8.0)
    far = TextPosition(text="far", x=50.1, y=20.0, font_size=8.0)

    assert stripper._is_word_break(close, prev) is False  # noqa: SLF001
    assert stripper._is_word_break(far, prev) is True  # noqa: SLF001
