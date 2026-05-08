from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDUserAttributeObject,
    PDUserProperty,
)


def test_wave306_user_property_is_unhashable_with_value_equality() -> None:
    owner = PDUserAttributeObject()
    dictionary = COSDictionary()
    dictionary.set_string("N", "alpha")

    left = PDUserProperty(owner, dictionary)
    right = PDUserProperty(owner, dictionary)

    assert left == right
    with pytest.raises(TypeError):
        hash(left)
