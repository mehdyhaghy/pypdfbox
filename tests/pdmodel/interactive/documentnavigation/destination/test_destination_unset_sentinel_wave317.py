from __future__ import annotations

from pypdfbox.cos import COSNull
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitRectangleDestination,
    PDPageFitWidthDestination,
    PDPageXYZDestination,
)


def test_wave317_xyz_unset_sentinel_writes_cos_null() -> None:
    dest = PDPageXYZDestination()

    dest.set_left(PDPageXYZDestination.UNSET)
    dest.set_top(-1)
    dest.set_zoom(-1.0)

    assert dest.get_left() is None
    assert dest.get_top() is None
    assert dest.get_zoom() is None
    assert dest.is_left_unset() is True
    assert dest.is_top_unset() is True
    assert dest.is_zoom_unset() is True
    assert dest.get_cos_array().get(2) is COSNull.NULL
    assert dest.get_cos_array().get(3) is COSNull.NULL
    assert dest.get_cos_array().get(4) is COSNull.NULL


def test_wave317_fit_width_unset_sentinel_writes_cos_null() -> None:
    dest = PDPageFitWidthDestination()
    dest.set_top(512.0)

    dest.set_top(-1)

    assert dest.get_top() is None
    assert dest.is_top_unset() is True
    assert dest.get_cos_array().get(2) is COSNull.NULL


def test_wave317_fit_rectangle_unset_sentinel_only_clears_matching_slots() -> None:
    dest = PDPageFitRectangleDestination()

    dest.set_rect(-1.0, 20.0, -1.0, 40.0)

    assert dest.get_rect() == (None, 20.0, None, 40.0)
    assert dest.is_complete() is False
    assert dest.get_cos_array().get(2) is COSNull.NULL
    assert dest.get_cos_array().get(4) is COSNull.NULL
