from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fontTools.pens.recordingPen import RecordingPen


class BoundingBox:
    """Lightweight bounding box.

    Mirrors ``org.apache.fontbox.util.BoundingBox`` (enough surface for
    glyph consumers: lower-left / upper-right floats and a four-arg
    constructor). The full upstream class lives under ``fontbox.util``;
    we inline a minimal version here so :class:`GlyphData` callers don't
    need to reach into a sibling package that isn't ported yet.
    """

    def __init__(
        self,
        min_x: float = 0.0,
        min_y: float = 0.0,
        max_x: float = 0.0,
        max_y: float = 0.0,
    ) -> None:
        self._lower_left_x = float(min_x)
        self._lower_left_y = float(min_y)
        self._upper_right_x = float(max_x)
        self._upper_right_y = float(max_y)

    def get_lower_left_x(self) -> float:
        return self._lower_left_x

    def get_lower_left_y(self) -> float:
        return self._lower_left_y

    def get_upper_right_x(self) -> float:
        return self._upper_right_x

    def get_upper_right_y(self) -> float:
        return self._upper_right_y

    def set_lower_left_x(self, value: float) -> None:
        self._lower_left_x = float(value)

    def set_lower_left_y(self, value: float) -> None:
        self._lower_left_y = float(value)

    def set_upper_right_x(self, value: float) -> None:
        self._upper_right_x = float(value)

    def set_upper_right_y(self, value: float) -> None:
        self._upper_right_y = float(value)

    def get_width(self) -> float:
        return self._upper_right_x - self._lower_left_x

    def get_height(self) -> float:
        return self._upper_right_y - self._lower_left_y

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (
            self._lower_left_x,
            self._lower_left_y,
            self._upper_right_x,
            self._upper_right_y,
        )

    def __repr__(self) -> str:
        return (
            f"BoundingBox({self._lower_left_x}, {self._lower_left_y}, "
            f"{self._upper_right_x}, {self._upper_right_y})"
        )


class GlyphData:
    """A glyph data record from the ``glyf`` table.

    Mirrors ``org.apache.fontbox.ttf.GlyphData`` at the public-method
    level. Internally the glyph itself is parsed by ``fontTools`` —
    glyph outlines, composite resolution, contour decoding, etc., are
    exactly what fontTools' ``_g_l_y_f`` table does, so we wrap it
    instead of porting ``GlyfDescript`` / ``GlyfSimpleDescript`` /
    ``GlyfCompositeDescript`` / ``GlyphRenderer`` from upstream.

    Instances are constructed by :class:`GlyphTable.get_glyph` rather
    than by callers.
    """

    def __init__(
        self,
        glyf_table: Any | None = None,
        glyph_name: str | None = None,
        units_per_em: int = 1000,
    ) -> None:
        # Lazy fontTools resolution: we hold the parent ``glyf`` table
        # plus the glyph's name (fontTools keys glyphs by name, not GID),
        # then materialise the bounding box / path on first access.
        self._glyf_table = glyf_table
        self._glyph_name = glyph_name
        self._units_per_em = int(units_per_em)
        self._x_min: int = 0
        self._y_min: int = 0
        self._x_max: int = 0
        self._y_max: int = 0
        self._number_of_contours: int = 0
        self._bounding_box: BoundingBox | None = None
        self._initialised: bool = False
        self._empty: bool = glyf_table is None or glyph_name is None

    # ---- internal initialisation ----

    def _ensure_initialised(self) -> None:
        if self._initialised:
            return
        self._initialised = True
        if self._empty:
            self._bounding_box = BoundingBox()
            return
        # fontTools ``_g_l_y_f`` indexes by glyph name. The Glyph object
        # exposes ``xMin``, ``yMin``, ``xMax``, ``yMax`` and
        # ``numberOfContours`` once it has been expanded; for lazy fonts
        # the recalc helpers force expansion as a side effect.
        glyph = self._glyf_table[self._glyph_name]
        # Empty / no-outline glyphs (.notdef-style or whitespace) carry
        # numberOfContours == 0 with no min/max attrs — guard accordingly.
        n_contours = int(getattr(glyph, "numberOfContours", 0))
        self._number_of_contours = n_contours
        x_min = getattr(glyph, "xMin", None)
        if x_min is None:
            # No outline: bbox is degenerate, matches upstream's
            # ``initEmptyData`` zero-rect fallback.
            self._x_min = self._y_min = self._x_max = self._y_max = 0
            self._bounding_box = BoundingBox()
            return
        self._x_min = int(glyph.xMin)
        self._y_min = int(glyph.yMin)
        self._x_max = int(glyph.xMax)
        self._y_max = int(glyph.yMax)
        self._bounding_box = BoundingBox(
            self._x_min, self._y_min, self._x_max, self._y_max
        )

    # ---- accessors mirroring upstream surface ----

    def get_bounding_box(self) -> BoundingBox:
        self._ensure_initialised()
        # ``_ensure_initialised`` always sets ``_bounding_box``.
        assert self._bounding_box is not None
        return self._bounding_box

    def get_number_of_contours(self) -> int:
        self._ensure_initialised()
        return self._number_of_contours

    def get_x_minimum(self) -> int:
        self._ensure_initialised()
        return self._x_min

    def get_x_maximum(self) -> int:
        self._ensure_initialised()
        return self._x_max

    def get_y_minimum(self) -> int:
        self._ensure_initialised()
        return self._y_min

    def get_y_maximum(self) -> int:
        self._ensure_initialised()
        return self._y_max

    def get_path(self) -> RecordingPen:
        """Return a recorded outline of this glyph.

        Upstream returns a ``java.awt.geom.GeneralPath`` driven by
        ``GlyphRenderer``. The Python port hands back fontTools'
        ``RecordingPen`` — its ``value`` attribute is a list of
        ``(operator, args)`` tuples (``moveTo`` / ``lineTo`` /
        ``qCurveTo`` / ``curveTo`` / ``closePath``) describing the same
        contour, which callers can replay onto any other pen (a Skia
        canvas, reportlab path, etc.).

        For empty / no-outline glyphs the returned pen has an empty
        ``value`` list.
        """
        from fontTools.pens.recordingPen import RecordingPen  # noqa: PLC0415

        pen = RecordingPen()
        if self._empty or self._glyf_table is None or self._glyph_name is None:
            return pen
        glyph = self._glyf_table[self._glyph_name]
        # ``Glyph.draw`` needs the full ``glyf`` table so it can resolve
        # composite component references back to their base glyphs.
        glyph.draw(pen, self._glyf_table)
        return pen


__all__ = ["BoundingBox", "GlyphData"]
