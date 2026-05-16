"""Coverage tests for :mod:`pypdfbox.pdmodel.common.cos_dictionary_map`.

Targets the read-only accessors (``is_empty``, ``contains_value``,
``key_set``, ``values``, ``entry_set``), the dunder protocols, the
``equals``/``hash_code``/``to_string`` parity surface, and the
``_to_cos`` value-coercion helper.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.common import COSDictionaryMap
from pypdfbox.pdmodel.common.cos_dictionary_map import _to_cos


class _Wrapper:
    def __init__(self, name: str) -> None:
        self._dict = COSDictionary()
        self._dict.set_name("K", name)

    def get_cos_object(self) -> COSDictionary:
        return self._dict


def _empty_map() -> COSDictionaryMap[str, _Wrapper]:
    return COSDictionaryMap({}, COSDictionary())


# ----------------------------------------------------------------------
# Read-only accessors (lines 40, 46, 52, 55, 58)
# ----------------------------------------------------------------------
def test_is_empty_returns_true_for_fresh_map() -> None:
    cdm = _empty_map()
    assert cdm.is_empty() is True


def test_is_empty_returns_false_after_put() -> None:
    cdm = _empty_map()
    cdm.put("k", _Wrapper("v"))
    assert cdm.is_empty() is False


def test_contains_value_true_for_inserted_value() -> None:
    cdm = _empty_map()
    wrapped = _Wrapper("v")
    cdm.put("k", wrapped)
    assert cdm.contains_value(wrapped) is True
    assert cdm.contains_value(_Wrapper("other")) is False


def test_key_set_returns_set_of_keys() -> None:
    cdm = _empty_map()
    cdm.put("a", _Wrapper("a"))
    cdm.put("b", _Wrapper("b"))
    assert cdm.key_set() == {"a", "b"}


def test_values_returns_list_of_values() -> None:
    cdm = _empty_map()
    w1 = _Wrapper("a")
    w2 = _Wrapper("b")
    cdm.put("k1", w1)
    cdm.put("k2", w2)
    assert cdm.values() == [w1, w2]


def test_entry_set_returns_list_of_pairs() -> None:
    cdm = _empty_map()
    w = _Wrapper("v")
    cdm.put("k", w)
    assert cdm.entry_set() == [("k", w)]


# ----------------------------------------------------------------------
# Python protocol dunders (lines 83, 86, 92, 95, 98)
# ----------------------------------------------------------------------
def test_len_matches_size() -> None:
    cdm = _empty_map()
    cdm.put("a", _Wrapper("a"))
    cdm.put("b", _Wrapper("b"))
    assert len(cdm) == 2


def test_iter_yields_keys() -> None:
    cdm = _empty_map()
    cdm.put("a", _Wrapper("a"))
    cdm.put("b", _Wrapper("b"))
    assert sorted(iter(cdm)) == ["a", "b"]


def test_getitem_returns_value() -> None:
    cdm = _empty_map()
    w = _Wrapper("v")
    cdm.put("k", w)
    assert cdm["k"] is w


def test_setitem_delegates_to_put() -> None:
    cdm = _empty_map()
    w = _Wrapper("v")
    cdm["k"] = w
    assert cdm.get("k") is w


def test_delitem_delegates_to_remove() -> None:
    cdm = _empty_map()
    cdm.put("k", _Wrapper("v"))
    del cdm["k"]
    assert cdm.get("k") is None


# ----------------------------------------------------------------------
# Equality / hash / repr / parity surface (lines 101-103, 106, 109, 115, 119, 123)
# ----------------------------------------------------------------------
def test_eq_returns_true_for_same_backing_dictionary() -> None:
    backing = COSDictionary()
    a = COSDictionaryMap({}, backing)
    b = COSDictionaryMap({}, backing)
    assert a == b
    assert a.equals(b) is True


def test_eq_returns_false_for_different_backing_dictionary() -> None:
    a = _empty_map()
    b = _empty_map()
    assert (a == b) is False


def test_eq_returns_false_for_unrelated_object() -> None:
    cdm = _empty_map()
    assert (cdm == "not a map") is False
    assert cdm.equals(42) is False


def test_hash_uses_backing_dictionary_id() -> None:
    backing = COSDictionary()
    cdm = COSDictionaryMap({}, backing)
    assert hash(cdm) == id(backing)
    assert cdm.hash_code() == id(backing)


def test_repr_returns_to_string() -> None:
    cdm = _empty_map()
    cdm.put("k", _Wrapper("v"))
    assert repr(cdm) == cdm.to_string()


def test_to_string_is_repr_of_actuals() -> None:
    cdm: COSDictionaryMap[str, int] = COSDictionaryMap({"a": 1}, COSDictionary())
    assert cdm.to_string() == repr({"a": 1})


# ----------------------------------------------------------------------
# _to_cos coercion helper (lines 179, 181, 183, 185, 187, 191)
# ----------------------------------------------------------------------
def test_to_cos_passes_through_cos_base() -> None:
    name = COSName.get_pdf_name("X")
    assert _to_cos(name) is name


def test_to_cos_converts_str_to_cos_string() -> None:
    result = _to_cos("hello")
    assert isinstance(result, COSString)
    assert result.get_string() == "hello"


def test_to_cos_converts_bool_to_cos_boolean() -> None:
    result = _to_cos(True)
    assert isinstance(result, COSBoolean)
    assert result.get_value() is True


def test_to_cos_converts_int_to_cos_integer() -> None:
    result = _to_cos(42)
    assert isinstance(result, COSInteger)
    assert result.int_value() == 42


def test_to_cos_converts_float_to_cos_float() -> None:
    result = _to_cos(1.5)
    assert isinstance(result, COSFloat)
    assert result.float_value() == pytest.approx(1.5)


def test_to_cos_uses_get_cos_object_for_wrappers() -> None:
    wrapper = _Wrapper("v")
    result = _to_cos(wrapper)
    assert result is wrapper.get_cos_object()


def test_to_cos_raises_for_unsupported_type() -> None:
    class _Unknown:
        pass

    with pytest.raises(TypeError, match="cannot convert"):
        _to_cos(_Unknown())
