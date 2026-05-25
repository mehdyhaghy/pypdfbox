"""Wave 1396 branch-coverage tests for ``GlyfCompositeDescript``.

Closes the False-branch arrows where an accessor walks the components
but the requested point/contour index falls outside every component's
slice and falls through to the ``return 0`` tail:

* 132->134 — ``get_end_pt_of_contours`` with no matching component
* 141->143 — ``get_flags`` with no matching component
* 150->155 — ``get_x_coordinate`` with no matching component
* 162->167 — ``get_y_coordinate`` with no matching component
* 240->238 / 252->250 — inner accessor predicates with a non-matching
  component (gd missing or index outside its range)
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp
from pypdfbox.fontbox.ttf.glyf_composite_descript import GlyfCompositeDescript


class _FakeSimpleDescript:
    """Minimal fake descript exposing the accessors a composite needs."""

    def __init__(self, point_count: int = 4, contour_count: int = 1) -> None:
        self._point_count = point_count
        self._contour_count = contour_count

    def resolve(self) -> None:
        return

    def get_point_count(self) -> int:
        return self._point_count

    def get_contour_count(self) -> int:
        return self._contour_count

    def get_end_pt_of_contours(self, i: int) -> int:
        return 0

    def get_flags(self, i: int) -> int:
        return 0

    def get_x_coordinate(self, i: int) -> int:
        return 0

    def get_y_coordinate(self, i: int) -> int:
        return 0


def _build_composite_with_one_component() -> GlyfCompositeDescript:
    """Build a 1-component composite whose sub-glyph 0 has 4 points / 1 contour."""
    desc = GlyfCompositeDescript()
    comp = GlyfCompositeComp.__new__(GlyfCompositeComp)
    # Wire only the fields we need (avoid the bytes-driven constructor).
    comp._flags = 0  # noqa: SLF001
    comp._glyph_index = 0  # noqa: SLF001
    comp._x_translate = 0  # noqa: SLF001
    comp._y_translate = 0  # noqa: SLF001
    comp._first_index = 0  # noqa: SLF001
    comp._first_contour = 0  # noqa: SLF001
    comp._scale01 = 0.0  # noqa: SLF001
    comp._scale10 = 0.0  # noqa: SLF001
    comp._xscale = 1.0  # noqa: SLF001
    comp._yscale = 1.0  # noqa: SLF001
    desc._components = [comp]  # noqa: SLF001
    desc._descriptions = {0: _FakeSimpleDescript(point_count=4, contour_count=1)}  # noqa: SLF001
    desc._resolved = True  # noqa: SLF001
    return desc


def test_get_end_pt_of_contours_returns_zero_when_no_matching_component() -> None:
    """Out-of-range contour index falls through to ``return 0``.

    Closes False arm of ``c is not None`` at line 132 in the
    ``get_composite_comp_end_pt`` flow.
    """
    desc = _build_composite_with_one_component()
    # Index 999 is way past the single contour — no match.
    assert desc.get_end_pt_of_contours(999) == 0


def test_get_flags_returns_zero_when_no_matching_component() -> None:
    """Out-of-range point index falls through to ``return 0``.

    Closes False arm at line 141.
    """
    desc = _build_composite_with_one_component()
    assert desc.get_flags(999) == 0


def test_get_x_coordinate_returns_zero_when_no_matching_component() -> None:
    """Out-of-range point index falls through to ``return 0``.

    Closes False arm at line 150.
    """
    desc = _build_composite_with_one_component()
    assert desc.get_x_coordinate(999) == 0


def test_get_y_coordinate_returns_zero_when_no_matching_component() -> None:
    """Out-of-range point index falls through to ``return 0``.

    Closes False arm at line 162.
    """
    desc = _build_composite_with_one_component()
    assert desc.get_y_coordinate(999) == 0


def test_get_composite_comp_skips_component_with_missing_description() -> None:
    """A component whose description is missing must be skipped.

    Closes False arm at line 240 (``gd is not None``).
    """
    desc = GlyfCompositeDescript()
    # Component points at glyph 42 — but no description registered.
    comp = GlyfCompositeComp.__new__(GlyfCompositeComp)
    comp._flags = 0  # noqa: SLF001
    comp._glyph_index = 42  # noqa: SLF001
    comp._first_index = 0  # noqa: SLF001
    comp._first_contour = 0  # noqa: SLF001
    desc._components = [comp]  # noqa: SLF001
    desc._descriptions = {}  # missing 42  # noqa: SLF001
    desc._resolved = True  # noqa: SLF001

    # get_composite_comp with i=0 — first_index<=0 is True but gd is None.
    assert desc.get_composite_comp(0) is None


def test_get_composite_comp_end_pt_skips_component_with_missing_description() -> None:
    """A component whose description is missing must be skipped for the
    contour variant too.

    Closes False arm at line 252 (``gd is not None``).
    """
    desc = GlyfCompositeDescript()
    comp = GlyfCompositeComp.__new__(GlyfCompositeComp)
    comp._flags = 0  # noqa: SLF001
    comp._glyph_index = 42  # noqa: SLF001
    comp._first_index = 0  # noqa: SLF001
    comp._first_contour = 0  # noqa: SLF001
    desc._components = [comp]  # noqa: SLF001
    desc._descriptions = {}  # noqa: SLF001
    desc._resolved = True  # noqa: SLF001
    assert desc.get_composite_comp_end_pt(0) is None
