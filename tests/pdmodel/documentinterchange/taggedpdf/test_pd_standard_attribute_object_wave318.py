from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDLayoutAttributeObject,
    PDStandardAttributeObject,
)


class _ConcreteStandard(PDStandardAttributeObject):
    pass


def test_wave318_set_number_rejects_bool_without_mutating() -> None:
    obj = _ConcreteStandard(COSDictionary())

    with pytest.raises(TypeError, match="LineHeight must be a number"):
        obj.set_number("LineHeight", True)

    assert obj.get_cos_object().get_dictionary_object("LineHeight") is None


def test_wave318_set_integer_rejects_bool_without_mutating() -> None:
    obj = _ConcreteStandard(COSDictionary())

    with pytest.raises(TypeError, match="ColumnCount must be an integer"):
        obj.set_integer("ColumnCount", False)

    assert obj.get_cos_object().get_dictionary_object("ColumnCount") is None


def test_wave318_layout_numeric_setter_rejects_bool_without_mutating() -> None:
    obj = PDLayoutAttributeObject()

    with pytest.raises(TypeError, match="SpaceBefore must be a number"):
        obj.set_space_before(True)

    assert obj.get_cos_object().get_dictionary_object("SpaceBefore") is None
