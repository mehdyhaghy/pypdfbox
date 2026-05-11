"""Hand-written tests for new ports under ``pypdfbox.text``."""

from __future__ import annotations

from pypdfbox.text.legacy_pdf_stream_engine import LegacyPDFStreamEngine
from pypdfbox.text.line_item import LineItem


def test_line_item_word_separator_singleton() -> None:
    sep = LineItem.WORD_SEPARATOR
    assert sep.is_word_separator()
    assert sep.get_text_position() is None
    assert LineItem.get_word_separator() is sep


def test_line_item_with_position() -> None:
    sentinel = object()
    item = LineItem(sentinel)  # type: ignore[arg-type]
    assert not item.is_word_separator()
    assert item.get_text_position() is sentinel


def test_legacy_pdf_stream_engine_constructs() -> None:
    engine = LegacyPDFStreamEngine()
    # Subclass-overridable hooks default to no-ops returning None.
    assert engine.show_glyph(None, None, 0, None) is None
    assert engine.process_text_position(None) is None
