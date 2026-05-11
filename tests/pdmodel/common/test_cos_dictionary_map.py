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


class _Wrapper:
    def __init__(self, name: str) -> None:
        self._dict = COSDictionary()
        self._dict.set_name("K", name)

    def get_cos_object(self) -> COSDictionary:
        return self._dict


def test_put_and_get_sync_with_dictionary() -> None:
    backing = COSDictionary()
    actuals: dict[str, _Wrapper] = {}
    cdm: COSDictionaryMap[str, _Wrapper] = COSDictionaryMap(actuals, backing)
    cdm.put("alpha", _Wrapper("a"))
    assert cdm.get("alpha") is not None
    assert backing.get_dictionary_object("alpha") is not None


def test_remove_syncs_dictionary() -> None:
    backing = COSDictionary()
    actuals: dict[str, _Wrapper] = {}
    cdm: COSDictionaryMap[str, _Wrapper] = COSDictionaryMap(actuals, backing)
    cdm.put("alpha", _Wrapper("a"))
    cdm.remove("alpha")
    assert cdm.get("alpha") is None
    assert backing.get_dictionary_object("alpha") is None


def test_clear_empties_both() -> None:
    backing = COSDictionary()
    actuals: dict[str, _Wrapper] = {}
    cdm: COSDictionaryMap[str, _Wrapper] = COSDictionaryMap(actuals, backing)
    cdm.put("alpha", _Wrapper("a"))
    cdm.put("beta", _Wrapper("b"))
    cdm.clear()
    assert cdm.size() == 0
    assert backing.size() == 0


def test_size_and_contains() -> None:
    backing = COSDictionary()
    actuals: dict[str, _Wrapper] = {}
    cdm: COSDictionaryMap[str, _Wrapper] = COSDictionaryMap(actuals, backing)
    cdm.put("k1", _Wrapper("v1"))
    assert cdm.size() == 1
    assert "k1" in cdm
    assert "missing" not in cdm


def test_put_all_raises() -> None:
    cdm: COSDictionaryMap[str, _Wrapper] = COSDictionaryMap({}, COSDictionary())
    with pytest.raises(NotImplementedError):
        cdm.put_all({"x": _Wrapper("x")})


def test_convert_materializes_dict() -> None:
    out = COSDictionaryMap.convert({"alpha": _Wrapper("a"), "beta": _Wrapper("b")})
    assert isinstance(out, COSDictionary)
    assert out.size() == 2


def test_convert_basic_types_to_map_string() -> None:
    d = COSDictionary()
    d.set_item("S", COSString("hi"))
    d.set_item("I", COSInteger.get(42))
    d.set_item("F", COSFloat(1.5))
    d.set_item("B", COSBoolean.get_boolean(True))
    d.set_item("N", COSName.get_pdf_name("Foo"))
    out = COSDictionaryMap.convert_basic_types_to_map(d)
    assert out is not None
    assert out.get("S") == "hi"
    assert out.get("I") == 42
    assert out.get("F") == pytest.approx(1.5)
    assert out.get("B") is True
    assert out.get("N") == "Foo"


def test_convert_basic_types_to_map_none_input() -> None:
    assert COSDictionaryMap.convert_basic_types_to_map(None) is None


def test_convert_basic_types_to_map_unknown_raises() -> None:
    d = COSDictionary()
    d.set_item("X", COSDictionary())
    with pytest.raises(OSError):
        COSDictionaryMap.convert_basic_types_to_map(d)
