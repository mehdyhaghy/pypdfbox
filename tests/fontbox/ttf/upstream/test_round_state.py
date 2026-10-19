"""Port of upstream ``RoundStateTest``: the ``GraphicsState.round`` state machine."""

import pytest

from pypdfbox.fontbox.ttf.graphics_state import GraphicsState


def _round(state, distance):
    gs = GraphicsState()
    gs.set_round_state(state)
    return gs.round(distance)


def test_round_to_grid():
    assert _round(GraphicsState.ROUND_TO_GRID, 100) == 128  # 1.56px -> 2px
    assert _round(GraphicsState.ROUND_TO_GRID, 95) == 64  # 1.48px -> 1px
    assert _round(GraphicsState.ROUND_TO_GRID, 96) == 128  # 1.5px rounds up
    assert _round(GraphicsState.ROUND_TO_GRID, -100) == -128


def test_round_down_and_up():
    assert _round(GraphicsState.ROUND_DOWN_TO_GRID, 100) == 64
    assert _round(GraphicsState.ROUND_DOWN_TO_GRID, 127) == 64
    assert _round(GraphicsState.ROUND_UP_TO_GRID, 65) == 128
    assert _round(GraphicsState.ROUND_UP_TO_GRID, 64) == 64


def test_round_off():
    assert _round(GraphicsState.ROUND_OFF, 100) == 100
    assert _round(GraphicsState.ROUND_OFF, -37) == -37


def test_round_to_double_grid():
    # double grid snaps to multiples of half a pixel (32)
    assert _round(GraphicsState.ROUND_TO_DOUBLE_GRID, 80) == 96  # 1.25px -> 1.5px
    assert _round(GraphicsState.ROUND_TO_DOUBLE_GRID, 70) == 64  # 1.09px -> 1.0px


def test_round_to_half_grid():
    # half grid snaps to (n + 0.5) pixels, i.e. 32, 96, 160, ...
    assert _round(GraphicsState.ROUND_TO_HALF_GRID, 100) == 96  # -> 1.5px
    assert _round(GraphicsState.ROUND_TO_HALF_GRID, 50) == 32  # -> 0.5px


def test_super_round_reduces_to_grid():
    # SROUND with period=1px, phase=0, threshold=half is equivalent to round-to-grid
    gs = GraphicsState()
    gs.set_super_round(0x4000, 0x48)  # 01 period=1.0, 00 phase=0, 1000 threshold=4*p/8=half
    assert gs.round(100) == 128
    assert gs.round(95) == 64


def test_negative_distances_mirror_free_type():
    # a negative distance is rounded as -round(-d), and a result that would cross zero is clamped
    # to zero (or to the phase for half-grid). Stems measured right-to-left produce negative
    # distances, so this is not an edge case.
    assert _round(GraphicsState.ROUND_TO_GRID, -95) == -64
    assert _round(GraphicsState.ROUND_TO_GRID, -96) == -128
    assert _round(GraphicsState.ROUND_TO_GRID, -31) == 0
    assert _round(GraphicsState.ROUND_DOWN_TO_GRID, -127) == -64  # toward zero
    assert _round(GraphicsState.ROUND_DOWN_TO_GRID, -63) == 0
    assert _round(GraphicsState.ROUND_UP_TO_GRID, -65) == -128  # away from zero
    assert _round(GraphicsState.ROUND_UP_TO_GRID, -1) == -64
    assert _round(GraphicsState.ROUND_TO_DOUBLE_GRID, -80) == -96
    assert _round(GraphicsState.ROUND_TO_DOUBLE_GRID, -70) == -64
    assert _round(GraphicsState.ROUND_TO_DOUBLE_GRID, -20) == -32
    assert _round(GraphicsState.ROUND_TO_HALF_GRID, -100) == -96
    assert _round(GraphicsState.ROUND_TO_HALF_GRID, -50) == -32
    assert _round(GraphicsState.ROUND_TO_HALF_GRID, -1) == -32  # floor(1)+32, negated


@pytest.mark.parametrize(
    "state",
    [
        GraphicsState.ROUND_TO_GRID,
        GraphicsState.ROUND_DOWN_TO_GRID,
        GraphicsState.ROUND_UP_TO_GRID,
        GraphicsState.ROUND_TO_DOUBLE_GRID,
    ],
)
def test_grid_values_are_fixed_points(state):
    assert _round(state, 0) == 0
    assert _round(state, 128) == 128
    assert _round(state, -128) == -128


def test_grid_values_half_grid():
    assert _round(GraphicsState.ROUND_TO_HALF_GRID, 0) == 32
    assert _round(GraphicsState.ROUND_TO_HALF_GRID, 64) == 96


def test_super_round45_parameters():
    # S45ROUND parameters are derived in F2Dot14 and shifted, as FreeType does: with the diagonal
    # period 0x2D41 the "period - 1" threshold is (0x2D41 - 1) >> 8 = 45, not (45 - 1) = 44.
    gs = GraphicsState()
    gs.set_super_round(0x2D41, 0x40)  # period = diagonal, phase 0, threshold = period - 1
    # period 45, threshold 45: any positive distance rounds up to the next multiple of 45
    assert gs.round(1) == 45
    assert gs.round(46) == 90
    assert gs.round(-1) == -45

    gs.set_super_round(0x2D41, 0x58)  # period = diagonal, phase = period/4 = 11, threshold = half
    assert gs.round(0) == 11
    assert gs.round(40) == 56  # 45 + 11
