"""Abstract base for glyph descriptions in the ``glyf`` table.

Mirrors ``org.apache.fontbox.ttf.GlyfDescript`` (GlyfDescript.java
lines 26-116). pypdfbox's parser path uses fontTools for raw byte
decoding, but the upstream class also publishes a small public
surface — outline-flag constants plus a handful of accessors — that
ported descript subclasses share, so we keep that surface here.

Subclasses :class:`GlyfSimpleDescript` and
:class:`GlyfCompositeDescript` extend this base and add their own
point / contour storage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ttf_data_stream import TTFDataStream


class GlyfDescript:
    """Common state for simple and composite glyph descriptions.

    Holds the contour count and (lazily) the TrueType hinting
    instruction byte sequence. Subclasses override the point / flag
    accessors.
    """

    # Outline-flag bits, see "Outline flags" in
    # https://developer.apple.com/fonts/TrueType-Reference-Manual/RM06/Chap6glyf.html
    #: If set, the point is on the curve.
    ON_CURVE: int = 0x01
    #: If set, the x-coordinate is 1 byte long.
    X_SHORT_VECTOR: int = 0x02
    #: If set, the y-coordinate is 1 byte long.
    Y_SHORT_VECTOR: int = 0x04
    #: If set, the next byte specifies the number of additional times
    #: this set of flags is to be repeated.
    REPEAT: int = 0x08
    #: Sign / delta indicator for the x-coordinate (see upstream doc).
    X_DUAL: int = 0x10
    #: Sign / delta indicator for the y-coordinate (see upstream doc).
    Y_DUAL: int = 0x20

    def __init__(self, number_of_contours: int) -> None:
        # Upstream constructor (line 74) stores the contour count as an
        # int even though the parameter is a Java ``short``.
        self._contour_count = int(number_of_contours)
        self._instructions: list[int] | None = None

    def resolve(self) -> None:
        """Force-resolve any deferred decoding.

        Mirrors upstream ``GlyfDescript.resolve()`` (line 83) which is a
        no-op for the simple descript and gets overridden in the
        composite descript to flatten sub-components.
        """

    def get_contour_count(self) -> int:
        """Return the number of contours.

        Mirrors upstream ``getContourCount()`` (line 91).
        """
        return self._contour_count

    # Convenience aliases for the bbox / contour metadata that the
    # public ``GlyphData`` carrier already publishes — these are not
    # part of upstream's abstract class, but the parity task asks for
    # ``get_x_min`` / ``get_x_max`` etc. so callers that hold only a
    # descript handle can read them. Default to zero; subclasses /
    # callers may override after construction.
    def get_x_min(self) -> int:
        return 0

    def get_x_max(self) -> int:
        return 0

    def get_y_min(self) -> int:
        return 0

    def get_y_max(self) -> int:
        return 0

    # ---- abstract surface (overridden by subclasses) -------------

    def get_number_of_contours(self) -> int:
        """Alias of :meth:`get_contour_count` matching the parity prompt."""
        return self.get_contour_count()

    def is_composite(self) -> bool:
        """Return ``True`` for composite glyph descriptions.

        Mirrors upstream's abstract ``isComposite()`` (from the
        ``GlyphDescription`` interface — GlyphDescription.java line 65).
        Upstream declares it abstract; the base implementation here
        returns ``False`` because an "empty" :class:`GlyfDescript`
        (zero contours, no points, no instructions) is by definition a
        simple-glyph degenerate, not a composite. :class:`GlyfCompositeDescript`
        overrides to return ``True``.
        """
        return False

    def get_point_count(self) -> int:
        """Return the total number of points in the glyph outline.

        Mirrors upstream's abstract ``getPointCount()``
        (GlyphDescription.java line 71). The base implementation
        returns ``0`` — an empty descript has no points; concrete
        subclasses populate from their decoded point arrays.
        """
        return 0

    def get_end_pt_of_contours(self, i: int) -> int:  # noqa: ARG002
        """Return the end-point index of the *i*-th contour.

        Mirrors upstream's abstract ``getEndPtOfContours(int)``
        (GlyphDescription.java line 34). The base implementation
        returns ``-1`` to signal "no contour" — concrete subclasses
        index into their decoded contour array.
        """
        return -1

    def get_flags(self, i: int) -> int:  # noqa: ARG002
        """Return the outline flag byte for the *i*-th point.

        Mirrors upstream's abstract ``getFlags(int)``
        (GlyphDescription.java line 45). The base implementation
        returns ``0`` (no flags set); concrete subclasses index into
        their decoded flag array.
        """
        return 0

    def get_x_coordinate(self, i: int) -> int:  # noqa: ARG002
        """Return the x coordinate of the *i*-th point.

        Mirrors upstream's abstract ``getXCoordinate(int)``
        (GlyphDescription.java line 52). The base implementation
        returns ``0``; concrete subclasses index into their decoded
        x-coordinate array.
        """
        return 0

    def get_y_coordinate(self, i: int) -> int:  # noqa: ARG002
        """Return the y coordinate of the *i*-th point.

        Mirrors upstream's abstract ``getYCoordinate(int)``
        (GlyphDescription.java line 59). The base implementation
        returns ``0``; concrete subclasses index into their decoded
        y-coordinate array.
        """
        return 0

    # ---- instruction handling ----------------------------------------

    def get_instructions(self) -> list[int] | None:
        """Return the TrueType hinting instructions byte stream.

        Mirrors upstream ``getInstructions()`` (line 100). Returns
        ``None`` when no instructions have been read.
        """
        return self._instructions

    def read_instructions(self, bais: TTFDataStream, count: int) -> None:
        """Read ``count`` hinting instruction bytes from ``bais``.

        Mirrors upstream ``readInstructions(TTFDataStream, int)``
        (line 111). Defers to the data stream's
        ``read_unsigned_byte_array`` helper.
        """
        self._instructions = bais.read_unsigned_byte_array(count)


__all__ = ["GlyfDescript"]
