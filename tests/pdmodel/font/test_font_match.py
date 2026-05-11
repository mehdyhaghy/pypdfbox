"""Tests for :mod:`pypdfbox.pdmodel.font.font_match`.

:class:`FontMatch` is a private nested class upstream so no JUnit tests
exist. The shape we need to preserve is *ordering*: highest-scoring
match pops first from a heap.
"""

from __future__ import annotations

import heapq
from typing import Any

from pypdfbox.pdmodel.font.font_match import FontMatch


class _FakeFontInfo:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"_FakeFontInfo({self.name!r})"


def test_default_score_is_zero() -> None:
    match = FontMatch(_FakeFontInfo("any"))
    assert match.score == 0.0


def test_info_stored_verbatim() -> None:
    info = _FakeFontInfo("Arial")
    match = FontMatch(info)
    assert match.info is info


def test_higher_score_pops_first_from_min_heap() -> None:
    # Verify heapq pops the highest-scoring FontMatch first.
    queue: list[FontMatch] = []
    low = FontMatch(_FakeFontInfo("low"))
    low.score = 1.0
    high = FontMatch(_FakeFontInfo("high"))
    high.score = 5.0
    mid = FontMatch(_FakeFontInfo("mid"))
    mid.score = 3.0
    for m in (low, high, mid):
        heapq.heappush(queue, m)
    assert heapq.heappop(queue).info.name == "high"
    assert heapq.heappop(queue).info.name == "mid"
    assert heapq.heappop(queue).info.name == "low"


def test_repr_contains_score_and_info() -> None:
    match = FontMatch(_FakeFontInfo("Arial"))
    match.score = 2.5
    text = repr(match)
    assert "2.5" in text
    assert "Arial" in text


def test_lt_compared_against_non_match_returns_notimplemented() -> None:
    match = FontMatch(_FakeFontInfo("any"))
    # Python's NotImplemented machinery promotes to TypeError under <.
    result: Any
    try:
        result = match < 42
    except TypeError:
        result = "TypeError"
    assert result == "TypeError"
