from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSString
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDParentTreeValue,
)


def test_construct_from_array() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(1))
    val = PDParentTreeValue(arr)
    assert val.get_cos_object() is arr


def test_construct_from_dictionary() -> None:
    d = COSDictionary()
    d.set_string("Name", "Foo")
    val = PDParentTreeValue(d)
    assert val.get_cos_object() is d


def test_invalid_argument_type_raises() -> None:
    with pytest.raises(TypeError):
        PDParentTreeValue(COSString("nope"))  # type: ignore[arg-type]


def test_repr_delegates_to_underlying() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(7))
    val = PDParentTreeValue(arr)
    assert repr(arr) == repr(val)
