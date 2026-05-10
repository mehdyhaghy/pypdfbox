"""Tests for :class:`pypdfbox.fontbox.ttf.glyf_composite_descript.GlyfCompositeDescript`.

Also includes the ported upstream JUnit test from
``GlyfCompositeDescriptTest.java`` (PDFBox 3.0.x).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont
from pypdfbox.fontbox.ttf.glyf_composite_comp import GlyfCompositeComp
from pypdfbox.fontbox.ttf.glyf_composite_descript import GlyfCompositeDescript
from pypdfbox.fontbox.ttf.glyf_descript import GlyfDescript
from pypdfbox.fontbox.ttf.glyf_simple_descript import GlyfSimpleDescript

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_sans() -> TrueTypeFont:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return TrueTypeFont.from_bytes(FIXTURE.read_bytes())


def test_default_construction_is_composite() -> None:
    d = GlyfCompositeDescript()
    assert d.is_composite() is True
    # contourCount is -1 initially (Java ``super((short) -1)``), so the
    # base accessor reports -1 until resolution; the resolved getter
    # returns 0 with no components.
    assert d.get_contour_count() == 0
    assert d.get_point_count() == 0
    assert d.get_component_count() == 0
    assert d.get_components() == ()


def test_resolve_with_one_simple_subglyph() -> None:
    """Manually wire a composite with a single simple subglyph and resolve."""
    composite = GlyfCompositeDescript()

    # Single component pointing at sub-glyph 1 with no transform.
    comp = GlyfCompositeComp()
    comp._glyph_index = 1
    comp._flags = GlyfCompositeComp.ARGS_ARE_XY_VALUES
    composite._components.append(comp)

    # Sub-glyph: 3-point single-contour shape backed by a hand-made
    # simple descript.
    sub = GlyfSimpleDescript()
    sub._contour_count = 1
    sub._end_pts_of_contours = [2]
    sub._flags = [GlyfDescript.ON_CURVE, GlyfDescript.ON_CURVE, GlyfDescript.ON_CURVE]
    sub._x_coordinates = [0, 10, 5]
    sub._y_coordinates = [0, 0, 10]
    sub._point_count = 3
    composite._descriptions[1] = sub

    composite.resolve()

    # firstIndex/firstContour assigned, point/contour counts reflect sub.
    assert composite._components[0].get_first_index() == 0
    assert composite._components[0].get_first_contour() == 0
    assert composite.get_point_count() == 3
    assert composite.get_contour_count() == 1

    # Coordinates pass through the identity transform.
    for i in range(3):
        assert composite.get_x_coordinate(i) == sub.get_x_coordinate(i)
        assert composite.get_y_coordinate(i) == sub.get_y_coordinate(i)
        assert composite.get_flags(i) == GlyfDescript.ON_CURVE
    assert composite.get_end_pt_of_contours(0) == 2


def test_resolve_with_translation() -> None:
    composite = GlyfCompositeDescript()
    comp = GlyfCompositeComp()
    comp._glyph_index = 1
    comp._flags = GlyfCompositeComp.ARGS_ARE_XY_VALUES
    comp._xtranslate = 100
    comp._ytranslate = -50
    composite._components.append(comp)

    sub = GlyfSimpleDescript()
    sub._contour_count = 1
    sub._end_pts_of_contours = [0]
    sub._flags = [GlyfDescript.ON_CURVE]
    sub._x_coordinates = [10]
    sub._y_coordinates = [20]
    sub._point_count = 1
    composite._descriptions[1] = sub

    composite.resolve()

    # x' = round(10*1 + 20*0) + 100 = 110, y' = round(10*0 + 20*1) + -50 = -30
    assert composite.get_x_coordinate(0) == 110
    assert composite.get_y_coordinate(0) == -30


def test_circular_reference_does_not_infinite_loop(caplog) -> None:
    # Set the being-resolved flag manually and call resolve(): it
    # should short-circuit via the error log (upstream lines 93-96).
    composite = GlyfCompositeDescript()
    composite._being_resolved = True
    composite.resolve()
    # Still not marked resolved.
    assert composite._resolved is False


def test_get_components_returns_immutable_view() -> None:
    """Ported from upstream GlyfCompositeDescriptTest.getComponentsView."""
    composite = GlyfCompositeDescript()
    composite._components.append(GlyfCompositeComp())
    composite._components.append(GlyfCompositeComp())
    view = composite.get_components()
    assert len(view) == 2
    # Tuples don't have ``.remove``; mutation attempts raise.
    with pytest.raises(AttributeError):
        view.remove(view[0])  # type: ignore[attr-defined]


def test_get_components_real_font(liberation_sans: TrueTypeFont) -> None:
    """Liberation Sans 'A acute' (or any composite) parity check.

    Mirrors the spirit of upstream
    ``GlyfCompositeDescriptTest.getComponentsView`` (line 39) which
    opens LiberationSans-Regular.ttf and inspects a known composite
    glyph. We don't pin a specific glyph id since fontTools may key
    differently, just walk the table looking for a composite.
    """
    glyf = liberation_sans._tt["glyf"]
    composite_name = next(
        (n for n in glyf.glyphs if glyf[n].isComposite()),
        None,
    )
    if composite_name is None:
        pytest.skip("font has no composite glyphs")
    glyph = glyf[composite_name]
    # Build descript via the library-first adapter.
    descript = GlyfCompositeDescript.from_glyph(
        glyph,
        glyf,
        description_for_index=lambda _i: None,
    )
    assert descript.is_composite() is True
    assert descript.get_component_count() >= 1
