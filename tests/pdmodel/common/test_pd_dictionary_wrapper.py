from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.common import PDDictionaryWrapper


def test_default_constructor_creates_empty_dict() -> None:
    pdw = PDDictionaryWrapper()
    assert isinstance(pdw.get_cos_object(), COSDictionary)
    assert pdw.get_cos_object().size() == 0


def test_existing_dictionary_preserved() -> None:
    d = COSDictionary()
    d.set_name("Type", "X")
    pdw = PDDictionaryWrapper(d)
    assert pdw.get_cos_object() is d


def test_equality_by_dictionary_identity() -> None:
    d = COSDictionary()
    d.set_name("X", "Y")
    pdw1 = PDDictionaryWrapper(d)
    pdw2 = PDDictionaryWrapper(d)
    assert pdw1 == pdw2


def test_inequality_with_non_wrapper() -> None:
    pdw = PDDictionaryWrapper()
    assert pdw != "not a wrapper"
    assert pdw == pdw


def test_hash_is_defined() -> None:
    d = COSDictionary()
    d.set_name("A", "B")
    pdw = PDDictionaryWrapper(d)
    assert isinstance(hash(pdw), int)


def test_equals_method_delegates_to_dunder_eq() -> None:
    """``equals(Object)`` mirrors upstream's Java ``equals`` and must
    return the same answer as Python's ``==``."""
    d = COSDictionary()
    d.set_name("X", "Y")
    a = PDDictionaryWrapper(d)
    b = PDDictionaryWrapper(d)
    assert a.equals(b) is True
    assert a.equals(PDDictionaryWrapper()) is False
    assert a.equals("not a wrapper") is False
    assert a.equals(a) is True


def test_hash_code_method_delegates_to_dunder_hash() -> None:
    """``hash_code()`` mirrors upstream ``hashCode()`` and returns the
    same int as ``hash(self)``."""
    d = COSDictionary()
    d.set_name("A", "B")
    pdw = PDDictionaryWrapper(d)
    assert pdw.hash_code() == hash(pdw)
