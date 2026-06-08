from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSString
from pypdfbox.pdmodel.interactive.pagenavigation import (
    PDThread,
    PDThreadBead,
    PDTransition,
    PDTransitionDimension,
    PDTransitionDirection,
    PDTransitionMotion,
    PDTransitionStyle,
)
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _name(name: str) -> COSName:
    return COSName.get_pdf_name(name)


def test_transition_has_and_clear_helpers_restore_read_defaults() -> None:
    transition = PDTransition()
    transition.set_style(PDTransitionStyle.FLY)
    transition.set_duration(2.5)
    transition.set_motion(PDTransitionMotion.O)
    transition.set_dimension(PDTransitionDimension.V)
    transition.set_direction(PDTransitionDirection.RIGHT_TO_LEFT)
    transition.set_scale(0.5)
    transition.set_fly_area_opaque(True)

    assert transition.has_style() is True
    assert transition.has_duration() is True
    assert transition.has_motion() is True
    assert transition.has_dimension() is True
    assert transition.has_direction() is True
    assert transition.has_scale() is True
    assert transition.has_fly_scale() is True
    assert transition.has_fly_area_opaque() is True
    assert transition.has_fly_area_to_show() is True

    transition.clear_style()
    transition.clear_duration()
    transition.clear_motion()
    transition.clear_dimension()
    transition.clear_direction()
    transition.clear_scale()
    transition.clear_fly_area_opaque()

    assert transition.has_style() is False
    assert transition.has_duration() is False
    assert transition.has_motion() is False
    assert transition.has_dimension() is False
    assert transition.has_direction() is False
    assert transition.has_scale() is False
    assert transition.has_fly_scale() is False
    assert transition.has_fly_area_opaque() is False
    assert transition.has_fly_area_to_show() is False
    assert transition.get_style() == PDTransitionStyle.R
    assert transition.get_duration() == 1
    assert transition.get_motion() == PDTransitionMotion.I
    assert transition.get_dimension() == PDTransitionDimension.H
    assert transition.get_direction() == PDTransitionDirection.LEFT_TO_RIGHT
    assert transition.get_scale() == 1
    assert transition.is_fly_area_opaque() is False


def test_transition_has_helpers_ignore_malformed_cos_values() -> None:
    raw = COSDictionary()
    raw.set_item(_name("S"), COSString("Fly"))
    raw.set_item(_name("D"), _name("BadDuration"))
    raw.set_item(_name("M"), COSString("O"))
    raw.set_item(_name("Dm"), COSString("V"))
    raw.set_item(_name("Di"), _name("BadDirection"))
    raw.set_item(_name("SS"), _name("BadScale"))
    raw.set_item(_name("B"), _name("BadBoolean"))

    transition = PDTransition(raw)

    assert transition.has_style() is False
    assert transition.has_duration() is False
    assert transition.has_motion() is False
    assert transition.has_dimension() is False
    assert transition.has_direction() is False
    assert transition.has_scale() is False
    assert transition.has_fly_area_to_show() is False
    assert transition.get_style() == PDTransitionStyle.R
    assert transition.get_duration() == 1
    assert transition.get_motion() == PDTransitionMotion.I
    assert transition.get_dimension() == PDTransitionDimension.H
    assert transition.get_direction() == PDTransitionDirection.LEFT_TO_RIGHT
    assert transition.get_scale() == 1
    assert transition.get_fly_area_to_show() is False


def test_thread_has_clear_helpers_and_aliases() -> None:
    thread = PDThread()
    info = PDDocumentInformation()
    bead = PDThreadBead()

    assert thread.has_thread_info() is False
    assert thread.has_info() is False
    assert thread.has_first_bead() is False

    thread.set_info(info)
    thread.set_first_bead(bead)
    assert thread.has_thread_info() is True
    assert thread.has_info() is True
    assert thread.has_first_bead() is True

    thread.clear_info()
    thread.clear_first_bead()
    assert thread.get_info() is None
    assert thread.get_first_bead() is None
    assert thread.has_thread_info() is False
    assert thread.has_info() is False
    assert thread.has_first_bead() is False


def test_thread_predicates_ignore_malformed_cos_values() -> None:
    raw = COSDictionary()
    raw.set_item(_name("I"), COSString("not an info dictionary"))
    raw.set_item(_name("F"), COSString("not a bead dictionary"))

    thread = PDThread(raw)

    assert thread.get_thread_info() is None
    assert thread.get_first_bead() is None
    assert thread.has_thread_info() is False
    assert thread.has_first_bead() is False


def test_thread_bead_has_clear_helpers_and_aliases() -> None:
    bead = PDThreadBead()
    thread = PDThread()
    page = PDPage()
    rect = PDRectangle(0, 0, 10, 10)

    assert bead.has_thread() is False
    assert bead.has_next_bead() is True
    assert bead.has_next() is True
    assert bead.has_previous_bead() is True
    assert bead.has_previous() is True

    bead.set_thread(thread)
    bead.set_page(page)
    bead.set_rectangle(rect)
    assert bead.has_thread() is True
    assert bead.has_page() is True
    assert bead.has_rectangle() is True
    assert bead.is_first_bead() is True

    bead.clear_thread()
    bead.clear_page()
    bead.clear_rectangle()
    bead.clear_next()
    bead.clear_previous()
    assert bead.has_thread() is False
    assert bead.has_page() is False
    assert bead.has_rectangle() is False
    assert bead.has_next_bead() is False
    assert bead.has_previous_bead() is False
    assert bead.get_next() is None
    assert bead.get_previous() is None
    assert bead.is_first_bead() is False


def test_thread_bead_predicates_and_malformed_rectangle_values() -> None:
    raw = COSDictionary()
    raw.set_item(_name("T"), COSString("not a thread dictionary"))
    raw.set_item(_name("N"), COSString("not a next bead dictionary"))
    raw.set_item(_name("V"), COSString("not a previous bead dictionary"))
    raw.set_item(_name("P"), COSString("not a page dictionary"))
    raw.set_item(
        _name("R"),
        COSArray(
            [
                COSFloat(0.0),
                COSFloat(1.0),
                COSString("not numeric"),
                COSFloat(2.0),
            ]
        ),
    )

    bead = PDThreadBead(raw)

    assert bead.get_thread() is None
    assert bead.get_next_bead() is None
    assert bead.get_previous_bead() is None
    assert bead.get_page() is None
    rectangle = bead.get_rectangle()
    assert rectangle is not None
    assert rectangle.get_lower_left_x() == 0.0
    assert rectangle.get_lower_left_y() == 1.0
    assert rectangle.get_upper_right_x() == 0.0
    assert rectangle.get_upper_right_y() == 2.0
    assert bead.has_thread() is False
    assert bead.has_next_bead() is False
    assert bead.has_previous_bead() is False
    assert bead.has_page() is False
    assert bead.has_rectangle() is False
    assert bead.is_first_bead() is False
