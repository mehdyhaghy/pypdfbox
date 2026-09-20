"""PDFBOX-6261 — ``getArrayOfString`` / ``getHeaders`` on standard attribute
objects.

Upstream cast every ``/Headers`` element to ``COSName``, so the getter raised
``ClassCastException`` on the byte strings that PDF 32000-1 Table 349 actually
mandates (TIKA-4891). It now reads each slot through ``COSArray.getString(int)``
and keeps the array *positional*: a non-string element yields ``null`` in place
(logged at WARNING) rather than being dropped, so element *i* still lines up
with column *i*.
"""

from __future__ import annotations

import logging

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDExportFormatAttributeObject,
    PDTableAttributeObject,
)

_STD_LOGGER = (
    "pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_standard_attribute_object"
)


def _table_with_headers(*items: object) -> PDTableAttributeObject:
    dictionary = COSDictionary()
    dictionary.set_name("O", "Table")
    headers = COSArray()
    for item in items:
        headers.add(item)
    dictionary.set_item("Headers", headers)
    return PDTableAttributeObject(dictionary)


# ---------------------------------------------------------------------------
# The ClassCastException case: an array of COSString.
# ---------------------------------------------------------------------------


def test_headers_of_cos_strings_are_returned() -> None:
    obj = _table_with_headers(COSString("node0"), COSString("node1"))
    assert obj.get_headers() == ["node0", "node1"]


def test_export_format_headers_of_cos_strings_are_returned() -> None:
    dictionary = COSDictionary()
    dictionary.set_name("O", "XML-1.00")
    headers = COSArray()
    headers.add(COSString("node0"))
    dictionary.set_item("Headers", headers)
    obj = PDExportFormatAttributeObject(dictionary)
    assert obj.get_headers() == ["node0"]


# ---------------------------------------------------------------------------
# Positional None for non-string slots + the WARNING upstream added.
# ---------------------------------------------------------------------------


def test_non_string_element_yields_none_in_place() -> None:
    obj = _table_with_headers(
        COSName.get_pdf_name("Ignored"), COSString("node1"), COSInteger.get(7)
    )
    # Upstream returns String[]{null, "node1", null} — positions are kept so
    # headers[i] still corresponds to column i.
    assert obj.get_headers() == [None, "node1", None]


def test_non_string_element_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    obj = _table_with_headers(COSString("node0"), COSInteger.get(7))
    with caplog.at_level(logging.WARNING, logger=_STD_LOGGER):
        assert obj.get_headers() == ["node0", None]
    messages = [record.getMessage() for record in caplog.records]
    assert any("Element 1 is" in message for message in messages)
    assert any("should be a string" in message for message in messages)


def test_all_string_headers_log_nothing(caplog: pytest.LogCaptureFixture) -> None:
    obj = _table_with_headers(COSString("node0"), COSString("node1"))
    with caplog.at_level(logging.WARNING, logger=_STD_LOGGER):
        obj.get_headers()
    assert caplog.records == []


# ---------------------------------------------------------------------------
# Absent / wrong-typed /Headers.
# ---------------------------------------------------------------------------


def test_absent_headers_returns_none() -> None:
    """Upstream javadoc after PDFBOX-6261: "the headers or null if there are
    none"."""
    obj = PDTableAttributeObject()
    assert obj.get_headers() is None


def test_headers_not_an_array_returns_none() -> None:
    dictionary = COSDictionary()
    dictionary.set_name("O", "Table")
    dictionary.set_item("Headers", COSString("not an array"))
    assert PDTableAttributeObject(dictionary).get_headers() is None


def test_empty_headers_array_returns_empty_list() -> None:
    obj = _table_with_headers()
    assert obj.get_headers() == []


# ---------------------------------------------------------------------------
# Round-trip + decoding parity with COSString.get_string().
# ---------------------------------------------------------------------------


def test_set_headers_round_trips_non_ascii() -> None:
    obj = PDTableAttributeObject()
    obj.set_headers(["café", "日本"])
    assert obj.get_headers() == ["café", "日本"]


def test_export_format_set_headers_round_trips_non_ascii() -> None:
    obj = PDExportFormatAttributeObject()
    obj.set_headers(["café"])
    assert obj.get_headers() == ["café"]


def test_headers_decode_matches_cos_string_get_string() -> None:
    """Elements are decoded by ``COSString.get_string()`` (UTF-16 BOM sniffing,
    else PDFDocEncoding) exactly as upstream's ``COSArray.getString(int)``."""
    raw = COSString(b"\xff")
    obj = _table_with_headers(raw)
    assert obj.get_headers() == [raw.get_string()]


# ---------------------------------------------------------------------------
# toString() renders a null slot as Java's StringJoiner does.
# ---------------------------------------------------------------------------


def test_to_string_renders_none_slot_as_null() -> None:
    obj = _table_with_headers(COSString("node0"), COSName.get_pdf_name("Ignored"))
    assert str(obj) == "O=Table, Headers=[node0, null]"


# ---------------------------------------------------------------------------
# The shared helper itself.
# ---------------------------------------------------------------------------


def test_get_array_of_string_is_positional() -> None:
    dictionary = COSDictionary()
    dictionary.set_name("O", "Table")
    array = COSArray()
    array.add(COSName.get_pdf_name("NameValue"))
    array.add(COSString("StringValue"))
    array.add(COSInteger.get(7))
    dictionary.set_item("MixedStrings", array)

    obj = PDTableAttributeObject(dictionary)
    assert obj.get_array_of_string("MixedStrings") == [None, "StringValue", None]


def test_get_array_of_string_missing_key_returns_none() -> None:
    assert PDTableAttributeObject().get_array_of_string("Missing") is None
