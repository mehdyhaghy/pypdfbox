from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
)


def test_typed_presence_helpers_match_dictionary_getter_shapes() -> None:
    child = COSDictionary()
    array = COSArray([COSInteger.ONE])  # type: ignore[attr-defined]
    dictionary = COSDictionary(
        [
            ("Name", COSName.get_pdf_name("Page")),
            ("String", COSString("Title")),
            ("Int", COSInteger.get(7)),
            ("Float", COSFloat(2.5)),
            ("Boolean", COSBoolean.TRUE),
            ("Dictionary", child),
            ("Array", array),
        ]
    )

    assert dictionary.has_name("Name")
    assert dictionary.has_string("Name")
    assert dictionary.has_string("String")
    assert dictionary.has_int("Int")
    assert dictionary.has_int("Float")
    assert dictionary.has_long("Int")
    assert dictionary.has_float("Int")
    assert dictionary.has_boolean("Boolean")
    assert dictionary.has_cos_dictionary("Dictionary")
    assert dictionary.has_cos_array("Array")


def test_typed_presence_helpers_resolve_indirect_values_and_ignore_cos_null() -> None:
    dictionary = COSDictionary(
        [
            ("Name", COSObject(1, 0, resolved=COSName.get_pdf_name("Page"))),
            ("String", COSObject(2, 0, resolved=COSString("Title"))),
            ("Int", COSObject(3, 0, resolved=COSInteger.get(7))),
            ("Boolean", COSObject(4, 0, resolved=COSBoolean.TRUE)),
            ("Null", COSObject(5, 0, resolved=COSNull.NULL)),
            ("Missing", COSObject(6, 0)),
        ]
    )

    assert dictionary.has_name("Name")
    assert dictionary.has_string("String")
    assert dictionary.has_int("Int")
    assert dictionary.has_boolean("Boolean")
    assert not dictionary.has_name("Null")
    assert not dictionary.has_string("Null")
    assert not dictionary.has_int("Missing")
    assert dictionary.get_item("Null") is not None


def test_typed_presence_helpers_reject_malformed_shapes() -> None:
    dictionary = COSDictionary(
        [
            ("Name", COSString("not-a-name")),
            ("String", COSInteger.ONE),  # type: ignore[attr-defined]
            ("Int", COSName.get_pdf_name("not-a-number")),
            ("Float", COSBoolean.TRUE),
            ("Boolean", COSInteger.ONE),  # type: ignore[attr-defined]
            ("Dictionary", COSArray()),
            ("Array", COSDictionary()),
        ]
    )

    assert not dictionary.has_name("Name")
    assert not dictionary.has_string("String")
    assert not dictionary.has_int("Int")
    assert not dictionary.has_float("Float")
    assert not dictionary.has_boolean("Boolean")
    assert not dictionary.has_cos_dictionary("Dictionary")
    assert not dictionary.has_cos_array("Array")


def test_typed_clear_helpers_remove_entries() -> None:
    dictionary = COSDictionary(
        [
            ("Name", COSName.get_pdf_name("Page")),
            ("String", COSString("Title")),
            ("Int", COSInteger.get(7)),
            ("Long", COSInteger.get(8)),
            ("Float", COSFloat(2.5)),
            ("Boolean", COSBoolean.TRUE),
            ("Dictionary", COSDictionary()),
            ("Array", COSArray()),
        ]
    )

    dictionary.clear_name("Name")
    dictionary.clear_string("String")
    dictionary.clear_int("Int")
    dictionary.clear_long("Long")
    dictionary.clear_float("Float")
    dictionary.clear_boolean("Boolean")
    dictionary.clear_cos_dictionary("Dictionary")
    dictionary.clear_cos_array("Array")

    assert dictionary.is_empty()


def test_camelcase_presence_and_clear_aliases_delegate() -> None:
    dictionary = COSDictionary(
        [
            ("Name", COSName.get_pdf_name("Page")),
            ("String", COSString("Title")),
            ("Int", COSInteger.get(7)),
            ("Long", COSInteger.get(8)),
            ("Float", COSFloat(2.5)),
            ("Boolean", COSBoolean.TRUE),
            ("Dictionary", COSDictionary()),
            ("Array", COSArray()),
            ("Raw", COSInteger.ONE),  # type: ignore[attr-defined]
        ]
    )

    assert dictionary.hasName("Name")
    assert dictionary.hasString("String")
    assert dictionary.hasInt("Int")
    assert dictionary.hasLong("Long")
    assert dictionary.hasFloat("Float")
    assert dictionary.hasBoolean("Boolean")
    assert dictionary.hasCOSDictionary("Dictionary")
    assert dictionary.hasCOSArray("Array")

    dictionary.clearName("Name")
    dictionary.clearString("String")
    dictionary.clearInt("Int")
    dictionary.clearLong("Long")
    dictionary.clearFloat("Float")
    dictionary.clearBoolean("Boolean")
    dictionary.clearCOSDictionary("Dictionary")
    dictionary.clearCOSArray("Array")
    dictionary.clearItem("Raw")

    assert dictionary.is_empty()
