from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.pagenavigation import (
    PDThread,
    PDTransition,
    PDTransitionDirection,
)


def test_thread_compares_equal_to_itself() -> None:
    thread = PDThread()

    assert thread == thread


def test_transition_direction_defaults_for_unrecognized_cos_type() -> None:
    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("Di"), COSDictionary())

    transition = PDTransition(raw)

    assert transition.has_direction() is False
    assert transition.get_direction() == PDTransitionDirection.LEFT_TO_RIGHT
