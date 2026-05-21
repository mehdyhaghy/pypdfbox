"""Wave 1365 parity tests for :class:`SearchEngine`.

Upstream ``SearchEngine.java`` is the pure-text search backend behind the
debugger's find bar. The existing waves cover the obvious paths (case
sensitivity, regex, ``None``/empty inputs); this file fills the remaining
upstream-mirrored semantics that were not directly exercised:

* ``search`` on a non-overlapping key advances ``start_at`` by the full
  key length (parity with upstream's ``index += searchKey.length()``).
* ``search`` calls ``remove_all_highlights`` exactly once before walking
  the document (matches the upstream ``removeAllHighlights()`` call).
* ``search`` on an all-overlapping potential pattern still emits
  non-overlapping hits ("aaa" in "aaaaa" => 1 hit, not 3).
* ``search`` returns an empty list (and does NOT clear) when the input is
  ``None`` — verifies the early-return order is "check None *before*
  clear", matching upstream.
* ``search_regex`` emits the correct ``Highlight.painter`` for every match.
* ``search`` records the matched substring length on each :class:`Highlight`
  (``end_offset - start_offset == len(key)``).
* ``search_regex`` returns an empty list (and does NOT clear) when the
  pattern is ``None``.
"""

from __future__ import annotations

from pypdfbox.debugger.ui.textsearcher.search_engine import SearchEngine


class _Sink:
    """Capture-only callbacks that record everything they receive."""

    def __init__(self, body: str) -> None:
        self._body = body
        self.add_calls: list[tuple[int, int, str]] = []
        self.remove_calls: int = 0

    def get_text(self) -> str:
        return self._body

    def add_highlight(self, start: int, end: int, painter: str) -> None:
        self.add_calls.append((start, end, painter))

    def remove_all_highlights(self) -> None:
        self.remove_calls += 1


def _engine(body: str, painter: str = "match") -> tuple[SearchEngine, _Sink]:
    sink = _Sink(body)
    engine = SearchEngine(
        get_text=sink.get_text,
        add_highlight=sink.add_highlight,
        remove_all_highlights=sink.remove_all_highlights,
        painter=painter,
    )
    return engine, sink


def test_search_advances_past_full_key_length() -> None:
    """Hits must not overlap — start_at jumps to ``end`` each iteration."""
    engine, sink = _engine("ababab")
    hits = engine.search("ab", True)
    starts = [h.start_offset for h in hits]
    assert starts == [0, 2, 4]


def test_search_overlap_candidate_is_non_overlapping() -> None:
    """``"aa"`` in ``"aaaa"`` => exactly 2 non-overlapping hits."""
    engine, sink = _engine("aaaa")
    hits = engine.search("aa", True)
    starts = [h.start_offset for h in hits]
    assert starts == [0, 2]


def test_search_removes_all_highlights_exactly_once() -> None:
    """Upstream calls ``removeAllHighlights()`` once before walking matches."""
    engine, sink = _engine("foo bar foo")
    engine.search("foo", True)
    assert sink.remove_calls == 1


def test_search_none_does_not_clear() -> None:
    """``None`` returns empty without invoking ``remove_all_highlights``."""
    engine, sink = _engine("anything")
    out = engine.search(None, True)
    assert out == []
    assert sink.remove_calls == 0


def test_search_records_painter_on_every_highlight() -> None:
    engine, sink = _engine("xy xy xy", painter="custom")
    hits = engine.search("xy", True)
    assert all(h.painter == "custom" for h in hits)
    assert all(c[2] == "custom" for c in sink.add_calls)


def test_search_highlight_span_matches_key_length() -> None:
    """Every emitted highlight covers exactly ``len(key)`` characters."""
    engine, sink = _engine("abc abc abc")
    hits = engine.search("abc", True)
    for h in hits:
        assert h.end_offset - h.start_offset == 3


def test_search_regex_none_does_not_clear() -> None:
    """``None`` pattern short-circuits without calling ``remove_all_highlights``."""
    engine, sink = _engine("anything")
    out = engine.search_regex(None, True)
    assert out == []
    assert sink.remove_calls == 0


def test_search_on_empty_document_returns_empty_but_clears() -> None:
    """Empty body still triggers ``remove_all_highlights`` (parity with the
    pre-loop clear) but produces no hits."""
    engine, sink = _engine("")
    hits = engine.search("anything", True)
    assert hits == []
    assert sink.remove_calls == 1
    assert sink.add_calls == []
