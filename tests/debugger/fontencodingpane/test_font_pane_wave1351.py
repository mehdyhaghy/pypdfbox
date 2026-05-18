"""Wave 1351 coverage-boost tests for ``FontPane``.

Targets the residual branches in :func:`_iter_xy_pairs` — early return
for ``None`` / ``str`` items inside the outer iterable, and the final
fallback for items that are neither ``list`` nor ``tuple``.
"""

from __future__ import annotations

from pypdfbox.debugger.fontencodingpane.font_pane import FontPane


class _ConcreteFontPane(FontPane):
    def get_panel(self):  # pragma: no cover - never called by these tests
        raise NotImplementedError


def test_y_bounds_path_with_none_segment_is_skipped() -> None:
    """A path whose top-level iterates is fine, but inner ``None``
    items hit ``_iter_xy_pairs``'s early ``None`` short-circuit
    (line 138)."""
    pane = _ConcreteFontPane()
    rows = [["c", "n", "u", [None]]]
    # Inner None is skipped → no points → row contributes nothing.
    assert pane.get_y_bounds(rows, 3) == (0.0, 0.0)


def test_y_bounds_path_with_string_segment_is_skipped() -> None:
    """A path whose inner item is a ``str`` is treated as a sentinel
    inside ``_iter_xy_pairs`` and contributes no points (line 138)."""
    pane = _ConcreteFontPane()
    rows = [["c", "n", "u", ["closePath"]]]
    assert pane.get_y_bounds(rows, 3) == (0.0, 0.0)


def test_y_bounds_path_with_scalar_segment_is_skipped() -> None:
    """A path whose inner item is neither list nor tuple (e.g. an int)
    falls through to the final ``return []`` (line 150)."""
    pane = _ConcreteFontPane()
    rows = [["c", "n", "u", [42]]]
    assert pane.get_y_bounds(rows, 3) == (0.0, 0.0)


def test_y_bounds_path_with_object_segment_is_skipped() -> None:
    """An opaque object as an inner path item also hits the final
    ``return []`` in ``_iter_xy_pairs`` (line 150)."""
    pane = _ConcreteFontPane()
    rows = [["c", "n", "u", [object()]]]
    assert pane.get_y_bounds(rows, 3) == (0.0, 0.0)
