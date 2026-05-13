"""Abstract base for encoding-inspector panes.

Ported from ``org.apache.pdfbox.debugger.fontencodingpane.FontPane``.

The upstream Java class declares an abstract ``getPanel()`` returning a
``JPanel`` and a package-private ``getYBounds`` helper. The Tkinter port
keeps the same surface: concrete subclasses return a ``ttk.Frame``
(typed as :class:`tkinter.Misc`) from :meth:`get_panel`, and
:meth:`get_y_bounds` walks the table data to find the min/max y range
shared across every glyph path so the rendering scale lines up between
rows.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import tkinter as tk


class FontPane(ABC):
    """Abstract base for the per-font-type encoding panes.

    Mirrors upstream's ``abstract class FontPane``. Concrete subclasses
    (``SimpleFont``, ``Type0Font``, ``Type3Font``) provide the
    :meth:`get_panel` implementation.
    """

    @abstractmethod
    def get_panel(self) -> tk.Misc:
        """Return the Tkinter widget showing this font's encoding table.

        Mirrors upstream ``abstract JPanel getPanel()``.
        """

    # ---- shared helpers ----------------------------------------------------

    def get_y_bounds(
        self, table_data: Sequence[Sequence[Any]], glyph_index: int
    ) -> tuple[float, float]:
        """Return ``(min_y, max_y)`` over the glyph paths in ``table_data``.

        Mirrors upstream ``double[] getYBounds(Object[][], int)``: scans
        the supplied 2-d data, finds the column at ``glyph_index`` (the
        glyph outline / path), and returns the global min lower bound
        (capped at ``0``) and max upper bound (floored at ``0``).

        The Java upstream consumes a ``java.awt.geom.GeneralPath`` and
        calls ``getBounds2D()``. Pypdfbox stores outlines as whatever the
        concrete font subclass produces (a list of contour tuples for
        Type1, a fontTools ``glyph`` for TrueType, etc.). To stay
        renderer-agnostic this helper walks the outline coordinates
        directly, treating any 2-element ``(x, y)`` pair found inside the
        path as a control point.
        """
        min_y: float = 0.0
        max_y: float = 0.0
        for row in table_data:
            if glyph_index >= len(row):
                continue
            path = row[glyph_index]
            bounds = _path_y_bounds(path)
            if bounds is None:
                continue
            lo, hi = bounds
            min_y = min(min_y, lo)
            max_y = max(max_y, hi)
        return (min_y, max_y)


def _path_y_bounds(path: Any) -> tuple[float, float] | None:
    """Return ``(min_y, max_y)`` for ``path`` or ``None`` for empty / opaque.

    Recognises three shapes:

    1. ``None`` and string sentinels (e.g. ``"No glyph"``) — return ``None``.
    2. Anything with a ``get_bounds`` / ``getBounds2D`` / ``bounds`` method
       returning a rectangle-like object with ``min_y`` & ``max_y``
       attributes (or ``y`` & ``height``) — used in tests where we hand in
       a stand-in object.
    3. Iterables of segment tuples — walks every ``(x, y)`` pair that can
       be coerced to a float and uses min/max on the y values. Empty
       iterables return ``None`` so the caller can skip them.
    """
    if path is None or isinstance(path, str):
        return None

    # Rectangle-like accessors (fast path for objects that already know
    # their own bbox).
    for attr in ("get_bounds", "getBounds2D", "bounds"):
        if hasattr(path, attr):
            try:
                rect = getattr(path, attr)
                rect = rect() if callable(rect) else rect
            except Exception:  # noqa: BLE001 — defensive: any failure ⇒ fall through
                rect = None
            if rect is not None:
                lo = _maybe_float(getattr(rect, "min_y", None))
                hi = _maybe_float(getattr(rect, "max_y", None))
                if lo is None or hi is None:
                    y = _maybe_float(getattr(rect, "y", None))
                    h = _maybe_float(getattr(rect, "height", None))
                    if y is not None and h is not None:
                        lo, hi = y, y + h
                if lo is not None and hi is not None and not (lo == 0.0 and hi == 0.0):
                    return (lo, hi)
                if lo is not None and hi is not None:
                    # Empty bounds — skip, mirroring upstream's
                    # ``bounds2D.isEmpty()`` short-circuit.
                    return None
            break  # only consult the first matching accessor

    # Fall back to walking the iterable for ``(x, y)`` pairs.
    try:
        items = list(path)
    except TypeError:
        return None
    if not items:
        return None
    lo_y: float | None = None
    hi_y: float | None = None
    for item in items:
        for pt in _iter_xy_pairs(item):
            y = pt[1]
            lo_y = y if lo_y is None else min(lo_y, y)
            hi_y = y if hi_y is None else max(hi_y, y)
    if lo_y is None or hi_y is None:
        return None
    return (lo_y, hi_y)


def _iter_xy_pairs(item: Any) -> list[tuple[float, float]]:
    """Pull ``(x, y)`` pairs out of a single path-segment entry."""
    if item is None or isinstance(item, str):
        return []
    # Tuple of (verb, *coords) or (x, y) raw.
    if isinstance(item, (list, tuple)):
        coords: list[float] = []
        for value in item:
            f = _maybe_float(value)
            if f is not None:
                coords.append(f)
        # Group consecutive floats into pairs.
        return [
            (coords[i], coords[i + 1]) for i in range(0, len(coords) - 1, 2)
        ]
    return []


def _maybe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
