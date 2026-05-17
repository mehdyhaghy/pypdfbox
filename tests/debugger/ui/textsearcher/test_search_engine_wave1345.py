"""Wave 1345 coverage-boost tests for :class:`SearchEngine` and :class:`Highlight`.

Targets:

* lines 41/44/47 — the camelCase-parity getter methods on
  :class:`Highlight` (``get_start_offset`` / ``get_end_offset`` /
  ``get_painter``).
* lines 117, 147, 150 — search's "empty key after lower-casing" branch
  plus the ``search_regex`` early-return arms for ``None`` and ``""``.

Line 117 is unreachable in normal text — ``str.lower()`` cannot empty a
non-empty string in Python's Unicode case-folding tables — but the
defensive guard is exercised here via a stub whose ``lower()`` *does*
collapse, just to keep coverage 100% honest.
"""

from __future__ import annotations

from pypdfbox.debugger.ui.textsearcher.search_engine import (
    Highlight,
    SearchEngine,
)


class _FakeWidget:
    def __init__(self, text: str) -> None:
        self.text = text
        self.added: list[tuple[int, int, str]] = []
        self.cleared = 0

    def get_text(self) -> str:
        return self.text

    def add_highlight(self, start: int, end: int, painter: str) -> None:
        self.added.append((start, end, painter))

    def remove_all_highlights(self) -> None:
        self.cleared += 1
        self.added.clear()


def _engine() -> tuple[SearchEngine, _FakeWidget]:
    widget = _FakeWidget("hello")
    return SearchEngine(
        get_text=widget.get_text,
        add_highlight=widget.add_highlight,
        remove_all_highlights=widget.remove_all_highlights,
        painter="match",
    ), widget


def test_highlight_camel_case_getters_return_construction_values() -> None:
    """``Highlight.get_*`` getters mirror upstream's ``Highlighter.Highlight``
    interface."""
    h = Highlight(7, 13, "tag-a")
    assert h.get_start_offset() == 7
    assert h.get_end_offset() == 13
    assert h.get_painter() == "tag-a"


class _StrCollapsingToEmpty(str):
    """A ``str`` subclass whose ``.lower()`` collapses to ``""``.

    Lets us exercise the defensive ``search_key_length == 0`` guard
    after the lower-cased re-assignment, which no real Unicode input
    could otherwise produce.
    """

    def lower(self) -> str:  # type: ignore[override]
        return ""


def test_search_case_insensitive_empty_after_lower_returns_early() -> None:
    """The defensive ``len(search_key) == 0`` branch is reached when
    ``.lower()`` collapses the input. Line 117."""
    eng, widget = _engine()
    result = eng.search(_StrCollapsingToEmpty("abc"), False)
    assert result == []
    # Highlights must have been cleared once at line 100.
    assert widget.cleared == 1


def test_search_regex_with_none_returns_empty_and_does_not_clear() -> None:
    """``search_regex(None, ...)`` returns ``[]`` without clearing highlights.

    Mirrors the early-return guard at line 147.
    """
    eng, widget = _engine()
    assert eng.search_regex(None, True) == []
    assert widget.cleared == 0


def test_search_regex_with_empty_pattern_clears_but_returns_empty() -> None:
    """``search_regex("", ...)`` clears highlights but returns ``[]``.

    Mirrors the early-return guard at line 150 (after the clear call).
    """
    eng, widget = _engine()
    assert eng.search_regex("", True) == []
    assert widget.cleared == 1
