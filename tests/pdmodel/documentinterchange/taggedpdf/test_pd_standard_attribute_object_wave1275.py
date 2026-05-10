"""Wave 1275 — PDStandardAttributeObject.set_four_colors public helper."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_four_colours import (
    PDFourColours,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_standard_attribute_object import (
    PDStandardAttributeObject,
)


class _ConcreteAttr(PDStandardAttributeObject):
    """Minimal concrete subclass — PDStandardAttributeObject is abstract-ish."""


def _make() -> _ConcreteAttr:
    return _ConcreteAttr(COSDictionary())


def test_set_four_colors_writes_envelope() -> None:
    attr = _make()
    four = PDFourColours()
    four.set_top((1.0, 0.0, 0.0))
    four.set_right((0.0, 1.0, 0.0))
    four.set_bottom((0.0, 0.0, 1.0))
    four.set_left((1.0, 1.0, 0.0))

    attr.set_four_colors("BorderColor", four)
    cos = attr.get_cos_object().get_dictionary_object("BorderColor")
    assert isinstance(cos, COSArray)
    assert cos.size() == 4
    # The stored array is the same one carried by the PDFourColours wrapper.
    assert cos is four.get_cos_array()


def test_set_four_colors_none_removes_entry() -> None:
    attr = _make()
    four = PDFourColours()
    four.set_top((0.5, 0.5, 0.5))
    attr.set_four_colors("BorderColor", four)
    assert attr.is_specified("BorderColor")

    attr.set_four_colors("BorderColor", None)
    assert not attr.is_specified("BorderColor")


def test_set_four_colors_round_trip_through_get_color_or_four_colors() -> None:
    attr = _make()
    four = PDFourColours()
    four.set_top((1.0, 0.0, 0.0))
    four.set_right((0.0, 1.0, 0.0))
    four.set_bottom((0.0, 0.0, 1.0))
    four.set_left((1.0, 1.0, 0.0))
    attr.set_four_colors("BorderColor", four)

    result = attr.get_color_or_four_colors("BorderColor")
    assert isinstance(result, PDFourColours)
    assert result.get_top() == (1.0, 0.0, 0.0)
    assert result.get_left() == (1.0, 1.0, 0.0)
