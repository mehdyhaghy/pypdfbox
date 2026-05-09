from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_export_format_attribute_object import (
    PDExportFormatAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_list_attribute_object import (
    PDListAttributeObject,
)
from pypdfbox.pdmodel.documentinterchange.taggedpdf.pd_table_attribute_object import (
    PDTableAttributeObject,
)


def test_constructor_with_existing_dictionary_preserves_owner() -> None:
    raw = COSDictionary()
    raw.set_name("O", "HTML-3.2")

    obj = PDExportFormatAttributeObject(raw, owner="CSS-2.00")

    assert obj.get_cos_object() is raw
    assert obj.get_owner() == "HTML-3.2"


def test_constructor_without_dictionary_uses_explicit_or_default_owner() -> None:
    assert PDExportFormatAttributeObject().get_owner() == "XML-1.00"
    assert (
        PDExportFormatAttributeObject(owner="CSS-1.00").get_owner()
        == "CSS-1.00"
    )


def test_get_list_numbering_falls_back_when_name_helper_returns_none() -> None:
    obj = PDExportFormatAttributeObject()
    obj.get_cos_object().set_item(
        PDListAttributeObject.LIST_NUMBERING, COSInteger.get(12)
    )

    assert obj.get_list_numbering() == PDExportFormatAttributeObject.LIST_NUMBERING_NONE


def test_headers_skip_non_string_items_and_decode_latin1_fallback() -> None:
    obj = PDExportFormatAttributeObject()
    array = COSArray()
    array.add(COSString(b"\xff"))
    array.add(COSName.get_pdf_name("IgnoredName"))
    array.add(COSInteger.get(7))
    obj.get_cos_object().set_item(PDTableAttributeObject.HEADERS, array)

    assert obj.get_headers() == ["ÿ"]


def test_set_headers_writes_utf8_cos_strings() -> None:
    obj = PDExportFormatAttributeObject()

    obj.set_headers(["alpha", "café"])

    array = obj.get_cos_object().get_dictionary_object(PDTableAttributeObject.HEADERS)
    assert isinstance(array, COSArray)
    assert [array.get_object(i).get_bytes() for i in range(array.size())] == [
        b"alpha",
        "café".encode(),
    ]


def test_presence_aliases_and_clear_helpers_for_each_export_key() -> None:
    obj = PDExportFormatAttributeObject()
    obj.set_list_numbering(PDExportFormatAttributeObject.LIST_NUMBERING_DECIMAL)
    obj.set_row_span(2)
    obj.set_col_span(3)
    obj.set_headers(["h1"])
    obj.set_scope(PDExportFormatAttributeObject.SCOPE_COLUMN)
    obj.set_summary("summary")

    assert obj.is_list_numbering_specified() is True
    assert obj.has_list_numbering() is True
    assert obj.is_row_span_specified() is True
    assert obj.has_row_span() is True
    assert obj.is_col_span_specified() is True
    assert obj.has_col_span() is True
    assert obj.is_headers_specified() is True
    assert obj.has_headers() is True
    assert obj.is_scope_specified() is True
    assert obj.has_scope() is True
    assert obj.is_summary_specified() is True
    assert obj.has_summary() is True

    obj.clear_list_numbering()
    obj.clear_row_span()
    obj.clear_col_span()
    obj.clear_headers()
    obj.clear_scope()
    obj.clear_summary()

    assert obj.has_list_numbering() is False
    assert obj.has_row_span() is False
    assert obj.has_col_span() is False
    assert obj.has_headers() is False
    assert obj.has_scope() is False
    assert obj.has_summary() is False
    assert obj.get_list_numbering() == PDExportFormatAttributeObject.LIST_NUMBERING_NONE
    assert obj.get_row_span() == 1
    assert obj.get_col_span() == 1
    assert obj.get_headers() == []
    assert obj.get_scope() is None
    assert obj.get_summary() is None


def test_clear_scope_and_summary_remove_raw_entries_even_when_none_set() -> None:
    obj = PDExportFormatAttributeObject()
    obj.set_scope(None)
    obj.set_summary(None)

    obj.clear_scope()
    obj.clear_summary()

    assert obj.get_cos_object().get_dictionary_object(PDTableAttributeObject.SCOPE) is None
    assert (
        obj.get_cos_object().get_dictionary_object(PDTableAttributeObject.SUMMARY)
        is None
    )


def test_repr_reflects_missing_owner_from_existing_dictionary() -> None:
    obj = PDExportFormatAttributeObject(COSDictionary())

    assert repr(obj) == "PDExportFormatAttributeObject(O=None)"
