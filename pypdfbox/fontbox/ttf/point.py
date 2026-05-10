"""Single glyph point used by :class:`GlyphRenderer`.

Mirrors the package-private static ``Point`` nested in upstream
``org.apache.fontbox.ttf.GlyphRenderer`` (GlyphRenderer.java lines
193-220). Upstream keeps the class private; pypdfbox lifts it into its
own module so the ported renderer and tests can reference it without
reaching into private state.

The carrier holds five attributes:

``x`` / ``y``
    Integer device-space coordinates of the point.
``on_curve``
    True iff the point is on the rasterised contour (matches the
    ``GlyfDescript.ON_CURVE`` flag).
``end_of_contour``
    True iff this point closes a contour.
``touched``
    Hinter-tracking flag used by composite resolution; upstream's
    nested class doesn't carry this field explicitly but pdf.js and
    other ports do, and pypdfbox callers set it during composite
    decoding.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Point:
    """One glyph contour point.

    See module docstring for the field semantics.
    """

    x: int = 0
    y: int = 0
    on_curve: bool = True
    end_of_contour: bool = False
    touched: bool = False

    def to_string(self) -> str:
        """Mirror upstream ``toString()`` (GlyphRenderer.java line 217).

        Format ``Point(x,y,onCurve,endOfContour)`` where the last two
        slots collapse to empty strings when the flags are unset.
        """
        on_curve_label = "onCurve" if self.on_curve else ""
        end_label = "endOfContour" if self.end_of_contour else ""
        return f"Point({self.x},{self.y},{on_curve_label},{end_label})"

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["Point"]
