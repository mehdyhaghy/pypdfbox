"""Tests for the :class:`FontPane` abstract base."""

from __future__ import annotations

from pypdfbox.debugger.fontencodingpane.font_pane import FontPane


class _ConcreteFontPane(FontPane):
    def get_panel(self):  # pragma: no cover - never called by these tests
        raise NotImplementedError


def test_y_bounds_empty_table_returns_zero_zero():
    pane = _ConcreteFontPane()
    assert pane.get_y_bounds([], 0) == (0.0, 0.0)


def test_y_bounds_skips_string_sentinels():
    pane = _ConcreteFontPane()
    rows = [
        ["code", "name", "u", "No glyph"],
        ["code", "name", "u", ".notdef"],
        ["code", "name", "u", None],
    ]
    assert pane.get_y_bounds(rows, 3) == (0.0, 0.0)


def test_y_bounds_walks_tuple_paths():
    pane = _ConcreteFontPane()
    # Each row's path is a sequence of ("moveTo"/"lineTo"/etc, x, y) entries.
    path1 = [("moveTo", 0.0, -10.0), ("lineTo", 5.0, 20.0)]
    path2 = [("moveTo", 0.0, 15.0), ("lineTo", 5.0, 30.0)]
    rows = [
        ["c", "n", "u", path1],
        ["c", "n", "u", path2],
    ]
    lo, hi = pane.get_y_bounds(rows, 3)
    # Capped at 0 / floored at 0 mirrors upstream behaviour: minY=-10, maxY=30.
    assert lo == -10.0
    assert hi == 30.0


def test_y_bounds_ignores_glyph_index_out_of_range():
    pane = _ConcreteFontPane()
    rows = [["only-one-column"]]
    assert pane.get_y_bounds(rows, 3) == (0.0, 0.0)


# ---- rectangle-like accessor path ----------------------------------------


class _Bounds:
    """Minimal rectangle-like helper for the ``get_bounds`` fast path."""

    def __init__(self, min_y: float, max_y: float) -> None:
        self.min_y = min_y
        self.max_y = max_y


class _BoundsContainer:
    def __init__(self, lo: float, hi: float) -> None:
        self._bounds = _Bounds(lo, hi)

    def get_bounds(self) -> _Bounds:
        return self._bounds


def test_y_bounds_uses_rectangle_accessor():
    pane = _ConcreteFontPane()
    rows = [["c", "n", "u", _BoundsContainer(-3.0, 8.0)]]
    lo, hi = pane.get_y_bounds(rows, 3)
    assert lo == -3.0
    assert hi == 8.0


class _YHContainer:
    """Variant exposing ``y`` + ``height`` instead of min/max."""

    class _R:
        def __init__(self, y: float, h: float) -> None:
            self.min_y = None
            self.max_y = None
            self.y = y
            self.height = h

    def __init__(self, y: float, h: float) -> None:
        self._rect = self._R(y, h)

    def get_bounds(self) -> _R:  # type: ignore[name-defined]
        return self._rect


def test_y_bounds_with_y_height_accessor():
    """Variant accessor (``y`` + ``height``) feeds into the same bounds
    aggregator. Min is capped at 0 and max is floored at 0, mirroring
    upstream's ``Math.min(0, ...)`` / ``Math.max(0, ...)`` calls."""
    pane = _ConcreteFontPane()
    rows = [["c", "n", "u", _YHContainer(-1.0, 5.0)]]
    lo, hi = pane.get_y_bounds(rows, 3)
    # -1 < 0, so min_y becomes -1; max_y stays >= 0.
    assert lo == -1.0
    assert hi == 4.0  # -1 + 5


class _EmptyBoundsContainer:
    def __init__(self) -> None:
        self._bounds = _Bounds(0.0, 0.0)

    def get_bounds(self) -> _Bounds:
        return self._bounds


def test_y_bounds_skips_empty_rectangle_bounds():
    pane = _ConcreteFontPane()
    rows = [["c", "n", "u", _EmptyBoundsContainer()]]
    # Empty bounds — overall result is still (0, 0).
    assert pane.get_y_bounds(rows, 3) == (0.0, 0.0)


class _RaisingBoundsContainer:
    def get_bounds(self) -> _Bounds:
        raise RuntimeError("boom")


def test_y_bounds_swallows_exceptions_from_bounds_method():
    pane = _ConcreteFontPane()
    rows = [["c", "n", "u", _RaisingBoundsContainer()]]
    # ``get_bounds`` raised → fall through to iterable path which fails
    # because the object isn't iterable → ``None`` → row skipped.
    assert pane.get_y_bounds(rows, 3) == (0.0, 0.0)


def test_y_bounds_handles_path_iteration_error():
    """Items that aren't iterable should yield ``None`` and be skipped."""
    pane = _ConcreteFontPane()
    # An ``int`` is not iterable as a path → row contributes nothing.
    rows = [["c", "n", "u", 42]]
    assert pane.get_y_bounds(rows, 3) == (0.0, 0.0)


def test_y_bounds_handles_empty_iterable_path():
    pane = _ConcreteFontPane()
    rows = [["c", "n", "u", []]]
    assert pane.get_y_bounds(rows, 3) == (0.0, 0.0)


def test_y_bounds_treats_bool_values_as_non_numeric():
    """``_maybe_float(True)`` returns ``None`` so the path contributes nothing."""
    pane = _ConcreteFontPane()
    rows = [["c", "n", "u", [(True, False)]]]
    assert pane.get_y_bounds(rows, 3) == (0.0, 0.0)
