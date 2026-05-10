"""Single composite-glyph component.

Mirrors ``org.apache.fontbox.ttf.GlyfCompositeComp`` (GlyfCompositeComp.java
lines 25-316). One :class:`GlyfCompositeComp` represents one entry in
the chain of components that make up a composite glyph: it carries the
sub-glyph index, the two argument words (point indices or x/y
translates), and the optional 1- to 4-element transformation matrix.

The class can be constructed either from a positioned
:class:`TTFDataStream` (mirroring upstream's package-private
constructor at line 88) or via :meth:`from_fonttools` for the
library-first path where fontTools has already decoded the component.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .ttf_data_stream import TTFDataStream


class GlyfCompositeComp:
    """One component of a composite glyph."""

    # Composite-component flag bits — values lifted verbatim from
    # GlyfCompositeComp.java lines 30-65.
    ARG_1_AND_2_ARE_WORDS: int = 0x0001
    ARGS_ARE_XY_VALUES: int = 0x0002
    ROUND_XY_TO_GRID: int = 0x0004
    WE_HAVE_A_SCALE: int = 0x0008
    MORE_COMPONENTS: int = 0x0020
    WE_HAVE_AN_X_AND_Y_SCALE: int = 0x0040
    WE_HAVE_A_TWO_BY_TWO: int = 0x0080
    WE_HAVE_INSTRUCTIONS: int = 0x0100
    USE_MY_METRICS: int = 0x0200

    def __init__(self, bais: TTFDataStream | None = None) -> None:
        # Defaults match upstream field initialisers (lines 67-80).
        self._first_index: int = 0
        self._first_contour: int = 0
        self._argument1: int = 0
        self._argument2: int = 0
        self._flags: int = 0
        self._glyph_index: int = 0
        self._xscale: float = 1.0
        self._yscale: float = 1.0
        self._scale01: float = 0.0
        self._scale10: float = 0.0
        self._xtranslate: int = 0
        self._ytranslate: int = 0
        self._point1: int = 0
        self._point2: int = 0

        if bais is not None:
            self._read(bais)

    # ---- decode ------------------------------------------------------

    def _read(self, bais: TTFDataStream) -> None:
        """Decode this component from ``bais``.

        Mirrors the upstream constructor body (GlyfCompositeComp.java
        lines 88-150).
        """
        self._flags = bais.read_signed_short()
        # ``number of glyph in a font is uint16`` (line 91).
        self._glyph_index = bais.read_unsigned_short()

        if (self._flags & GlyfCompositeComp.ARG_1_AND_2_ARE_WORDS) != 0:
            # 16-bit signed (or unsigned, depending on flag interpretation).
            self._argument1 = bais.read_signed_short()
            self._argument2 = bais.read_signed_short()
        else:
            self._argument1 = bais.read_signed_byte()
            self._argument2 = bais.read_signed_byte()

        if (self._flags & GlyfCompositeComp.ARGS_ARE_XY_VALUES) != 0:
            self._xtranslate = self._argument1
            self._ytranslate = self._argument2
        else:
            # Point-anchored case: upstream notes this is currently
            # unused but keeps the values around (line 117-125).
            self._point1 = self._argument1
            self._point2 = self._argument2

        if (self._flags & GlyfCompositeComp.WE_HAVE_A_SCALE) != 0:
            i = bais.read_signed_short()
            self._xscale = self._yscale = i / float(0x4000)
        elif (self._flags & GlyfCompositeComp.WE_HAVE_AN_X_AND_Y_SCALE) != 0:
            i = bais.read_signed_short()
            self._xscale = i / float(0x4000)
            i = bais.read_signed_short()
            self._yscale = i / float(0x4000)
        elif (self._flags & GlyfCompositeComp.WE_HAVE_A_TWO_BY_TWO) != 0:
            i = bais.read_signed_short()
            self._xscale = i / float(0x4000)
            i = bais.read_signed_short()
            self._scale01 = i / float(0x4000)
            i = bais.read_signed_short()
            self._scale10 = i / float(0x4000)
            i = bais.read_signed_short()
            self._yscale = i / float(0x4000)

    # ---- upstream accessors ------------------------------------------

    def set_first_index(self, idx: int) -> None:
        # Mirrors upstream ``setFirstIndex`` (line 158).
        self._first_index = int(idx)

    def get_first_index(self) -> int:
        # Mirrors upstream ``getFirstIndex`` (line 168).
        return self._first_index

    def set_first_contour(self, idx: int) -> None:
        # Mirrors upstream ``setFirstContour`` (line 178).
        self._first_contour = int(idx)

    def get_first_contour(self) -> int:
        # Mirrors upstream ``getFirstContour`` (line 188).
        return self._first_contour

    def get_argument1(self) -> int:
        # Mirrors upstream ``getArgument1`` (line 198).
        return self._argument1

    def get_argument2(self) -> int:
        # Mirrors upstream ``getArgument2`` (line 208).
        return self._argument2

    def get_flags(self) -> int:
        # Mirrors upstream ``getFlags`` (line 218).
        return self._flags

    def get_glyph_index(self) -> int:
        # Mirrors upstream ``getGlyphIndex`` (line 228).
        return self._glyph_index

    def get_scale01(self) -> float:
        # Mirrors upstream ``getScale01`` (line 238).
        return self._scale01

    def get_scale10(self) -> float:
        # Mirrors upstream ``getScale10`` (line 248).
        return self._scale10

    def get_x_scale(self) -> float:
        # Mirrors upstream ``getXScale`` (line 258).
        return self._xscale

    def get_y_scale(self) -> float:
        # Mirrors upstream ``getYScale`` (line 268).
        return self._yscale

    def get_xy_scale01(self) -> float:
        """Convenience alias for the off-diagonal scale-01 value.

        Provided to satisfy the parity prompt's naming preference; the
        underlying value is identical to :meth:`get_scale01`.
        """
        return self._scale01

    def get_xy_scale10(self) -> float:
        """Convenience alias for the off-diagonal scale-10 value."""
        return self._scale10

    def get_x_translate(self) -> int:
        # Mirrors upstream ``getXTranslate`` (line 278).
        return self._xtranslate

    def get_y_translate(self) -> int:
        # Mirrors upstream ``getYTranslate`` (line 288).
        return self._ytranslate

    # ---- helper predicates -------------------------------------------

    def get_arg1(self) -> int:
        """Alias requested by the parity prompt; same as
        :meth:`get_argument1`."""
        return self._argument1

    def get_arg2(self) -> int:
        """Alias requested by the parity prompt; same as
        :meth:`get_argument2`."""
        return self._argument2

    def has_two_byte_args(self) -> bool:
        """True iff the component's two argument values were encoded as
        16-bit words rather than bytes.
        """
        return (self._flags & GlyfCompositeComp.ARG_1_AND_2_ARE_WORDS) != 0

    def has_word_arg_value(self) -> bool:
        """Alias of :meth:`has_two_byte_args` matching the parity prompt."""
        return self.has_two_byte_args()

    def has_scale(self) -> bool:
        """True iff this component carries a uniform scale."""
        return (self._flags & GlyfCompositeComp.WE_HAVE_A_SCALE) != 0

    def has_xy_scale(self) -> bool:
        """True iff this component carries separate x/y scales."""
        return (self._flags & GlyfCompositeComp.WE_HAVE_AN_X_AND_Y_SCALE) != 0

    def has_two_by_two(self) -> bool:
        """True iff this component carries a full 2x2 transform."""
        return (self._flags & GlyfCompositeComp.WE_HAVE_A_TWO_BY_TWO) != 0

    def more_components(self) -> bool:
        """True iff another component follows this one in the chain."""
        return (self._flags & GlyfCompositeComp.MORE_COMPONENTS) != 0

    def has_instructions(self) -> bool:
        """True iff the composite is followed by a hinting program."""
        return (self._flags & GlyfCompositeComp.WE_HAVE_INSTRUCTIONS) != 0

    def args_are_xy_values(self) -> bool:
        """True iff the two argument words encode x/y translates."""
        return (self._flags & GlyfCompositeComp.ARGS_ARE_XY_VALUES) != 0

    # ---- transforms --------------------------------------------------

    def scale_x(self, x: int, y: int) -> int:
        """Transform an x-coordinate through this component's matrix.

        Mirrors upstream ``scaleX(int, int)`` (line 300).
        """
        return _java_round(x * self._xscale + y * self._scale10)

    def scale_y(self, x: int, y: int) -> int:
        """Transform a y-coordinate through this component's matrix.

        Mirrors upstream ``scaleY(int, int)`` (line 312).
        """
        return _java_round(x * self._scale01 + y * self._yscale)

    # ---- library-first adapter ---------------------------------------

    @classmethod
    def from_fonttools(cls, component: Any) -> GlyfCompositeComp:
        """Build a :class:`GlyfCompositeComp` from a fontTools component.

        fontTools represents composite components as
        ``fontTools.ttLib.tables._g_l_y_f.GlyphComponent`` instances.
        This adapter copies the relevant fields onto a fresh
        :class:`GlyfCompositeComp` so the upstream API works over
        already-decoded glyphs.
        """
        comp = cls()
        comp._flags = int(getattr(component, "flags", 0))
        comp._glyph_index = int(
            getattr(component, "glyphID", getattr(component, "glyphIndex", 0))
        )
        # fontTools stores the transform / translate fields under
        # different attribute names depending on the component variant.
        x = int(getattr(component, "x", 0))
        y = int(getattr(component, "y", 0))
        if comp.args_are_xy_values():
            comp._xtranslate = x
            comp._ytranslate = y
            comp._argument1 = x
            comp._argument2 = y
        else:
            point1 = int(getattr(component, "firstPt", 0))
            point2 = int(getattr(component, "secondPt", 0))
            comp._point1 = point1
            comp._point2 = point2
            comp._argument1 = point1
            comp._argument2 = point2
        # Transform fields land on the component as four floats.
        if hasattr(component, "transform"):
            t = component.transform
            comp._xscale = float(t[0][0])
            comp._scale01 = float(t[0][1])
            comp._scale10 = float(t[1][0])
            comp._yscale = float(t[1][1])
        return comp


def _java_round(value: float) -> int:
    """Replicate ``Math.round((float) value)``: half-up for positives,
    half-down for negatives.
    """
    import math

    return math.floor(value + 0.5)


__all__ = ["GlyfCompositeComp"]
