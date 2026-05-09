from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.documentinterchange.taggedpdf import PDTableAttributeObject


def test_headers_decode_latin1_fallback_and_skip_non_strings() -> None:
    dictionary = COSDictionary()
    dictionary.set_name("O", "Table")
    headers = COSArray()
    headers.add(COSString(b"\xff"))
    headers.add(COSName.get_pdf_name("Ignored"))
    dictionary.set_item("Headers", headers)

    obj = PDTableAttributeObject(dictionary)

    assert obj.get_headers() == ["ÿ"]
    assert str(obj) == "O=Table, Headers=[ÿ]"


def test_clear_helpers_remove_written_values_and_aliases_track_presence() -> None:
    obj = PDTableAttributeObject()
    obj.set_row_span(2)
    obj.set_col_span(3)
    obj.set_headers(["h1"])
    obj.set_scope(PDTableAttributeObject.SCOPE_ROW)
    obj.set_summary("summary")

    assert obj.has_row_span() is True
    assert obj.has_col_span() is True
    assert obj.has_headers() is True
    assert obj.has_scope() is True
    assert obj.has_summary() is True

    obj.clear_row_span()
    obj.clear_col_span()
    obj.clear_headers()
    obj.clear_scope()
    obj.clear_summary()

    assert obj.has_row_span() is False
    assert obj.has_col_span() is False
    assert obj.has_headers() is False
    assert obj.has_scope() is False
    assert obj.has_summary() is False
    assert obj.get_row_span() == 1
    assert obj.get_col_span() == 1
    assert obj.get_headers() == []
    assert obj.get_scope() is None
    assert obj.get_summary() is None
    assert str(obj) == "O=Table"


def test_set_headers_empty_removes_entry_after_existing_value() -> None:
    obj = PDTableAttributeObject()
    obj.set_headers(["h1", "h2"])

    obj.set_headers([])

    assert obj.get_headers() == []
    assert obj.has_headers() is False
    assert obj.get_cos_object().get_dictionary_object("Headers") is None


def test_constants_owner_and_repr_reflect_current_values() -> None:
    obj = PDTableAttributeObject()
    obj.set_row_span(4)
    obj.set_col_span(5)

    assert PDTableAttributeObject.OWNER_TABLE == "Table"
    assert PDTableAttributeObject.OWNER == "Table"
    assert PDTableAttributeObject.SCOPE_COLUMN == "Column"
    assert repr(obj) == "PDTableAttributeObject(O=Table, RowSpan=4, ColSpan=5)"
