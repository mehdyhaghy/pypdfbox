"""Port of upstream ``PDTransitionTest`` (PDFBox 3.0.x).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/
pagenavigation/PDTransitionTest.java``.

Upstream ``PDTransitionStyle`` / ``PDTransitionMotion`` / ``PDTransitionDimension``
are Java enums; pypdfbox surfaces them as classes with string constants — so
``PDTransitionStyle.R.name()`` becomes just ``PDTransitionStyle.R``. Likewise
``PDTransitionDirection.NONE`` is the ``int`` sentinel ``-1`` and its
``COSBase`` projection lives on the class-level :meth:`get_cos_base` factory
rather than per-enum-member.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.pagenavigation import (
    PDTransition,
    PDTransitionDimension,
    PDTransitionDirection,
    PDTransitionMotion,
    PDTransitionStyle,
)

_TYPE: COSName = COSName.get_pdf_name("Type")
_TRANS: COSName = COSName.get_pdf_name("Trans")


def test_default_style() -> None:
    transition = PDTransition()
    assert transition.get_cos_object().get_cos_name(_TYPE) == _TRANS
    assert transition.get_style() == PDTransitionStyle.R


def test_get_style() -> None:
    transition = PDTransition(style=PDTransitionStyle.FADE)
    assert transition.get_cos_object().get_cos_name(_TYPE) == _TRANS
    assert transition.get_style() == PDTransitionStyle.FADE


def test_default_values() -> None:
    transition = PDTransition(COSDictionary())
    assert transition.get_style() == PDTransitionStyle.R
    assert transition.get_dimension() == PDTransitionDimension.H
    assert transition.get_motion() == PDTransitionMotion.I
    # ``get_direction_cos()`` mirrors upstream ``getDirection()`` which returns
    # the underlying ``COSBase`` — defaults to ``COSInteger.ZERO``.
    direction_cos = transition.get_direction_cos()
    assert isinstance(direction_cos, COSInteger)
    assert direction_cos.int_value() == 0
    assert transition.get_duration() == 1
    assert transition.get_fly_scale() == 1
    assert not transition.is_fly_area_opaque()


def test_dimension() -> None:
    transition = PDTransition()
    transition.set_dimension(PDTransitionDimension.H)
    assert transition.get_dimension() == PDTransitionDimension.H


def test_direction_none() -> None:
    transition = PDTransition()
    transition.set_direction(PDTransitionDirection.NONE)
    direction_cos = transition.get_direction_cos()
    assert isinstance(direction_cos, COSName)
    assert direction_cos == COSName.get_pdf_name("None")


def test_direction_number() -> None:
    transition = PDTransition()
    transition.set_direction(PDTransitionDirection.LEFT_TO_RIGHT)
    direction_cos = transition.get_direction_cos()
    assert isinstance(direction_cos, COSInteger)
    assert direction_cos.int_value() == 0


def test_motion() -> None:
    transition = PDTransition()
    transition.set_motion(PDTransitionMotion.O)
    assert transition.get_motion() == PDTransitionMotion.O


def test_duration() -> None:
    transition = PDTransition()
    transition.set_duration(4)
    assert transition.get_duration() == 4


def test_fly_scale() -> None:
    transition = PDTransition()
    transition.set_fly_scale(4)
    assert transition.get_fly_scale() == 4


def test_fly_area() -> None:
    transition = PDTransition()
    transition.set_fly_area_opaque(True)
    assert transition.is_fly_area_opaque()
