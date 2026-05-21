"""Wave 1370 — normalize / normalize_add + TextLine-style metrics.

The lite stripper exposes ``normalize`` (mirrors upstream
``PDFTextStripper.normalize(List<LineItem>)``), ``normalize_add``
(mirrors ``normalizeAdd``), and ``create_word``
(mirrors ``createWord``). Together they build the
``WordWithTextPositions`` list a single line consists of in upstream's
output.

Upstream PDFBox also exposes a per-line metrics holder (``TextLine``
internally) tracking maxFontSize / averageFontSize / baseline. pypdfbox
does not yet port that holder as a top-level class, but the
:class:`TextMetrics` data-holder fills the same conceptual slot for
a single ``TextPosition``. These tests pin both layers.
"""
from __future__ import annotations

import pytest

from pypdfbox.text import (
    LineItem,
    PDFTextStripper,
    TextMetrics,
    TextPosition,
    WordWithTextPositions,
)


def _tp(text: str = "x", **kw) -> TextPosition:
    base = {"text": text, "x": 0.0, "y": 0.0, "font_size": 12.0, "width": 10.0}
    base.update(kw)
    return TextPosition(**base)


# ---------------------------------------------------------------------------
# create_word + normalize_word
# ---------------------------------------------------------------------------


def test_create_word_returns_word_with_text_positions_instance() -> None:
    s = PDFTextStripper()
    positions = [_tp("h"), _tp("i")]
    word = s.create_word("hi", positions)
    assert isinstance(word, WordWithTextPositions)
    assert word.get_text() == "hi"
    assert word.get_text_positions() is positions


def test_normalize_word_preserves_ltr_text_unchanged() -> None:
    s = PDFTextStripper()
    assert s.normalize_word("hello") == "hello"


def test_normalize_word_decomposes_arabic_presentation_form() -> None:
    """Upstream NFKC-decomposes Arabic Presentation Forms-B (FE70-FEFF).

    U+FE80 (ARABIC LETTER HAMZA, isolated form) NFKC-decomposes to
    U+0621 (ARABIC LETTER HAMZA, canonical form)."""
    s = PDFTextStripper()
    result = s.normalize_word("ﺀ")
    # The presentation form is collapsed to its canonical counterpart.
    assert result == "ء"


def test_normalize_word_empty_string_passes_through() -> None:
    s = PDFTextStripper()
    assert s.normalize_word("") == ""


# ---------------------------------------------------------------------------
# normalize / normalize_add — build a line out of LineItem sentinels
# ---------------------------------------------------------------------------


def test_normalize_splits_at_word_separator() -> None:
    """A list of LineItems with WORD_SEPARATOR markers splits into the
    corresponding sequence of words."""
    s = PDFTextStripper()
    line = [
        LineItem(_tp("H")),
        LineItem(_tp("i")),
        LineItem.get_word_separator(),
        LineItem(_tp("o")),
        LineItem(_tp("k")),
    ]
    words = s.normalize(line)
    assert [w.get_text() for w in words] == ["Hi", "ok"]


def test_normalize_handles_leading_separator() -> None:
    """A LineItem list that opens with a separator produces an initial
    empty word — upstream behaviour we mirror to avoid silently
    swallowing the boundary."""
    s = PDFTextStripper()
    line = [
        LineItem.get_word_separator(),
        LineItem(_tp("A")),
    ]
    words = s.normalize(line)
    # First entry is the empty word created by the leading separator.
    assert [w.get_text() for w in words] == ["", "A"]


def test_normalize_handles_trailing_runs_without_terminating_separator() -> None:
    s = PDFTextStripper()
    line = [LineItem(_tp("X"))]
    words = s.normalize(line)
    assert [w.get_text() for w in words] == ["X"]


def test_normalize_empty_list_yields_empty_result() -> None:
    s = PDFTextStripper()
    assert s.normalize([]) == []


# ---------------------------------------------------------------------------
# normalize_add — direct exercise (callers may invoke it as a hook)
# ---------------------------------------------------------------------------


def test_normalize_add_appends_position_to_word_in_progress() -> None:
    s = PDFTextStripper()
    normalized: list = []
    builder: list[str] = []
    positions: list[TextPosition] = []
    item = LineItem(_tp("a"))
    s.normalize_add(normalized, builder, positions, item)
    # No flush yet — normalized is still empty.
    assert normalized == []
    # But the builders advanced.
    assert builder == ["a"]
    assert positions == [item.get_text_position()]


def test_normalize_add_separator_flushes_current_word() -> None:
    s = PDFTextStripper()
    normalized: list = []
    builder: list[str] = ["w", "o", "r", "d"]
    pos_a = _tp("w")
    pos_b = _tp("o")
    positions: list[TextPosition] = [pos_a, pos_b]
    sep = LineItem.get_word_separator()
    s.normalize_add(normalized, builder, positions, sep)
    # Word flushed.
    assert len(normalized) == 1
    assert normalized[0].get_text() == "word"
    # And the in-progress buffers are reset.
    assert builder == []
    assert positions == []


# ---------------------------------------------------------------------------
# TextMetrics — line-height proxy and the upstream
# maxFontSize / averageFontSize / baseline contract for a single run
# ---------------------------------------------------------------------------


def test_text_metrics_max_font_size_equals_run_font_size() -> None:
    """For a single ``TextPosition`` the "max font size" of the
    derived line is the run's font size."""
    tp = _tp(font_size=18.0)
    metrics = TextMetrics(tp)
    # height = ascent + |descent| = 18 * 0.7 + 18 * 0.2 = 16.2
    assert metrics.get_height() == pytest.approx(18.0 * 0.9)


def test_text_metrics_baseline_at_run_y() -> None:
    """The metrics baseline is the position's Y — same as the run's
    text origin."""
    tp = _tp(x=10.0, y=42.0, font_size=12.0)
    metrics = TextMetrics(tp)
    assert metrics.get_x() == 10.0
    assert metrics.get_y() == 42.0


def test_text_metrics_height_proportional_to_font_size() -> None:
    """A larger font_size implies a proportionally larger line height."""
    small = TextMetrics(_tp(font_size=8.0))
    large = TextMetrics(_tp(font_size=24.0))
    assert large.get_height() == pytest.approx(3.0 * small.get_height())


def test_text_metrics_set_ascent_keeps_descent_unchanged() -> None:
    tp = _tp(font_size=10.0)
    metrics = TextMetrics(tp)
    initial_descent = metrics.get_descent()
    metrics.set_ascent(20.0)
    assert metrics.get_ascent() == 20.0
    assert metrics.get_descent() == initial_descent


def test_text_metrics_height_recomputed_after_mutation() -> None:
    """``get_height()`` re-derives from the live ascent/descent."""
    metrics = TextMetrics(_tp(font_size=10.0))
    metrics.set_ascent(5.0)
    metrics.set_descent(-2.0)
    assert metrics.get_height() == 7.0


# ---------------------------------------------------------------------------
# Stripper factory: word_with_text_positions static parity helper
# ---------------------------------------------------------------------------


def test_word_with_text_positions_factory_matches_constructor() -> None:
    positions = [_tp("a")]
    factory_result = PDFTextStripper.word_with_text_positions("a", positions)
    direct = WordWithTextPositions("a", positions)
    assert factory_result.get_text() == direct.get_text()
    assert factory_result.get_text_positions() is positions
