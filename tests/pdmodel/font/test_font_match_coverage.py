"""Coverage tests for :mod:`pypdfbox.pdmodel.font.font_match`.

The existing ``test_font_match`` file exercises the ``__lt__`` / heapq
ordering and ``__repr__``; this module fills the remaining gap on
:meth:`FontMatch.compare_to`, which mirrors the upstream Java
``compareTo(FontMatch)`` and must return a negative / zero / positive
int that orders highest score first.
"""

from __future__ import annotations

from pypdfbox.pdmodel.font.font_match import FontMatch


class _FakeFontInfo:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"_FakeFontInfo({self.name!r})"


def test_compare_to_equal_scores_returns_zero() -> None:
    a = FontMatch(_FakeFontInfo("a"))
    b = FontMatch(_FakeFontInfo("b"))
    a.score = 2.5
    b.score = 2.5
    assert a.compare_to(b) == 0


def test_compare_to_self_returns_negative_when_higher_score() -> None:
    """Mirror upstream: higher-score self orders BEFORE other."""
    a = FontMatch(_FakeFontInfo("a"))
    b = FontMatch(_FakeFontInfo("b"))
    a.score = 5.0
    b.score = 1.0
    assert a.compare_to(b) == -1


def test_compare_to_self_returns_positive_when_lower_score() -> None:
    a = FontMatch(_FakeFontInfo("a"))
    b = FontMatch(_FakeFontInfo("b"))
    a.score = 1.0
    b.score = 5.0
    assert a.compare_to(b) == 1


def test_compare_to_zero_score_pair_equal() -> None:
    """Two freshly-built FontMatch instances tie at ``compare_to == 0``."""
    a = FontMatch(_FakeFontInfo("a"))
    b = FontMatch(_FakeFontInfo("b"))
    assert a.compare_to(b) == 0
    assert b.compare_to(a) == 0
