"""Hand-written tests for the promoted public API on :class:`Searcher`.

Covers ``search``, ``scroll_to_word``, ``update_navigation_buttons``,
``update_high_lighter`` and ``change_highlighter`` (both the painter-swap
form and the project-extension strategy-swap form). These tests use a
stub text widget for the cases that don't need a live Tk root, and the
session-scoped ``tk_root`` fixture from ``conftest.py`` for the rest
(which honors ``PYPDFBOX_SKIP_TK=1``).
"""

from __future__ import annotations

import os
import tkinter as tk

import pytest

from pypdfbox.debugger.ui.textsearcher.search_engine import (
    Highlight,
    SearchEngine,
)
from pypdfbox.debugger.ui.textsearcher.searcher import (
    PAINTER,
    SELECTION_PAINTER,
    Searcher,
)


class _StubTextWidget:
    """Minimal ``tk.Text`` stand-in for headless tests."""

    def __init__(self, body: str) -> None:
        self._body = body
        self.tag_add_calls: list[tuple[str, str, str]] = []
        self.tag_remove_calls: list[tuple[str, str, str]] = []
        self.see_calls: list[str] = []

    def get(self, _start: str, _end: str) -> str:
        return self._body

    def tag_add(self, tag: str, start: str, end: str) -> None:
        self.tag_add_calls.append((tag, start, end))

    def tag_remove(self, tag: str, start: str, end: str) -> None:
        self.tag_remove_calls.append((tag, start, end))

    def see(self, index: str) -> None:
        self.see_calls.append(index)


# ---------------------------------------------------------------------------
# Headless tests (do not require a Tk display)
# ---------------------------------------------------------------------------


def test_search_returns_three_hits_in_order() -> None:
    widget = _StubTextWidget("foo bar foo baz foo")
    searcher = Searcher(widget)
    matches = searcher.search("foo")
    assert len(matches) == 3
    starts = [m.start_offset for m in matches]
    assert starts == sorted(starts)
    assert starts == [0, 8, 16]


def test_update_navigation_buttons_disables_prev_at_zero() -> None:
    widget = _StubTextWidget("x x x")
    searcher = Searcher(widget)
    searcher.search("x")  # 3 hits, current = 0
    searcher.update_navigation_buttons()
    assert searcher._previous_enabled is False  # type: ignore[attr-defined]
    assert searcher._next_enabled is True  # type: ignore[attr-defined]


def test_update_navigation_buttons_disables_next_at_last() -> None:
    widget = _StubTextWidget("x x x")
    searcher = Searcher(widget)
    searcher.search("x")  # 3 hits
    searcher._current_match = 2  # type: ignore[attr-defined]
    searcher.update_navigation_buttons()
    assert searcher._next_enabled is False  # type: ignore[attr-defined]
    assert searcher._previous_enabled is True  # type: ignore[attr-defined]


def test_scroll_to_word_calls_see_with_match_start() -> None:
    widget = _StubTextWidget("foo bar foo")
    searcher = Searcher(widget)
    matches = searcher.search("foo")
    widget.see_calls.clear()
    searcher.scroll_to_word(matches[1].start_offset)
    assert widget.see_calls == [f"1.0 + {matches[1].start_offset} chars"]


def test_change_highlighter_swaps_strategy_to_case_sensitive() -> None:
    widget = _StubTextWidget("Foo foo FOO")
    searcher = Searcher(widget)
    # Default engine is case-sensitive when called directly via .search().
    # Build an explicitly case-insensitive engine, swap it in, then verify
    # subsequent searches use the new strategy.
    insensitive = SearchEngine(
        get_text=lambda: widget.get("1.0", "end-1c"),
        add_highlight=lambda s, e, p: widget.tag_add(
            p, f"1.0 + {s} chars", f"1.0 + {e} chars"
        ),
        remove_all_highlights=lambda: None,
        painter=PAINTER,
    )
    # Wrap to flip case-sensitivity off no matter what arg the searcher passes.
    class _AlwaysInsensitive:
        def search(self, word: str, _ignored: bool) -> list[Highlight]:
            return insensitive.search(word, False)

        def search_regex(self, word: str, _ignored: bool) -> list[Highlight]:
            return insensitive.search_regex(word, False)

    case_sensitive_hits = searcher.search("foo")
    assert len(case_sensitive_hits) == 1  # only the lowercase "foo"

    searcher.change_highlighter(_AlwaysInsensitive())
    case_insensitive_hits = searcher.search("foo")
    assert len(case_insensitive_hits) == 3  # Foo, foo, FOO


def test_change_highlighter_painter_form_retags_one_match() -> None:
    widget = _StubTextWidget("aaa aaa")
    searcher = Searcher(widget)
    searcher.search("aaa")
    widget.tag_add_calls.clear()
    widget.tag_remove_calls.clear()
    searcher.change_highlighter(0, SELECTION_PAINTER)
    # The one match at index 0 should now carry SELECTION_PAINTER.
    assert searcher._highlights[0].painter == SELECTION_PAINTER  # type: ignore[attr-defined]
    # Both old painters cleared from the span, new one added.
    assert any(c[0] == SELECTION_PAINTER for c in widget.tag_add_calls)
    assert any(c[0] == PAINTER for c in widget.tag_remove_calls)
    assert any(c[0] == SELECTION_PAINTER for c in widget.tag_remove_calls)


def test_update_high_lighter_reapplies_all_tags() -> None:
    widget = _StubTextWidget("zz zz zz")
    searcher = Searcher(widget)
    searcher.search("zz")  # 3 highlights
    widget.tag_add_calls.clear()
    # Call with default args → re-apply PAINTER to every highlight.
    searcher.update_high_lighter()
    painter_adds = [c for c in widget.tag_add_calls if c[0] == PAINTER]
    assert len(painter_adds) == 3


def test_private_aliases_preserve_back_compat() -> None:
    widget = _StubTextWidget("ab ab")
    searcher = Searcher(widget)
    # The private-underscore names must still resolve and behave identically.
    assert Searcher._search is Searcher.search
    assert Searcher._scroll_to_word is Searcher.scroll_to_word
    assert Searcher._update_highlighter is Searcher.update_high_lighter
    assert Searcher._update_navigation_buttons is Searcher.update_navigation_buttons
    assert Searcher._change_highlighter is Searcher.change_highlighter
    # And they actually work.
    matches = searcher._search("ab")  # type: ignore[attr-defined]
    assert len(matches) == 2


# ---------------------------------------------------------------------------
# Live-Tk test (uses the session-scoped fixture that honors PYPDFBOX_SKIP_TK)
# ---------------------------------------------------------------------------


def test_scroll_to_word_against_live_text_widget(tk_root: tk.Tk) -> None:
    if os.environ.get("PYPDFBOX_SKIP_TK", "") == "1":  # pragma: no cover
        pytest.skip("PYPDFBOX_SKIP_TK=1")
    widget = tk.Text(tk_root)
    widget.insert("1.0", "alpha beta gamma")
    widget.tag_configure(PAINTER)
    widget.tag_configure(SELECTION_PAINTER)
    searcher = Searcher(widget)
    matches = searcher.search("beta")
    assert len(matches) == 1
    # Should not raise; ``Text.see`` accepts the "1.0 + N chars" form.
    searcher.scroll_to_word(matches[0].start_offset)
