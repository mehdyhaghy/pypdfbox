from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)


def test_set_line_rejects_non_four_coordinate_arrays_wave340() -> None:
    ann = PDAnnotationLine()
    original = ann.get_line()

    with pytest.raises(ValueError, match="/L must be a 4-element"):
        ann.set_line([1.0, 2.0, 3.0])

    assert ann.get_line() == original


def test_set_line_accepts_tuple_of_four_coordinates_wave340() -> None:
    ann = PDAnnotationLine()

    ann.set_line((1.0, 2.0, 3.0, 4.0))

    assert ann.get_line() == [1.0, 2.0, 3.0, 4.0]
