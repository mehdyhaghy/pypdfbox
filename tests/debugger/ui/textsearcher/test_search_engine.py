"""Hand-written tests for :class:`SearchEngine`."""

from __future__ import annotations

import pytest

from pypdfbox.debugger.ui.textsearcher.search_engine import (
    Highlight,
    SearchEngine,
)


class _FakeWidget:
    """In-memory stand-in for the ``tk.Text`` surface used by the engine."""

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


@pytest.fixture
def engine() -> tuple[SearchEngine, _FakeWidget]:
    widget = _FakeWidget("Hello hello HELLO world")
    eng = SearchEngine(
        get_text=widget.get_text,
        add_highlight=widget.add_highlight,
        remove_all_highlights=widget.remove_all_highlights,
        painter="match",
    )
    return eng, widget


def test_search_none_returns_empty_list_and_does_not_clear(
    engine: tuple[SearchEngine, _FakeWidget],
) -> None:
    eng, widget = engine
    assert eng.search(None, True) == []
    assert widget.cleared == 0


def test_search_empty_clears_but_returns_empty(
    engine: tuple[SearchEngine, _FakeWidget],
) -> None:
    eng, widget = engine
    assert eng.search("", True) == []
    assert widget.cleared == 1


def test_search_case_sensitive(
    engine: tuple[SearchEngine, _FakeWidget],
) -> None:
    eng, widget = engine
    highlights = eng.search("Hello", True)
    assert len(highlights) == 1
    assert highlights[0] == Highlight(0, 5, "match")
    assert widget.added == [(0, 5, "match")]


def test_search_case_insensitive_matches_all(
    engine: tuple[SearchEngine, _FakeWidget],
) -> None:
    eng, _widget = engine
    highlights = eng.search("hello", False)
    assert [(h.start_offset, h.end_offset) for h in highlights] == [
        (0, 5),
        (6, 11),
        (12, 17),
    ]


def test_search_non_overlapping_iterations() -> None:
    widget = _FakeWidget("aaaa")
    eng = SearchEngine(
        get_text=widget.get_text,
        add_highlight=widget.add_highlight,
        remove_all_highlights=widget.remove_all_highlights,
        painter="match",
    )
    highlights = eng.search("aa", True)
    # Like upstream, matches advance past the full match (no overlap).
    assert [(h.start_offset, h.end_offset) for h in highlights] == [(0, 2), (2, 4)]


def test_search_regex_basic() -> None:
    widget = _FakeWidget("apple ape application")
    eng = SearchEngine(
        get_text=widget.get_text,
        add_highlight=widget.add_highlight,
        remove_all_highlights=widget.remove_all_highlights,
        painter="match",
    )
    highlights = eng.search_regex(r"ap\w+", True)
    assert [widget.text[h.start_offset : h.end_offset] for h in highlights] == [
        "apple",
        "ape",
        "application",
    ]


def test_search_regex_case_insensitive() -> None:
    widget = _FakeWidget("CAT cat Cat")
    eng = SearchEngine(
        get_text=widget.get_text,
        add_highlight=widget.add_highlight,
        remove_all_highlights=widget.remove_all_highlights,
        painter="match",
    )
    assert len(eng.search_regex(r"cat", False)) == 3
    assert len(eng.search_regex(r"cat", True)) == 1


def test_search_regex_invalid_pattern_returns_empty() -> None:
    widget = _FakeWidget("text")
    eng = SearchEngine(
        get_text=widget.get_text,
        add_highlight=widget.add_highlight,
        remove_all_highlights=widget.remove_all_highlights,
        painter="match",
    )
    assert eng.search_regex(r"(unclosed", True) == []


def test_search_regex_skips_zero_width_matches() -> None:
    widget = _FakeWidget("aaa")
    eng = SearchEngine(
        get_text=widget.get_text,
        add_highlight=widget.add_highlight,
        remove_all_highlights=widget.remove_all_highlights,
        painter="match",
    )
    # ``a*`` matches the empty string repeatedly; the engine drops them so
    # only the substantive run is reported.
    highlights = eng.search_regex(r"a*", True)
    assert [(h.start_offset, h.end_offset) for h in highlights] == [(0, 3)]
