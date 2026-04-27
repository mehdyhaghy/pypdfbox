from __future__ import annotations

from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDExportFormatAttributeObject,
)


# ---------- defaults ----------


def test_list_numbering_default_is_none_when_absent() -> None:
    obj = PDExportFormatAttributeObject()
    assert obj.get_list_numbering() == PDExportFormatAttributeObject.LIST_NUMBERING_NONE
    assert obj.get_list_numbering() == "None"


def test_row_span_default_is_one_when_absent() -> None:
    obj = PDExportFormatAttributeObject()
    assert obj.get_row_span() == 1


def test_col_span_default_is_one_when_absent() -> None:
    obj = PDExportFormatAttributeObject()
    assert obj.get_col_span() == 1


def test_headers_default_is_empty_list_when_absent() -> None:
    obj = PDExportFormatAttributeObject()
    assert obj.get_headers() == []


def test_scope_default_is_none_when_absent() -> None:
    obj = PDExportFormatAttributeObject()
    assert obj.get_scope() is None


def test_summary_default_is_none_when_absent() -> None:
    obj = PDExportFormatAttributeObject()
    assert obj.get_summary() is None


# ---------- non-default round trips ----------


def test_list_numbering_round_trip_non_default() -> None:
    obj = PDExportFormatAttributeObject()
    obj.set_list_numbering(PDExportFormatAttributeObject.LIST_NUMBERING_DECIMAL)
    assert obj.get_list_numbering() == "Decimal"


def test_list_numbering_round_trip_all_non_default_values() -> None:
    non_default_values = [
        PDExportFormatAttributeObject.LIST_NUMBERING_DISC,
        PDExportFormatAttributeObject.LIST_NUMBERING_CIRCLE,
        PDExportFormatAttributeObject.LIST_NUMBERING_SQUARE,
        PDExportFormatAttributeObject.LIST_NUMBERING_DECIMAL,
        PDExportFormatAttributeObject.LIST_NUMBERING_UPPER_ROMAN,
        PDExportFormatAttributeObject.LIST_NUMBERING_LOWER_ROMAN,
        PDExportFormatAttributeObject.LIST_NUMBERING_UPPER_ALPHA,
        PDExportFormatAttributeObject.LIST_NUMBERING_LOWER_ALPHA,
    ]
    for value in non_default_values:
        obj = PDExportFormatAttributeObject()
        obj.set_list_numbering(value)
        assert obj.get_list_numbering() == value


def test_list_numbering_writes_cos_name() -> None:
    obj = PDExportFormatAttributeObject()
    obj.set_list_numbering(PDExportFormatAttributeObject.LIST_NUMBERING_UPPER_ROMAN)
    raw = obj.get_cos_object().get_dictionary_object("ListNumbering")
    assert isinstance(raw, COSName)
    assert raw.name == "UpperRoman"


def test_row_span_round_trip_non_default() -> None:
    obj = PDExportFormatAttributeObject()
    obj.set_row_span(4)
    assert obj.get_row_span() == 4


def test_col_span_round_trip_non_default() -> None:
    obj = PDExportFormatAttributeObject()
    obj.set_col_span(7)
    assert obj.get_col_span() == 7


def test_headers_round_trip_non_default() -> None:
    obj = PDExportFormatAttributeObject()
    obj.set_headers(["alpha", "beta", "gamma"])
    assert obj.get_headers() == ["alpha", "beta", "gamma"]


def test_set_headers_empty_removes_entry() -> None:
    obj = PDExportFormatAttributeObject()
    obj.set_headers(["x", "y"])
    assert obj.get_cos_object().get_dictionary_object("Headers") is not None
    obj.set_headers([])
    assert obj.get_cos_object().get_dictionary_object("Headers") is None
    assert obj.get_headers() == []


def test_get_headers_decodes_utf8_cos_string() -> None:
    obj = PDExportFormatAttributeObject()
    array = COSArray()
    array.add(COSString("café".encode("utf-8")))
    obj.get_cos_object().set_item("Headers", array)
    assert obj.get_headers() == ["café"]


def test_scope_round_trip_non_default() -> None:
    obj = PDExportFormatAttributeObject()
    obj.set_scope(PDExportFormatAttributeObject.SCOPE_ROW)
    assert obj.get_scope() == "Row"


def test_scope_constants_round_trip() -> None:
    for scope in (
        PDExportFormatAttributeObject.SCOPE_ROW,
        PDExportFormatAttributeObject.SCOPE_COLUMN,
        PDExportFormatAttributeObject.SCOPE_BOTH,
    ):
        obj = PDExportFormatAttributeObject()
        obj.set_scope(scope)
        assert obj.get_scope() == scope


def test_set_scope_writes_cos_name() -> None:
    obj = PDExportFormatAttributeObject()
    obj.set_scope(PDExportFormatAttributeObject.SCOPE_BOTH)
    raw = obj.get_cos_object().get_dictionary_object("Scope")
    assert isinstance(raw, COSName)
    assert raw.name == "Both"


def test_summary_round_trip_non_default() -> None:
    obj = PDExportFormatAttributeObject()
    obj.set_summary("quarterly results")
    assert obj.get_summary() == "quarterly results"


# ---------- repr ----------


def test_repr_includes_owner() -> None:
    obj = PDExportFormatAttributeObject(owner="HTML-4.01")
    assert "HTML-4.01" in repr(obj)
