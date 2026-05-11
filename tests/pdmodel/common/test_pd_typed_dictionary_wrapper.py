from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.common import PDTypedDictionaryWrapper


def test_construct_with_type_string_sets_type_entry() -> None:
    pdw = PDTypedDictionaryWrapper("X")
    assert pdw.get_type() == "X"
    assert pdw.get_cos_object().get_name_as_string("Type") == "X"


def test_construct_with_existing_dictionary() -> None:
    d = COSDictionary()
    d.set_name("Type", "Other")
    pdw = PDTypedDictionaryWrapper(d)
    assert pdw.get_cos_object() is d
    assert pdw.get_type() == "Other"


def test_construct_with_none_creates_typeless_dict() -> None:
    pdw = PDTypedDictionaryWrapper()
    assert pdw.get_type() is None


def test_construct_with_invalid_raises() -> None:
    with pytest.raises(TypeError):
        PDTypedDictionaryWrapper(42)  # type: ignore[arg-type]


def test_no_set_type_method() -> None:
    # Mirrors upstream's deliberate omission of setType.
    pdw = PDTypedDictionaryWrapper("X")
    assert not hasattr(pdw, "set_type")
