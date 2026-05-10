"""Composite-glyph description.

Mirrors ``org.apache.fontbox.ttf.GlyfCompositeDescript`` (GlyfCompositeDescript.java
lines 37-314). A composite glyph is a chain of sub-components, each
referencing a base glyph by index plus a transform; the descript class
flattens that chain so callers can read points and contours
through the same accessor surface as :class:`GlyfSimpleDescript`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .glyf_composite_comp import GlyfCompositeComp
from .glyf_descript import GlyfDescript

if TYPE_CHECKING:
    from .ttf_data_stream import TTFDataStream


_LOG = logging.getLogger(__name__)


class GlyfCompositeDescript(GlyfDescript):
    """Composite glyph description.

    Holds a list of :class:`GlyfCompositeComp` plus a description map
    keyed by sub-glyph index. Construction requires either a
    ``TTFDataStream`` cursor at the composite record (matching upstream)
    or a fontTools-decoded glyph plus a callback that hands back the
    description of a sub-glyph by index.
    """

    def __init__(
        self,
        bais: TTFDataStream | None = None,
        glyph_table: Any | None = None,
        level: int = 0,
    ) -> None:
        # Upstream ``super((short) -1);`` (line 62) — composites encode
        # ``numberOfContours = -1`` on disk.
        super().__init__(-1)
        self._components: list[GlyfCompositeComp] = []
        self._descriptions: dict[int, Any] = {}
        self._glyph_table = glyph_table
        self._being_resolved: bool = False
        self._resolved: bool = False
        self._point_count: int = -1
        self._contour_count_resolved: int = -1

        if bais is None:
            return

        # Get all of the composite components (lines 67-73).
        comp: GlyfCompositeComp | None = None
        while True:
            comp = GlyfCompositeComp(bais)
            self._components.append(comp)
            if (comp.get_flags() & GlyfCompositeComp.MORE_COMPONENTS) == 0:
                break

        # Hinting instructions trailer (lines 76-79).
        assert comp is not None
        if (comp.get_flags() & GlyfCompositeComp.WE_HAVE_INSTRUCTIONS) != 0:
            count = bais.read_unsigned_short()
            self.read_instructions(bais, count)

        self.init_descriptions(level)

    # ---- resolution --------------------------------------------------

    def resolve(self) -> None:
        """Flatten sub-component point / contour offsets.

        Mirrors upstream ``resolve()`` (line 87).
        """
        if self._resolved:
            return
        if self._being_resolved:
            _LOG.error("Circular reference in GlyfCompositeDesc")
            return
        self._being_resolved = True

        first_index = 0
        first_contour = 0
        for comp in self._components:
            comp.set_first_index(first_index)
            comp.set_first_contour(first_contour)
            desc = self._descriptions.get(comp.get_glyph_index())
            if desc is not None:
                desc.resolve()
                first_index += desc.get_point_count()
                first_contour += desc.get_contour_count()

        self._resolved = True
        self._being_resolved = False

    def init_descriptions(self, level: int) -> None:
        """Pull each component's base glyph description from the parent
        glyph table.

        Mirrors upstream ``initDescriptions(int)`` (line 295).
        """
        if self._glyph_table is None:
            return
        for component in self._components:
            try:
                index = component.get_glyph_index()
                # Mirror upstream's two-arg ``getGlyph(int, int)`` when
                # available; fall back to one-arg for the ported
                # GlyphTable shim.
                get_glyph = getattr(self._glyph_table, "get_glyph", None)
                if get_glyph is None:
                    continue
                try:
                    glyph = get_glyph(index, level)
                except TypeError:
                    glyph = get_glyph(index)
                if glyph is not None:
                    self._descriptions[index] = glyph.get_description()
            except OSError as exc:  # noqa: PERF203
                _LOG.error("failed to load component description: %s", exc)

    # ---- accessors ---------------------------------------------------

    def get_end_pt_of_contours(self, i: int) -> int:
        # Mirrors upstream ``getEndPtOfContours(int)`` (line 124).
        c = self.get_composite_comp_end_pt(i)
        if c is not None:
            gd = self._descriptions.get(c.get_glyph_index())
            if gd is not None:
                return gd.get_end_pt_of_contours(i - c.get_first_contour()) + c.get_first_index()
        return 0

    def get_flags(self, i: int) -> int:
        # Mirrors upstream ``getFlags(int)`` (line 139).
        c = self.get_composite_comp(i)
        if c is not None:
            gd = self._descriptions.get(c.get_glyph_index())
            if gd is not None:
                return gd.get_flags(i - c.get_first_index())
        return 0

    def get_x_coordinate(self, i: int) -> int:
        # Mirrors upstream ``getXCoordinate(int)`` (line 154).
        c = self.get_composite_comp(i)
        if c is not None:
            gd = self._descriptions.get(c.get_glyph_index())
            if gd is not None:
                n = i - c.get_first_index()
                x = gd.get_x_coordinate(n)
                y = gd.get_y_coordinate(n)
                return _to_signed_short(c.scale_x(x, y) + c.get_x_translate())
        return 0

    def get_y_coordinate(self, i: int) -> int:
        # Mirrors upstream ``getYCoordinate(int)`` (line 172).
        c = self.get_composite_comp(i)
        if c is not None:
            gd = self._descriptions.get(c.get_glyph_index())
            if gd is not None:
                n = i - c.get_first_index()
                x = gd.get_x_coordinate(n)
                y = gd.get_y_coordinate(n)
                return _to_signed_short(c.scale_y(x, y) + c.get_y_translate())
        return 0

    def is_composite(self) -> bool:
        # Mirrors upstream ``isComposite()`` (line 190).
        return True

    def get_point_count(self) -> int:
        # Mirrors upstream ``getPointCount()`` (line 199).
        if not self._resolved:
            _LOG.error("get_point_count called on unresolved GlyfCompositeDescript")
        if self._point_count < 0:
            if not self._components:
                self._point_count = 0
            else:
                c = self._components[-1]
                gd = self._descriptions.get(c.get_glyph_index())
                if gd is None:
                    _LOG.error(
                        "GlyphDescription for index %d is null, returning 0",
                        c.get_glyph_index(),
                    )
                    self._point_count = 0
                else:
                    self._point_count = c.get_first_index() + gd.get_point_count()
        return self._point_count

    def get_contour_count(self) -> int:
        # Mirrors upstream ``getContourCount()`` (line 226).
        if not self._resolved:
            _LOG.error("get_contour_count called on unresolved GlyfCompositeDescript")
        if self._contour_count_resolved < 0:
            if not self._components:
                self._contour_count_resolved = 0
            else:
                c = self._components[-1]
                gd = self._descriptions.get(c.get_glyph_index())
                if gd is None:
                    _LOG.error(
                        "missing glyph description for index %d", c.get_glyph_index()
                    )
                    self._contour_count_resolved = 0
                else:
                    self._contour_count_resolved = (
                        c.get_first_contour() + gd.get_contour_count()
                    )
        return self._contour_count_resolved

    # ---- components view ---------------------------------------------

    def get_component_count(self) -> int:
        """Number of components in this composite glyph.

        Mirrors upstream ``getComponentCount()`` (line 254).
        """
        return len(self._components)

    def get_components(self) -> tuple[GlyfCompositeComp, ...]:
        """Immutable view onto the component list.

        Mirrors upstream ``getComponents()`` (line 264). Upstream
        returns ``Collections.unmodifiableList``; pypdfbox uses a tuple
        which raises ``TypeError`` on mutation attempts, matching the
        intent of the Java contract (the upstream test (line 62)
        asserts an ``UnsupportedOperationException`` on ``.remove(0)``).
        """
        return tuple(self._components)

    # ---- private lookup helpers --------------------------------------

    def get_composite_comp(self, i: int) -> GlyfCompositeComp | None:
        # Mirrors upstream ``getCompositeComp`` (line 269).
        for c in self._components:
            gd = self._descriptions.get(c.get_glyph_index())
            if (
                c.get_first_index() <= i
                and gd is not None
                and i < (c.get_first_index() + gd.get_point_count())
            ):
                return c
        return None

    def get_composite_comp_end_pt(self, i: int) -> GlyfCompositeComp | None:
        # Mirrors upstream ``getCompositeCompEndPt`` (line 282).
        for c in self._components:
            gd = self._descriptions.get(c.get_glyph_index())
            if (
                c.get_first_contour() <= i
                and gd is not None
                and i < (c.get_first_contour() + gd.get_contour_count())
            ):
                return c
        return None

    # ---- library-first adapter ---------------------------------------

    @classmethod
    def from_glyph(
        cls,
        glyph: Any,
        glyf_table: Any,
        description_for_index: Any,
    ) -> GlyfCompositeDescript:
        """Build a composite descript from a fontTools-decoded glyph.

        ``description_for_index`` is a callable that maps a sub-glyph
        index back to a :class:`GlyfDescript` (so this class can defer
        the glyph-table lookup to the caller).
        """
        if not glyph.isComposite():
            raise ValueError(
                "GlyfCompositeDescript.from_glyph requires a composite glyph"
            )
        descript = cls()
        components = getattr(glyph, "components", []) or []
        for component in components:
            descript._components.append(GlyfCompositeComp.from_fonttools(component))
        for comp in descript._components:
            sub = description_for_index(comp.get_glyph_index())
            if sub is not None:
                descript._descriptions[comp.get_glyph_index()] = sub
        return descript


def _to_signed_short(value: int) -> int:
    """Wrap ``value`` into the signed-16 range like Java ``(short)``."""
    value &= 0xFFFF
    if value & 0x8000:
        return value - 0x10000
    return value


__all__ = ["GlyfCompositeDescript"]
