"""Tests for
:class:`pypdfbox.pdmodel.abstract_glyph_layout_processor.AbstractGlyphLayoutProcessor`.

Ported alongside upstream's PDFBOX-4951 glyph-layout core. Upstream's own
coverage for the Bidi split / reorder path and for ``getStringWidth`` lives in
the optional ``pdfbox-layout-awt`` module (commit "add width test"), which
pypdfbox does not port because it depends on a text-shaping backend. The
``getStringWidth``-sums-per-run and reorder assertions below are the
backend-free equivalents.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel import (
    AbstractGlyphLayoutProcessor,
    GlyphLayoutProcessorInterface,
)

_HEBREW = "אבג"  # alef bet gimel
_ARABIC = "اب"


class _RecordingProcessor(AbstractGlyphLayoutProcessor):
    """Backend-free stub: records the unidirectional runs it is handed and
    charges one width unit per character."""

    def __init__(self) -> None:
        self.width_runs: list[tuple[str, int]] = []
        self.shown_runs: list[tuple[str, int]] = []

    def supports_font(self, font: object) -> bool:
        return True

    def get_string_width_uni(
        self, font: object, font_size: float, text: str, bidi_level: int
    ) -> float:
        self.width_runs.append((text, bidi_level))
        return len(text) * font_size

    def show_text_uni(
        self,
        content_stream: object,
        font: object,
        font_size: float,
        text: str,
        bidi_level: int,
    ) -> None:
        self.shown_runs.append((text, bidi_level))


def _split(text: str) -> list[tuple[str, int]]:
    processor = _RecordingProcessor()
    return [
        (part.get_text(), part.get_bidi_level())
        for part in processor.do_bidi_splitting_and_reordering(text)
    ]


# ------------------------------------------------------------------
# type / interface shape
# ------------------------------------------------------------------


def test_is_a_glyph_layout_processor_interface() -> None:
    assert issubclass(AbstractGlyphLayoutProcessor, GlyphLayoutProcessorInterface)
    assert isinstance(_RecordingProcessor(), GlyphLayoutProcessorInterface)


def test_cannot_instantiate_without_the_abstract_hooks() -> None:
    with pytest.raises(TypeError):
        AbstractGlyphLayoutProcessor()  # type: ignore[abstract]


def test_text_and_bidi_level_accessors() -> None:
    entry = AbstractGlyphLayoutProcessor.TextAndBidiLevel("abc", 2)
    assert entry.get_text() == "abc"
    assert entry.get_bidi_level() == 2


# ------------------------------------------------------------------
# do_bidi_splitting_and_reordering
# ------------------------------------------------------------------


def test_plain_ltr_text_is_one_run_at_level_zero() -> None:
    assert _split("hello") == [("hello", 0)]


def test_empty_text_is_one_empty_run() -> None:
    assert _split("") == [("", 0)]


def test_digits_do_not_require_bidi() -> None:
    assert _split("abc 123") == [("abc 123", 0)]


def test_uniform_rtl_text_is_one_run_at_the_base_level() -> None:
    assert _split(_HEBREW) == [(_HEBREW, 1)]


def test_mixed_text_is_split_and_reordered() -> None:
    parts = _split(f"abc {_HEBREW} def")
    assert parts == [("abc ", 0), (_HEBREW, 1), (" def", 0)]


def test_rtl_base_direction_reorders_runs_visually() -> None:
    # Base direction is RTL (the first strong character is Arabic), so the
    # runs come back in visual (right-to-left) order.
    parts = _split(f"{_ARABIC} 12 {_ARABIC}")
    assert [text for text, _ in parts] == [f" {_ARABIC}", "12", f"{_ARABIC} "]
    assert [level for _, level in parts] == [1, 2, 1]


def test_result_is_immutable() -> None:
    processor = _RecordingProcessor()
    result = processor.do_bidi_splitting_and_reordering("hi")
    assert isinstance(result, tuple)


def test_none_text_is_rejected() -> None:
    processor = _RecordingProcessor()
    with pytest.raises(TypeError):
        processor.do_bidi_splitting_and_reordering(None)  # type: ignore[arg-type]


# ------------------------------------------------------------------
# get_string_width / show_text — per-run fan-out
# ------------------------------------------------------------------


def test_get_string_width_sums_the_unidirectional_runs() -> None:
    processor = _RecordingProcessor()
    text = f"abc {_HEBREW} def"
    width = processor.get_string_width(object(), 10.0, text)
    # Every character is charged once, whatever the run split looks like.
    assert width == pytest.approx(len(text) * 10.0)
    assert processor.width_runs == [("abc ", 0), (_HEBREW, 1), (" def", 0)]


def test_get_string_width_of_plain_text_is_a_single_run() -> None:
    processor = _RecordingProcessor()
    assert processor.get_string_width(object(), 12.0, "abcd") == pytest.approx(48.0)
    assert processor.width_runs == [("abcd", 0)]


def test_show_text_fans_out_over_the_reordered_runs() -> None:
    processor = _RecordingProcessor()
    processor.show_text(object(), object(), 9.0, f"abc {_HEBREW} def")
    assert processor.shown_runs == [("abc ", 0), (_HEBREW, 1), (" def", 0)]


def test_show_text_and_get_string_width_agree_on_the_split() -> None:
    processor = _RecordingProcessor()
    text = f"{_ARABIC} 12 {_ARABIC}"
    processor.get_string_width(object(), 1.0, text)
    processor.show_text(object(), object(), 1.0, text)
    assert processor.width_runs == processor.shown_runs
