"""Wave 1275 round-out: ``PDIndexed.set_high_value`` explicit method."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed


def test_set_high_value_round_trips_through_get_hival() -> None:
    cs = PDIndexed()
    cs.set_high_value(7)
    # Mirrors upstream ``PDIndexed.setHighValue`` (PDIndexed.java line
    # 330): writes the slot at array position 2.
    assert cs.get_hival() == 7


def test_set_high_value_clamps_via_get_hival_to_255() -> None:
    cs = PDIndexed()
    # No setter-side clamp — upstream's getter clamps on read.
    cs.set_high_value(1000)
    assert cs.get_hival() == 255


@pytest.mark.parametrize("value", [0, 1, 15, 64, 255])
def test_set_high_value_matches_set_hival(value: int) -> None:
    a = PDIndexed()
    b = PDIndexed()
    a.set_hival(value)
    b.set_high_value(value)
    assert a.get_hival() == b.get_hival()
