"""Wave 1365 parity tests for :class:`Searcher` find/jump semantics.

These tests focus on upstream-source behaviors (``Searcher.java``) that the
existing wave-1345/1349/1354 suites do not exercise directly:

* ``_previous_action`` on a zero-match panel must be a no-op (upstream's
  ``totalMatch != 0 && currentMatch != 0`` guard).
* ``_next_action`` on a zero-match panel must be a no-op (same guard).
* ``update_navigation_buttons`` mid-range must enable both arrows
  simultaneously (covers the 1 <= current <= total-1 elif branch).
* ``component_shown`` without a search panel attached must not crash —
  upstream guards on ``searchPanel != null``.
* ``update_high_lighter`` with ``present_index`` out of range and a valid
  ``previous_index`` must still retag the previous span (boundary branch).
* ``change_highlighter`` two-argument form on the last highlight must
  re-emit a fresh :class:`Highlight` so the recorded painter is in sync.
"""

from __future__ import annotations

from pypdfbox.debugger.ui.textsearcher.searcher import (
    PAINTER,
    SELECTION_PAINTER,
    Searcher,
)


class _StubText:
    """Minimal ``tk.Text`` stand-in (mirrors the shared helper)."""

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


def test_previous_action_with_no_matches_is_noop() -> None:
    widget = _StubText("nothing here")
    searcher = Searcher(widget)
    searcher.search("zzz")  # zero hits, total=0, current=-1
    # Counters should reflect "no match" state.
    assert searcher._total_match == 0  # type: ignore[attr-defined]
    assert searcher._current_match == -1  # type: ignore[attr-defined]
    searcher._previous_action()  # type: ignore[attr-defined]
    # State unchanged: still zero-match, no scroll.
    assert searcher._current_match == -1  # type: ignore[attr-defined]
    assert widget.see_calls == []


def test_next_action_with_no_matches_is_noop() -> None:
    widget = _StubText("nothing here")
    searcher = Searcher(widget)
    searcher.search("zzz")
    searcher._next_action()  # type: ignore[attr-defined]
    assert searcher._current_match == -1  # type: ignore[attr-defined]
    assert widget.see_calls == []


def test_update_navigation_buttons_midrange_enables_both() -> None:
    """Mid-range: current_match = 1 of 3 => prev True, next True."""
    widget = _StubText("a a a a a")  # 5 hits at offsets 0,2,4,6,8
    searcher = Searcher(widget)
    searcher.search("a")
    searcher._current_match = 2  # type: ignore[attr-defined]
    searcher.update_navigation_buttons()
    assert searcher._previous_enabled is True  # type: ignore[attr-defined]
    assert searcher._next_enabled is True  # type: ignore[attr-defined]


def test_component_shown_with_no_panel_is_noop() -> None:
    """Without ``init()`` the search panel is None and the guard must hold."""
    widget = _StubText("hello")
    searcher = Searcher(widget)
    assert searcher._search_panel is None  # type: ignore[attr-defined]
    # Must not raise even without a panel attached.
    searcher.component_shown(None)


def test_update_high_lighter_skips_out_of_range_present_index() -> None:
    """``present_index`` >= len(highlights) is silently ignored;
    ``previous_index`` is still applied."""
    widget = _StubText("foo bar foo")
    searcher = Searcher(widget)
    searcher.search("foo")  # 2 hits
    widget.tag_add_calls.clear()
    widget.tag_remove_calls.clear()
    # present_index 99 is out of range; previous_index 0 is in range.
    searcher.update_high_lighter(present_index=99, previous_index=0)
    # The previous span should have been retagged with PAINTER, but the
    # bogus present index should not crash and should not add SELECTION_PAINTER.
    selection_adds = [c for c in widget.tag_add_calls if c[0] == SELECTION_PAINTER]
    painter_adds = [c for c in widget.tag_add_calls if c[0] == PAINTER]
    assert selection_adds == []
    assert len(painter_adds) == 1


def test_update_high_lighter_skips_negative_previous_index() -> None:
    """``previous_index == -1`` with a real ``present_index`` only retags
    the present highlight (covers the ``previous_index != -1`` branch)."""
    widget = _StubText("foo bar foo")
    searcher = Searcher(widget)
    searcher.search("foo")
    widget.tag_add_calls.clear()
    widget.tag_remove_calls.clear()
    searcher.update_high_lighter(present_index=1, previous_index=-1)
    selection_adds = [c for c in widget.tag_add_calls if c[0] == SELECTION_PAINTER]
    painter_adds = [c for c in widget.tag_add_calls if c[0] == PAINTER]
    assert len(selection_adds) == 1
    assert painter_adds == []


def test_change_highlighter_painter_form_updates_recorded_painter() -> None:
    """The two-argument painter swap must rewrite ``self._highlights[index]``
    so subsequent reads see the new painter (parity with the upstream
    side-effect on ``Highlighter.Highlight``)."""
    widget = _StubText("foo bar foo")
    searcher = Searcher(widget)
    matches = searcher.search("foo")
    assert matches[0].painter == PAINTER
    searcher.change_highlighter(0, SELECTION_PAINTER)
    assert searcher._highlights[0].painter == SELECTION_PAINTER  # type: ignore[attr-defined]
    # Offsets are preserved.
    assert searcher._highlights[0].start_offset == matches[0].start_offset  # type: ignore[attr-defined]
    assert searcher._highlights[0].end_offset == matches[0].end_offset  # type: ignore[attr-defined]
