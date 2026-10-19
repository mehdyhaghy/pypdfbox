"""Port of upstream ``GraphicsStateTest``: defaults, deep copy and per-glyph reset.

A shallow copy would let a glyph write through to the saved post-``prep``
template, and resetting too much or too little would discard or retain state
the TrueType spec is specific about.
"""

from pypdfbox.fontbox.ttf.fixed import Fixed
from pypdfbox.fontbox.ttf.graphics_state import GraphicsState
from pypdfbox.fontbox.ttf.unit_vector import UnitVector


def test_defaults():
    gs = GraphicsState()
    assert gs.get_projection_vector() == UnitVector.x_axis()
    assert gs.get_freedom_vector() == UnitVector.x_axis()
    assert gs.get_round_state() == GraphicsState.ROUND_TO_GRID
    assert gs.get_loop() == 1
    assert gs.get_minimum_distance() == Fixed.ONE
    assert gs.get_control_value_cut_in() == 17 * Fixed.ONE // 16
    assert gs.get_delta_base() == 9
    assert gs.get_delta_shift() == 3
    assert gs.get_zp0() == 1
    assert gs.get_rp0() == 0
    assert gs.is_auto_flip()


def test_deep_copy_is_independent():
    original = GraphicsState()
    clone = original.copy()

    # the vector objects must not be shared
    assert original.get_freedom_vector() is not clone.get_freedom_vector()

    # mutating the clone's vector in place must not touch the original
    clone.get_freedom_vector().set(0, Fixed.ONE_F2DOT14)
    clone.set_rp0(5)
    clone.set_round_state(GraphicsState.ROUND_OFF)

    assert original.get_freedom_vector() == UnitVector.x_axis()
    assert original.get_rp0() == 0
    assert original.get_round_state() == GraphicsState.ROUND_TO_GRID


def test_reset_for_glyph_resets_only_spec_mandated_fields():
    gs = GraphicsState()

    # simulate state left behind by prep / a previous glyph
    gs.get_freedom_vector().set(0, Fixed.ONE_F2DOT14)
    gs.get_projection_vector().set(0, Fixed.ONE_F2DOT14)
    gs.set_rp0(3)
    gs.set_rp1(4)
    gs.set_rp2(5)
    gs.set_zp0(0)
    gs.set_loop(7)
    # prep-configured fields that must survive a per-glyph reset
    gs.set_round_state(GraphicsState.ROUND_OFF)
    gs.set_control_value_cut_in(999)
    gs.set_minimum_distance(123)
    gs.set_delta_base(42)

    gs.reset_for_glyph()

    # reset to defaults
    assert gs.get_freedom_vector() == UnitVector.x_axis()
    assert gs.get_projection_vector() == UnitVector.x_axis()
    assert gs.get_rp0() == 0
    assert gs.get_rp1() == 0
    assert gs.get_rp2() == 0
    assert gs.get_zp0() == 1
    assert gs.get_loop() == 1

    # preserved from prep
    assert gs.get_round_state() == GraphicsState.ROUND_OFF
    assert gs.get_control_value_cut_in() == 999
    assert gs.get_minimum_distance() == 123
    assert gs.get_delta_base() == 42
