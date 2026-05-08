from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.pagenavigation import (
    PDTransition,
    PDTransitionDirection,
)


def test_malformed_direction_name_is_absent_but_raw_value_is_preserved() -> None:
    raw = COSDictionary()
    malformed_direction = COSName.get_pdf_name("Sideways")
    raw.set_item(COSName.get_pdf_name("Di"), malformed_direction)

    transition = PDTransition(raw)

    assert transition.has_direction() is False
    assert transition.get_direction() == PDTransitionDirection.LEFT_TO_RIGHT
    assert transition.get_direction_cos() is malformed_direction
