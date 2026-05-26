from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .glyf_descript import GlyfDescript

if TYPE_CHECKING:
    from fontTools.pens.recordingPen import RecordingPen  # type: ignore[import-untyped]


class GlyphDescription:
    """Adapter mirroring ``org.apache.fontbox.ttf.GlyphDescription``.

    Upstream ``GlyphDescription`` is the common interface implemented
    by ``GlyfSimpleDescript`` and ``GlyfCompositeDescript``. pypdfbox
    decodes glyph contours via fontTools, so this adapter wraps a
    fontTools ``Glyph`` and surfaces the same public queries —
    :meth:`is_composite`, :meth:`get_contour_count`,
    :meth:`get_point_count`, :meth:`get_end_pt_of_contours`,
    :meth:`get_x_coordinate`, :meth:`get_y_coordinate`,
    :meth:`get_flags`, :meth:`resolve` — without re-implementing the
    parser hierarchy.
    """

    def __init__(
        self, glyf_table: Any | None, glyph: Any | None, x_shift: int = 0
    ) -> None:
        self._glyf_table = glyf_table
        self._glyph = glyph
        # x-translation applied to every x-coordinate so this description
        # reports upstream-aligned (LSB-based) coordinates. See
        # :meth:`GlyphData._x_shift`. Zero for composites / missing metrics.
        self._x_shift = int(x_shift)
        # Lazy-decoded coordinate arrays; populated on first query.
        self._coords: Any | None = None
        self._end_pts: list[int] | None = None
        self._flags: Any | None = None

    def _ensure_decoded(self) -> None:
        if self._coords is not None:
            return
        if self._glyph is None or self._glyf_table is None:
            self._coords = []
            self._end_pts = []
            self._flags = b""
            return
        # ``getCoordinates`` resolves composite components against the
        # parent ``glyf`` table, matching upstream behaviour where a
        # composite description exposes the union of its parts' points.
        coords, end_pts, flags = self._glyph.getCoordinates(self._glyf_table)
        self._coords = coords
        self._end_pts = list(end_pts)
        self._flags = flags

    def is_composite(self) -> bool:
        if self._glyph is None:
            return False
        return bool(self._glyph.isComposite())

    def get_contour_count(self) -> int:
        if self._glyph is None:
            return 0
        n = int(getattr(self._glyph, "numberOfContours", 0))
        # Composite glyphs encode -1 in the file but conceptually have
        # the contour count of the resolved outline.
        if n < 0:
            self._ensure_decoded()
            assert self._end_pts is not None
            return len(self._end_pts)
        return n

    def get_point_count(self) -> int:
        self._ensure_decoded()
        assert self._coords is not None
        return len(self._coords)

    def get_end_pt_of_contours(self, i: int) -> int:
        self._ensure_decoded()
        assert self._end_pts is not None
        return int(self._end_pts[i])

    def get_x_coordinate(self, i: int) -> int:
        self._ensure_decoded()
        assert self._coords is not None
        return int(self._coords[i][0]) + self._x_shift

    def get_y_coordinate(self, i: int) -> int:
        self._ensure_decoded()
        assert self._coords is not None
        return int(self._coords[i][1])

    def get_flags(self, i: int) -> int:
        self._ensure_decoded()
        assert self._flags is not None
        return int(self._flags[i])

    def resolve(self) -> None:
        """Force-decode any deferred composite resolution.

        Mirrors upstream ``GlyphDescription.resolve()``. fontTools
        decodes lazily on first coordinate access, so this just
        triggers that decode.
        """
        self._ensure_decoded()


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
        min_x: float | list[float] | tuple[float, ...] = 0.0,
        min_y: float = 0.0,
        max_x: float = 0.0,
        max_y: float = 0.0,
    ) -> None:
        # Upstream offers an overloaded constructor
        # ``BoundingBox(List<Number>)``; mirror that by accepting a
        # 4-element sequence as the first positional argument.
        if isinstance(min_x, (list, tuple)):
            numbers = min_x
            if len(numbers) != 4:
                raise ValueError(
                    "BoundingBox sequence constructor requires 4 values, "
                    f"got {len(numbers)}"
                )
            self._lower_left_x = float(numbers[0])
            self._lower_left_y = float(numbers[1])
            self._upper_right_x = float(numbers[2])
            self._upper_right_y = float(numbers[3])
            return
        self._lower_left_x = float(min_x)
        self._lower_left_y = float(min_y)
        self._upper_right_x = float(max_x)
        self._upper_right_y = float(max_y)

    @classmethod
    def from_numbers(cls, numbers: list[float] | tuple[float, ...]) -> BoundingBox:
        """Mirror upstream ``BoundingBox(List<Number>)`` constructor.

        Accepts a 4-element sequence ``[minX, minY, maxX, maxY]``.
        """
        if len(numbers) != 4:
            raise ValueError(
                f"BoundingBox.from_numbers requires 4 values, got {len(numbers)}"
            )
        return cls(numbers[0], numbers[1], numbers[2], numbers[3])

    def is_empty(self) -> bool:
        """Return True iff this bounding box has zero area.

        Convenience predicate over upstream's getters: useful to detect
        the default-constructed ``BoundingBox()`` and degenerate boxes
        produced by glyphs with no outline (``.notdef`` empty slots).
        Returns True when ``getWidth()`` and ``getHeight()`` are both
        zero — matches the natural Java check ``bbox.getWidth() == 0
        && bbox.getHeight() == 0``.
        """
        return self.get_width() == 0.0 and self.get_height() == 0.0

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

    def contains(self, x: float, y: float) -> bool:
        """Return True if (x, y) is on the edge or inside the rectangle.

        Mirrors upstream ``BoundingBox.contains(float, float)``.
        """
        return (
            x >= self._lower_left_x
            and x <= self._upper_right_x
            and y >= self._lower_left_y
            and y <= self._upper_right_y
        )

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (
            self._lower_left_x,
            self._lower_left_y,
            self._upper_right_x,
            self._upper_right_y,
        )

    def to_string(self) -> str:
        """Mirror upstream ``BoundingBox.toString()``.

        Upstream format (Java lines 195-196):
        ``"[" + getLowerLeftX() + "," + getLowerLeftY() + "," +
        getUpperRightX() + "," + getUpperRightY() + "]"``.
        """
        return (
            f"[{self._lower_left_x},{self._lower_left_y},"
            f"{self._upper_right_x},{self._upper_right_y}]"
        )

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return (
            f"BoundingBox({self._lower_left_x}, {self._lower_left_y}, "
            f"{self._upper_right_x}, {self._upper_right_y})"
        )

    def __eq__(self, other: object) -> bool:
        # Upstream Java doesn't define equals/hashCode, but Python value
        # equality is the conventional behavior for plain data carriers
        # like this one and is required for tests/sets. Two instances
        # with the same four floats compare equal.
        if not isinstance(other, BoundingBox):
            return NotImplemented
        return (
            self._lower_left_x == other._lower_left_x
            and self._lower_left_y == other._lower_left_y
            and self._upper_right_x == other._upper_right_x
            and self._upper_right_y == other._upper_right_y
        )

    def __hash__(self) -> int:
        return hash(
            (
                self._lower_left_x,
                self._lower_left_y,
                self._upper_right_x,
                self._upper_right_y,
            )
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
        left_side_bearing: int | None = None,
    ) -> None:
        # Lazy fontTools resolution: we hold the parent ``glyf`` table
        # plus the glyph's name (fontTools keys glyphs by name, not GID),
        # then materialise the bounding box / path on first access.
        self._glyf_table = glyf_table
        self._glyph_name = glyph_name
        self._units_per_em = int(units_per_em)
        # Left-side bearing (hmtx). Upstream's ``GlyfSimpleDescript`` starts the
        # x-coordinate accumulator at the LSB instead of the glyf-stored xMin,
        # which is equivalent to shifting every simple-glyph x-coordinate by
        # ``(leftSideBearing - xMin)``. fontTools decodes the spec-correct
        # (xMin-aligned) coordinates, so we re-apply that shift on the path.
        # ``None`` means "no hmtx available" -> no shift (matches upstream
        # behaviour when the metric is missing).
        self._left_side_bearing = left_side_bearing
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
        assert self._glyf_table is not None
        assert self._glyph_name is not None
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

    def _x_shift(self) -> int:
        """The simple-glyph x-shift ``(leftSideBearing - xMin)``.

        Upstream ``GlyfSimpleDescript`` accumulates x starting at the LSB rather
        than the glyf-stored xMin (``GlyphTable.getGlyphData`` ->
        ``GlyphData.initData`` -> ``GlyfSimpleDescript(.., x0=leftSideBearing)``),
        which is equivalent to translating the whole simple outline by this
        amount in x. fontTools decodes xMin-aligned coordinates, so this shift
        recovers upstream's positioning.

        Returns 0 when there is no LSB metric, the glyph is empty, or the glyph
        is composite — upstream applies the LSB x0 only in the *simple*
        descript; the composite descript places its components by their own
        (recursively LSB-shifted) coordinates plus the component offsets.
        """
        if self._left_side_bearing is None or self._empty:
            return 0
        self._ensure_initialised()
        if self._number_of_contours < 0:
            # Composite glyph — no top-level LSB shift (see docstring).
            return 0
        return int(self._left_side_bearing) - int(self._x_min)

    def get_description(self) -> GlyphDescription:
        """Return a :class:`GlyphDescription` view of this glyph.

        Mirrors upstream ``GlyphData.getDescription()``. For empty /
        no-outline glyphs this is a description backed by a zero-point
        fontTools Glyph (matching upstream's ``initEmptyData`` path
        which constructs an empty ``GlyfSimpleDescript``).

        The returned description carries the simple-glyph x-shift (see
        :meth:`_x_shift`) so ``get_x_coordinate`` reports upstream-aligned
        coordinates.
        """
        if self._empty or self._glyf_table is None or self._glyph_name is None:
            return GlyphDescription(None, None)
        glyph = self._glyf_table[self._glyph_name]
        return GlyphDescription(self._glyf_table, glyph, x_shift=self._x_shift())

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
        return self.glyph_renderer().get_path()

    # ---- upstream package-private initialisers --------------------------

    def init_data(
        self,
        glyph_table: Any,
        data: Any,  # noqa: ARG002 - upstream signature parity
        left_side_bearing: int,  # noqa: ARG002 - upstream signature parity
        level: int,  # noqa: ARG002 - upstream signature parity
    ) -> None:
        """Bind this record to a parent ``glyf`` table and re-resolve.

        Mirrors upstream ``GlyphData.initData(GlyphTable, TTFDataStream,
        int, int)`` (GlyphData.java line 47). Upstream consumes the
        on-disk bytes via ``TTFDataStream`` and then dispatches to a
        simple- or composite-descript constructor based on
        ``numberOfContours``. pypdfbox decodes the ``glyf`` table via
        fontTools long before this method is called, so the ``data`` /
        ``leftSideBearing`` / ``level`` arguments are accepted for
        signature parity but ignored — re-binding the parent ``glyf``
        table is the substantive part. After ``init_data`` returns, the
        next accessor call materialises the bbox and contour count from
        fontTools as usual.

        Accepts either the ported :class:`GlyphTable` (whose internal
        ``_glyf_table`` we read) or a fontTools ``_g_l_y_f`` object
        directly, matching how callers pass parents in tests.
        """
        glyf = getattr(glyph_table, "_glyf_table", glyph_table)
        self._glyf_table = glyf
        self._empty = glyf is None or self._glyph_name is None
        # Force re-resolution on next accessor call.
        self._initialised = False
        self._bounding_box = None

    def init_empty_data(self) -> None:
        """Reset this record to an empty (no-outline) glyph.

        Mirrors upstream ``GlyphData.initEmptyData()`` (GlyphData.java
        line 75) which constructs an empty ``GlyfSimpleDescript`` and a
        zero-rect ``BoundingBox``. Accessors thereafter return zero for
        every dimension and an empty :class:`GlyphDescription`.
        """
        self._glyf_table = None
        self._glyph_name = None
        self._empty = True
        self._x_min = 0
        self._y_min = 0
        self._x_max = 0
        self._y_max = 0
        self._number_of_contours = 0
        self._bounding_box = BoundingBox()
        self._initialised = True

    # ---- renderer factory ------------------------------------------------

    def glyph_renderer(self) -> _GlyphRenderer:
        """Return a renderer that turns this glyph's description into a path.

        Mirrors the role of ``new GlyphRenderer(glyphDescription)`` in
        upstream's ``GlyphData.getPath()`` (GlyphData.java line 111).
        Upstream's ``GlyphRenderer`` is a package-private helper that
        walks ``GlyphDescription`` points and emits a Java
        ``GeneralPath``; pypdfbox delegates the same job to fontTools'
        ``RecordingPen`` driven by ``Glyph.draw`` and exposes a
        compatible ``get_path()`` accessor on the returned object.
        """
        return _GlyphRenderer(self)


class _GlyphRenderer:
    """Minimal port of upstream ``org.apache.fontbox.ttf.GlyphRenderer``.

    Upstream's renderer walks point arrays and builds a
    ``java.awt.geom.GeneralPath``. pypdfbox does the same job via
    fontTools' ``RecordingPen``, so this class is a thin adapter:
    construct it from a :class:`GlyphData` (or a :class:`GlyphDescription`
    plus its parent ``glyf`` table) and call :meth:`get_path` to obtain
    the recorded outline.
    """

    def __init__(self, glyph_data: GlyphData) -> None:
        self._glyph_data = glyph_data

    def get_path(self) -> RecordingPen:
        from fontTools.pens.recordingPen import RecordingPen  # noqa: PLC0415

        pen = RecordingPen()
        gd = self._glyph_data
        if gd._empty or gd._glyf_table is None or gd._glyph_name is None:
            return pen
        glyph = gd._glyf_table[gd._glyph_name]
        # ``Glyph.draw`` needs the full ``glyf`` table so it can resolve
        # composite component references back to their base glyphs.
        glyph.draw(pen, gd._glyf_table)
        # Re-apply upstream's simple-glyph x-shift (LSB-based positioning) so
        # this path matches ``GlyphData.get_description()`` / upstream
        # ``getPath()``. See :meth:`GlyphData._x_shift`.
        shift = gd._x_shift()
        if shift:
            pen.value = [
                (op, _shift_args(op, args, shift)) for op, args in pen.value
            ]
        return pen


def _shift_args(op: str, args: Any, shift: int) -> Any:
    """Translate the x-component of every point in a RecordingPen arg tuple.

    ``closePath`` / ``endPath`` carry no points (empty args). Points may be
    ``None`` (fontTools' all-off-curve TrueType marker), which we leave intact.
    """
    if not args:
        return args
    return tuple(
        None if pt is None else (pt[0] + shift, pt[1]) for pt in args
    )


__all__ = ["BoundingBox", "GlyfDescript", "GlyphData", "GlyphDescription"]
