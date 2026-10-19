"""Hand-written tests for ``Zone``: arrays are shared by reference and reset in place."""

import pytest

from pypdfbox.fontbox.ttf.zone import Zone


def test_arrays_are_live_references():
    zone = Zone(3, 1)
    assert zone.get_point_count() == 3
    zone.get_current_x()[1] = 42
    assert zone.get_current_x()[1] == 42
    assert len(zone.get_contour_ends()) == 1
    assert zone.get_touched_y() == [False, False, False]


def test_reset_clears_in_place():
    zone = Zone(2, 2)
    cx = zone.get_current_x()
    flags = zone.get_on_curve()
    ends = zone.get_contour_ends()
    cx[0] = 5
    zone.get_unscaled_y()[1] = 9
    flags[1] = True
    ends[1] = 1
    zone.reset()
    assert cx is zone.get_current_x()
    assert cx == [0, 0]
    assert zone.get_unscaled_y() == [0, 0]
    assert flags == [False, False]
    assert ends == [0, 0]


def test_negative_size_is_rejected():
    with pytest.raises(ValueError):
        Zone(-1, 0)
