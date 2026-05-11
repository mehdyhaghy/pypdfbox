from __future__ import annotations

from pypdfbox.pdmodel.pd_rectangle import PDRectangle


class PDImmutableRectangle(PDRectangle):
    """Immutable :class:`PDRectangle` — coordinate setters raise.

    Mirrors ``org.apache.pdfbox.pdmodel.common.PDImmutableRectangle`` (Java
    lines 22-71). Used for the paper-size constants exposed on
    :class:`PDRectangle` (``LETTER``, ``A4``, ``LEGAL`` …) so callers can
    safely share them without worrying about a downstream mutation
    bleeding back into another caller's rectangle.
    """

    def __init__(self, width: float, height: float) -> None:
        """Construct an immutable rectangle from origin to ``(width,
        height)``. Mirrors upstream ``PDImmutableRectangle(float, float)``
        (Java line 31)."""
        super().__init__(0.0, 0.0, float(width), float(height))

    # ---------- forbidden setters ----------

    def set_upper_right_y(self, value: float) -> None:
        """Always raises — this rectangle is immutable."""
        raise TypeError("Immutable class")

    def set_upper_right_x(self, value: float) -> None:
        """Always raises — this rectangle is immutable."""
        raise TypeError("Immutable class")

    def set_lower_left_y(self, value: float) -> None:
        """Always raises — this rectangle is immutable."""
        raise TypeError("Immutable class")

    def set_lower_left_x(self, value: float) -> None:
        """Always raises — this rectangle is immutable."""
        raise TypeError("Immutable class")


__all__ = ["PDImmutableRectangle"]
