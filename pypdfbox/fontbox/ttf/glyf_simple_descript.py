"""Simple-glyph description for the ``glyf`` table.

Mirrors ``org.apache.fontbox.ttf.GlyfSimpleDescript`` (GlyfSimpleDescript.java
lines 27-228). Upstream parses the on-disk flag / coordinate arrays
directly from a ``TTFDataStream``. pypdfbox's primary parser path goes
through fontTools, but this ported class is still useful for callers
that already hold a ``TTFDataStream`` cursor positioned at a simple
glyph record (e.g. subsetter tooling, format probes) and want the
same point-decode loop as upstream.

The class can be constructed two ways:

* Empty no-arg form — mirrors upstream's ``GlyfSimpleDescript()`` no-op
  constructor (line 44), producing a zero-point description.
* Stream form — ``GlyfSimpleDescript(number_of_contours, bais, x0)`` —
  reads end-points, instructions, flags, and coordinates from ``bais``
  using the upstream layout.

A third "from fontTools" classmethod, :meth:`from_glyph`, wraps an
already-decoded fontTools glyph so callers can obtain the same
accessor surface without re-parsing the bytes themselves. This keeps
us aligned with the "library-first" policy in CLAUDE.md while still
exposing the upstream-named API.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .glyf_descript import GlyfDescript

if TYPE_CHECKING:
    from .ttf_data_stream import TTFDataStream


_LOG = logging.getLogger(__name__)


class GlyfSimpleDescript(GlyfDescript):
    """Simple (non-composite) glyph description."""

    def __init__(
        self,
        number_of_contours: int = 0,
        bais: TTFDataStream | None = None,
        x0: int = 0,
    ) -> None:
        super().__init__(number_of_contours)
        self._end_pts_of_contours: list[int] = []
        self._flags: list[int] = []
        self._x_coordinates: list[int] = []
        self._y_coordinates: list[int] = []
        self._point_count: int = 0

        if bais is None or number_of_contours == 0:
            # Upstream's "empty description" early-return path (lines
            # 44-48 + 67-71).
            return

        # Mirror the upstream parse — read endpoints, then handle
        # PDFBOX-2939's "empty single-contour" sentinel, then flags and
        # coordinates.
        self._end_pts_of_contours = bais.read_unsigned_short_array(
            number_of_contours
        )
        last_end_pt = self._end_pts_of_contours[number_of_contours - 1]
        if number_of_contours == 1 and last_end_pt == 65535:
            # PDFBOX-2939: empty glyph encoded as one contour ending at
            # 0xFFFF (line 77).
            self._point_count = 0
            return

        # Upstream: ``pointCount = lastEndPt + 1;`` (line 84)
        self._point_count = last_end_pt + 1
        self._flags = [0] * self._point_count
        self._x_coordinates = [0] * self._point_count
        self._y_coordinates = [0] * self._point_count

        instruction_count = bais.read_unsigned_short()
        self.read_instructions(bais, instruction_count)
        self.read_flags(self._point_count, bais)
        self.read_coords(self._point_count, bais, x0)

    # ---- upstream accessors ------------------------------------------

    def get_end_pt_of_contours(self, i: int) -> int:
        # Mirrors upstream ``getEndPtOfContours(int)`` (line 100).
        return int(self._end_pts_of_contours[i])

    def get_flags(self, i: int) -> int:
        # Mirrors upstream ``getFlags(int)`` (line 109).
        return int(self._flags[i])

    def get_x_coordinate(self, i: int) -> int:
        # Mirrors upstream ``getXCoordinate(int)`` (line 118).
        return int(self._x_coordinates[i])

    def get_y_coordinate(self, i: int) -> int:
        # Mirrors upstream ``getYCoordinate(int)`` (line 127).
        return int(self._y_coordinates[i])

    def is_composite(self) -> bool:
        # Mirrors upstream ``isComposite()`` (line 136).
        return False

    def get_point_count(self) -> int:
        # Mirrors upstream ``getPointCount()`` (line 145).
        return self._point_count

    # ---- private decode helpers --------------------------------------

    def read_coords(self, count: int, bais: TTFDataStream, x0: int) -> None:
        """Decode the relative x / y coordinate deltas into absolutes.

        Mirrors upstream ``readCoords(int, TTFDataStream, short)`` (line
        153). The stream encodes deltas, the in-memory arrays hold
        absolutes.
        """
        x = int(x0)
        for i in range(count):
            flag = self._flags[i]
            if (flag & GlyfDescript.X_DUAL) != 0:
                if (flag & GlyfDescript.X_SHORT_VECTOR) != 0:
                    x += bais.read_unsigned_byte()
            else:
                if (flag & GlyfDescript.X_SHORT_VECTOR) != 0:
                    x -= bais.read_unsigned_byte()
                else:
                    x += bais.read_signed_short()
            # Keep the absolute coordinate in signed-16 range to match
            # upstream's ``short`` storage.
            self._x_coordinates[i] = _to_signed_short(x)

        y = 0
        for i in range(count):
            flag = self._flags[i]
            if (flag & GlyfDescript.Y_DUAL) != 0:
                if (flag & GlyfDescript.Y_SHORT_VECTOR) != 0:
                    y += bais.read_unsigned_byte()
            else:
                if (flag & GlyfDescript.Y_SHORT_VECTOR) != 0:
                    y -= bais.read_unsigned_byte()
                else:
                    y += bais.read_signed_short()
            self._y_coordinates[i] = _to_signed_short(y)

    def read_flags(self, flag_count: int, bais: TTFDataStream) -> None:
        """Decode the run-length-encoded flag stream.

        Mirrors upstream ``readFlags(int, TTFDataStream)`` (line 207).
        """
        index = 0
        while index < flag_count:
            self._flags[index] = bais.read_unsigned_byte() & 0xFF
            if (self._flags[index] & GlyfDescript.REPEAT) != 0:
                repeats = bais.read_unsigned_byte()
                for i in range(1, repeats + 1):
                    if index + i >= len(self._flags):
                        # Upstream throws IOException; we mirror that with
                        # OSError per CLAUDE.md conventions.
                        raise OSError(
                            f"repeat count ({repeats}) higher than remaining space"
                        )
                    self._flags[index + i] = self._flags[index]
                index += repeats
            index += 1

    # ---- library-first adapter ---------------------------------------

    @classmethod
    def from_glyph(cls, glyph: Any, glyf_table: Any | None = None) -> GlyfSimpleDescript:
        """Wrap a fontTools-parsed simple glyph.

        Useful when the surrounding pipeline has already decoded the
        ``glyf`` table via fontTools and just needs the upstream
        descript API on top of those arrays. Composite glyphs should
        use :class:`GlyfCompositeDescript` instead.
        """
        n = int(getattr(glyph, "numberOfContours", 0))
        if n < 0:
            raise ValueError(
                "GlyfSimpleDescript.from_glyph requires a non-composite glyph"
            )
        descript = cls()
        descript._contour_count = n
        if n == 0:
            return descript
        # ``getCoordinates`` returns (GlyphCoordinates, end_pts, flags).
        coords, end_pts, flags = glyph.getCoordinates(glyf_table)
        descript._end_pts_of_contours = [int(e) for e in end_pts]
        descript._flags = [int(f) for f in flags]
        descript._x_coordinates = [int(p[0]) for p in coords]
        descript._y_coordinates = [int(p[1]) for p in coords]
        descript._point_count = len(coords)
        program = getattr(glyph, "program", None)
        if program is not None:
            # fontTools stores instructions as an assembled byte list on
            # ``program.bytecode``; surface that as the upstream-style
            # int array when present.
            bytecode = getattr(program, "bytecode", None)
            if bytecode is not None:
                descript._instructions = list(bytecode)
        return descript


def _to_signed_short(value: int) -> int:
    """Clamp / wrap ``value`` into the signed-16 range like Java ``short``."""
    value &= 0xFFFF
    if value & 0x8000:
        return value - 0x10000
    return value


__all__ = ["GlyfSimpleDescript"]
