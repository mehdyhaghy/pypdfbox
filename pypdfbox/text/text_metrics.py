from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.text.text_position import TextPosition


class TextMetrics:
    """Text-run metrics derived from a single :class:`TextPosition`.

    Lite port that mirrors the conceptual shape of a small data-holder
    used inside ``org.apache.pdfbox.text`` to capture the vertical and
    horizontal extents of a decoded text run.

    The metrics are seeded from the supplied :class:`TextPosition`:

    - :meth:`get_ascent`  — cap-height approximation derived from the
      run's font size (upstream: 0.7 * font size).
    - :meth:`get_descent` — descender approximation derived from the
      run's font size (upstream: 0.2 * font size, returned negative).
    - :meth:`get_height`  — overall line height (ascent + abs(descent)).
    - :meth:`get_x` / :meth:`get_y` — text origin in user space, taken
      directly from the source ``TextPosition``.

    Mutating accessors (:meth:`set_ascent`, :meth:`set_descent`) keep
    the data-holder writable for callers that progressively refine the
    metrics over a glyph run, matching the upstream pattern.
    """

    # Upstream cap-height / descender ratios used when deriving metrics
    # from a font size alone. Kept as class-level constants so callers
    # can override behavior in subclasses.
    _ASCENT_RATIO = 0.7
    _DESCENT_RATIO = -0.2

    def __init__(self, first: TextPosition) -> None:
        self._x: float = float(first.get_x())
        self._y: float = float(first.get_y())
        font_size = float(first.get_font_size())
        self._ascent: float = font_size * self._ASCENT_RATIO
        self._descent: float = font_size * self._DESCENT_RATIO

    # --- Accessors ----------------------------------------------------

    def get_ascent(self) -> float:
        return self._ascent

    def set_ascent(self, ascent: float) -> None:
        self._ascent = float(ascent)

    def get_descent(self) -> float:
        return self._descent

    def set_descent(self, descent: float) -> None:
        self._descent = float(descent)

    def get_height(self) -> float:
        """Overall line height: ascent plus the magnitude of descent."""
        return self._ascent + abs(self._descent)

    def get_x(self) -> float:
        return self._x

    def get_y(self) -> float:
        return self._y


__all__ = ["TextMetrics"]
