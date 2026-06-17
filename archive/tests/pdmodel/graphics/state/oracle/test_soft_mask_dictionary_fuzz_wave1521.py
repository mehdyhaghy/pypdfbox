"""Malformed ``PDSoftMask`` dictionary parity with PDFBox 3.0.7."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
)
from pypdfbox.pdmodel.common.function.pd_function import PDFunctionTypeIdentity
from pypdfbox.pdmodel.graphics.form.pd_transparency_group import (
    PDTransparencyGroup,
)
from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache
from tests.oracle.harness import requires_oracle, run_probe_text

_S = COSName.get_pdf_name("S")
_G = COSName.get_pdf_name("G")
_BC = COSName.get_pdf_name("BC")
_TR = COSName.get_pdf_name("TR")
_TAG = COSName.get_pdf_name("Tag")


def _indirect(value: COSBase, number: int) -> COSObject:
    return COSObject(number, resolved=value)


def _array(size: int) -> COSArray:
    return COSArray([COSFloat(index + 0.25) for index in range(size)])


def _function(function_type: int) -> COSDictionary:
    value = COSDictionary()
    value.set_int(COSName.get_pdf_name("FunctionType"), function_type)
    return value


def _form(tag: str, transparency: bool) -> COSStream:
    stream = COSStream()
    stream.set_name(COSName.get_pdf_name("Subtype"), "Form")
    stream.set_name(_TAG, tag)
    stream.set_item(COSName.get_pdf_name("Resources"), COSDictionary())
    if transparency:
        group = COSDictionary()
        group.set_name(_S, "Transparency")
        stream.set_item(COSName.get_pdf_name("Group"), group)
    return stream


def _subtype_stream(subtype: str | None) -> COSStream:
    stream = COSStream()
    if subtype is not None:
        stream.set_name(COSName.get_pdf_name("Subtype"), subtype)
    return stream


def _mixed_array() -> COSArray:
    return COSArray([COSName.get_pdf_name("Bad"), COSNull.NULL])


_FACTORY_CASES: tuple[tuple[str, Callable[[int], COSBase | None]], ...] = (
    ("null", lambda _: None),
    ("none", lambda _: COSName.get_pdf_name("None")),
    ("dict", lambda _: COSDictionary()),
    ("stream", lambda _: COSStream()),
    ("name", lambda _: COSName.get_pdf_name("Bad")),
    ("integer", lambda _: COSInteger.get(1)),
    ("array", lambda _: COSArray()),
    ("cos_null", lambda _: COSNull.NULL),
    ("indirect_none", lambda n: _indirect(COSName.get_pdf_name("None"), n)),
    ("indirect_dict", lambda n: _indirect(COSDictionary(), n)),
    ("indirect_null", lambda n: _indirect(COSNull.NULL, n)),
)

_ENTRY_CASES: tuple[
    tuple[str, COSName | None, Callable[[int], COSBase | None]], ...
] = (
    ("empty", None, lambda _: None),
    ("s_alpha", _S, lambda _: COSName.get_pdf_name("Alpha")),
    ("s_luminosity", _S, lambda _: COSName.get_pdf_name("Luminosity")),
    ("s_unknown", _S, lambda _: COSName.get_pdf_name("Unknown")),
    ("s_integer", _S, lambda _: COSInteger.get(1)),
    ("s_null", _S, lambda _: COSNull.NULL),
    ("s_indirect", _S, lambda n: _indirect(COSName.get_pdf_name("Alpha"), n)),
    ("s_indirect_wrong", _S, lambda n: _indirect(COSInteger.get(1), n)),
    ("s_indirect_null", _S, lambda n: _indirect(COSNull.NULL, n)),
    ("g_group", _G, lambda _: _form("direct", True)),
    ("g_form", _G, lambda _: _form("plain", False)),
    ("g_image", _G, lambda _: _subtype_stream("Image")),
    ("g_ps", _G, lambda _: _subtype_stream("PS")),
    ("g_bad_subtype", _G, lambda _: _subtype_stream("Bad")),
    ("g_no_subtype", _G, lambda _: _subtype_stream(None)),
    ("g_dictionary", _G, lambda _: COSDictionary()),
    ("g_name", _G, lambda _: COSName.get_pdf_name("Bad")),
    ("g_null", _G, lambda _: COSNull.NULL),
    ("g_indirect_group", _G, lambda n: _indirect(_form("indirect", True), n)),
    (
        "g_indirect_form",
        _G,
        lambda n: _indirect(_form("indirect_plain", False), n),
    ),
    ("g_indirect_wrong", _G, lambda n: _indirect(COSDictionary(), n)),
    ("g_indirect_null", _G, lambda n: _indirect(COSNull.NULL, n)),
    ("g_cache", _G, lambda _: _form("cached", True)),
    ("bc_empty", _BC, lambda _: _array(0)),
    ("bc_three", _BC, lambda _: _array(3)),
    ("bc_mixed", _BC, lambda _: _mixed_array()),
    ("bc_name", _BC, lambda _: COSName.get_pdf_name("Bad")),
    ("bc_integer", _BC, lambda _: COSInteger.get(1)),
    ("bc_null", _BC, lambda _: COSNull.NULL),
    ("bc_indirect", _BC, lambda n: _indirect(_array(2), n)),
    ("bc_indirect_wrong", _BC, lambda n: _indirect(COSInteger.get(1), n)),
    ("bc_indirect_null", _BC, lambda n: _indirect(COSNull.NULL, n)),
    ("tr_identity", _TR, lambda _: COSName.get_pdf_name("Identity")),
    ("tr_type0", _TR, lambda _: _function(0)),
    ("tr_type2", _TR, lambda _: _function(2)),
    ("tr_type3", _TR, lambda _: _function(3)),
    ("tr_type4", _TR, lambda _: _function(4)),
    ("tr_no_type", _TR, lambda _: COSDictionary()),
    ("tr_unknown_type", _TR, lambda _: _function(9)),
    ("tr_name", _TR, lambda _: COSName.get_pdf_name("Bad")),
    ("tr_integer", _TR, lambda _: COSInteger.get(1)),
    ("tr_array", _TR, lambda _: COSArray()),
    ("tr_null", _TR, lambda _: COSNull.NULL),
    (
        "tr_indirect_identity",
        _TR,
        lambda n: _indirect(COSName.get_pdf_name("Identity"), n),
    ),
    ("tr_indirect_type2", _TR, lambda n: _indirect(_function(2), n)),
    ("tr_indirect_wrong", _TR, lambda n: _indirect(COSInteger.get(1), n)),
    ("tr_indirect_null", _TR, lambda n: _indirect(COSNull.NULL, n)),
)

_MUTATION_CASES = (
    "s_cached",
    "s_retry",
    "g_cached",
    "g_retry",
    "bc_cached",
    "bc_retry",
    "tr_cached",
    "tr_retry",
)

_PINNED = {
    "CASE g_no_subtype": (
        "CASE g_no_subtype s=null g=ERR bc=null tr=null cache=ERR",
        "CASE g_no_subtype s=null g=form:none bc=null tr=null cache=null",
    ),
    "CASE g_dictionary": (
        "CASE g_dictionary s=null g=ERR bc=null tr=null cache=ERR",
        "CASE g_dictionary s=null g=null bc=null tr=null cache=na",
    ),
    "CASE g_indirect_wrong": (
        "CASE g_indirect_wrong s=null g=ERR bc=null tr=null cache=ERR",
        "CASE g_indirect_wrong s=null g=null bc=null tr=null cache=na",
    ),
}


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    lines = run_probe_text("SoftMaskDictionaryFuzzProbe").splitlines()
    return {" ".join(line.split(" ", 2)[:2]): line for line in lines}


def _create_projection(base: COSBase | None, cache: object | None) -> str:
    try:
        mask = PDSoftMask.create(base, cache)
        if mask is None:
            return "null"
        return "mask:same" if mask.get_cos_object() is base else "mask:other"
    except Exception:
        return "ERR"


def _emit_factory(name: str, builder: Callable[[int], COSBase | None]) -> str:
    base = builder(1)
    plain = _create_projection(base, None)
    cached = _create_projection(base, DefaultResourceCache())
    return f"CREATE {name} plain={plain} cached={cached}"


def _subtype(mask: PDSoftMask) -> str:
    try:
        value = mask.get_subtype()
        return "null" if value is None else value.name
    except Exception:
        return "ERR"


def _group(mask: PDSoftMask) -> str:
    try:
        value = mask.get_group()
        if value is None:
            return "null"
        tag = value.get_cos_object().get_name(_TAG)
        prefix = "group" if isinstance(value, PDTransparencyGroup) else "form"
        return f"{prefix}:{tag or 'none'}"
    except Exception:
        return "ERR"


def _backdrop(mask: PDSoftMask) -> str:
    try:
        value = mask.get_backdrop_color()
        return "null" if value is None else f"array:{value.size()}"
    except Exception:
        return "ERR"


def _transfer(mask: PDSoftMask) -> str:
    try:
        value = mask.get_transfer_function_typed()
        if value is None:
            return "null"
        if isinstance(value, PDFunctionTypeIdentity):
            return "identity"
        return str(value.get_function_type())
    except Exception:
        return "ERR"


def _cache(mask: PDSoftMask, expected: object | None) -> str:
    try:
        value = mask.get_group()
        if value is None:
            return "na"
        actual = value._cache
        if actual is expected:
            return "null" if expected is None else "same"
        return "other"
    except Exception:
        return "ERR"


def _emit_entry(
    name: str,
    key: COSName | None,
    builder: Callable[[int], COSBase | None],
    number: int,
) -> str:
    dictionary = COSDictionary()
    value = builder(number)
    if key is not None and value is not None:
        dictionary.set_item(key, value)
    cache = DefaultResourceCache() if name == "g_cache" else None
    mask = PDSoftMask(dictionary, cache)
    return (
        f"CASE {name} s={_subtype(mask)} g={_group(mask)}"
        f" bc={_backdrop(mask)} tr={_transfer(mask)} cache={_cache(mask, cache)}"
    )


def _emit_mutation(name: str) -> str:
    dictionary = COSDictionary()
    mask = PDSoftMask(dictionary)
    if name == "s_cached":
        dictionary.set_item(_S, COSName.get_pdf_name("Alpha"))
        first = _subtype(mask)
        dictionary.set_item(_S, COSName.get_pdf_name("Luminosity"))
        second = _subtype(mask)
    elif name == "s_retry":
        dictionary.set_item(_S, COSInteger.get(1))
        first = _subtype(mask)
        dictionary.set_item(_S, COSName.get_pdf_name("Alpha"))
        second = _subtype(mask)
    elif name == "g_cached":
        dictionary.set_item(_G, _form("first", True))
        first = _group(mask)
        dictionary.set_item(_G, _form("second", True))
        second = _group(mask)
    elif name == "g_retry":
        dictionary.set_item(_G, _form("plain_first", False))
        first = _group(mask)
        dictionary.set_item(_G, _form("fixed", True))
        second = _group(mask)
    elif name == "bc_cached":
        dictionary.set_item(_BC, _array(1))
        first = _backdrop(mask)
        dictionary.set_item(_BC, _array(3))
        second = _backdrop(mask)
    elif name == "bc_retry":
        dictionary.set_item(_BC, COSInteger.get(1))
        first = _backdrop(mask)
        dictionary.set_item(_BC, _array(2))
        second = _backdrop(mask)
    elif name == "tr_cached":
        dictionary.set_item(_TR, _function(2))
        first = _transfer(mask)
        dictionary.set_item(_TR, _function(3))
        second = _transfer(mask)
    else:
        dictionary.set_item(_TR, _function(9))
        first = _transfer(mask)
        dictionary.set_item(_TR, _function(2))
        second = _transfer(mask)
    return f"MUTATE {name} first={first} second={second}"


def _assert_oracle(key: str, python_line: str, java_line: str) -> None:
    pinned = _PINNED.get(key)
    if pinned is None:
        assert python_line == java_line
        return
    expected_java, expected_python = pinned
    assert java_line == expected_java
    assert python_line == expected_python


@requires_oracle
@pytest.mark.parametrize(
    ("name", "builder"),
    _FACTORY_CASES,
    ids=[f"f{index:02}" for index in range(len(_FACTORY_CASES))],
)
def test_factory_matches_oracle(
    name: str,
    builder: Callable[[int], COSBase | None],
    java_lines: dict[str, str],
) -> None:
    key = f"CREATE {name}"
    _assert_oracle(key, _emit_factory(name, builder), java_lines[key])


@requires_oracle
@pytest.mark.parametrize(
    ("name", "key", "builder"),
    _ENTRY_CASES,
    ids=[f"e{index:02}" for index in range(len(_ENTRY_CASES))],
)
def test_accessors_match_oracle(
    name: str,
    key: COSName | None,
    builder: Callable[[int], COSBase | None],
    java_lines: dict[str, str],
) -> None:
    actual = _emit_entry(name, key, builder, 100 + _ENTRY_CASES.index((name, key, builder)))
    line_key = f"CASE {name}"
    _assert_oracle(line_key, actual, java_lines[line_key])


@requires_oracle
@pytest.mark.parametrize(
    "name",
    _MUTATION_CASES,
    ids=[f"m{index:02}" for index in range(len(_MUTATION_CASES))],
)
def test_accessor_caching_matches_oracle(
    name: str, java_lines: dict[str, str]
) -> None:
    key = f"MUTATE {name}"
    _assert_oracle(key, _emit_mutation(name), java_lines[key])
