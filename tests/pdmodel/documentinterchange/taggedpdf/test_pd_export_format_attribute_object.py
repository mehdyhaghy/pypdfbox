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


# ---------- is_valid_owner ----------


def test_is_valid_owner_accepts_all_seven_constants() -> None:
    for owner in (
        PDExportFormatAttributeObject.OWNER_XML_1_00,
        PDExportFormatAttributeObject.OWNER_HTML_3_20,
        PDExportFormatAttributeObject.OWNER_HTML_4_01,
        PDExportFormatAttributeObject.OWNER_OEB_1_00,
        PDExportFormatAttributeObject.OWNER_RTF_1_05,
        PDExportFormatAttributeObject.OWNER_CSS_1_00,
        PDExportFormatAttributeObject.OWNER_CSS_2_00,
    ):
        assert PDExportFormatAttributeObject.is_valid_owner(owner)


def test_is_valid_owner_rejects_unknown_string() -> None:
    assert not PDExportFormatAttributeObject.is_valid_owner("Layout")
    assert not PDExportFormatAttributeObject.is_valid_owner("HTML-5")
    assert not PDExportFormatAttributeObject.is_valid_owner("")


def test_is_valid_owner_rejects_none() -> None:
    assert not PDExportFormatAttributeObject.is_valid_owner(None)


def test_is_valid_owner_aligns_with_factory_dispatch() -> None:
    # Every owner the predicate accepts must also dispatch to
    # PDExportFormatAttributeObject via the PDAttributeObject factory.
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_attribute_object import (
        PDAttributeObject,
    )

    for owner in (
        PDExportFormatAttributeObject.OWNER_XML_1_00,
        PDExportFormatAttributeObject.OWNER_HTML_3_20,
        PDExportFormatAttributeObject.OWNER_HTML_4_01,
        PDExportFormatAttributeObject.OWNER_OEB_1_00,
        PDExportFormatAttributeObject.OWNER_RTF_1_05,
        PDExportFormatAttributeObject.OWNER_CSS_1_00,
        PDExportFormatAttributeObject.OWNER_CSS_2_00,
    ):
        d = COSDictionary()
        d.set_item(COSName.get_pdf_name("O"), COSName.get_pdf_name(owner))
        result = PDAttributeObject.create(d)
        assert isinstance(result, PDExportFormatAttributeObject)
        assert PDExportFormatAttributeObject.is_valid_owner(owner)


# ---------- __str__ / toString parity ----------


def test_str_just_owner_when_no_extra_entries() -> None:
    """Upstream ``toString()`` returns ``"O=<owner>"`` plus whatever the
    layout super-class appends. With no layout entries set, the result is
    exactly ``"O=<owner>"``."""
    obj = PDExportFormatAttributeObject(owner="HTML-4.01")
    assert str(obj) == "O=HTML-4.01"


def test_str_appends_list_numbering_when_specified() -> None:
    obj = PDExportFormatAttributeObject(owner="HTML-4.01")
    obj.set_list_numbering(PDExportFormatAttributeObject.LIST_NUMBERING_DECIMAL)
    assert str(obj) == "O=HTML-4.01, ListNumbering=Decimal"


def test_str_appends_row_span_and_col_span_when_specified() -> None:
    obj = PDExportFormatAttributeObject(owner="HTML-4.01")
    obj.set_row_span(2)
    obj.set_col_span(3)
    assert str(obj) == "O=HTML-4.01, RowSpan=2, ColSpan=3"


def test_str_appends_headers_with_array_to_string_format() -> None:
    obj = PDExportFormatAttributeObject(owner="HTML-4.01")
    obj.set_headers(["alpha", "beta", "gamma"])
    # Mirrors upstream arrayToString — "[a, b, c]" formatting.
    assert str(obj) == "O=HTML-4.01, Headers=[alpha, beta, gamma]"


def test_str_appends_scope_when_specified() -> None:
    obj = PDExportFormatAttributeObject(owner="HTML-4.01")
    obj.set_scope(PDExportFormatAttributeObject.SCOPE_ROW)
    assert str(obj) == "O=HTML-4.01, Scope=Row"


def test_str_appends_summary_when_specified() -> None:
    obj = PDExportFormatAttributeObject(owner="HTML-4.01")
    obj.set_summary("quarterly results")
    assert str(obj) == "O=HTML-4.01, Summary=quarterly results"


def test_str_appends_all_six_in_upstream_order() -> None:
    """Mirror upstream ``PDExportFormatAttributeObject.toString()`` which
    appends ListNumbering, RowSpan, ColSpan, Headers, Scope, Summary in
    that exact order."""
    obj = PDExportFormatAttributeObject(owner="HTML-4.01")
    obj.set_list_numbering(PDExportFormatAttributeObject.LIST_NUMBERING_DECIMAL)
    obj.set_row_span(2)
    obj.set_col_span(3)
    obj.set_headers(["h1", "h2"])
    obj.set_scope(PDExportFormatAttributeObject.SCOPE_BOTH)
    obj.set_summary("summary text")
    assert str(obj) == (
        "O=HTML-4.01, ListNumbering=Decimal, RowSpan=2, ColSpan=3, "
        "Headers=[h1, h2], Scope=Both, Summary=summary text"
    )


def test_str_skips_unspecified_entries() -> None:
    """Only fields that ``is_specified()`` reports are appended — others
    are skipped even when their getter would return a default value."""
    obj = PDExportFormatAttributeObject(owner="HTML-4.01")
    obj.set_row_span(5)  # specified
    obj.set_summary("partial")  # specified
    out = str(obj)
    # Specified entries appear:
    assert "RowSpan=5" in out
    assert "Summary=partial" in out
    # Unspecified entries are skipped even though defaults exist:
    assert "ListNumbering" not in out
    assert "ColSpan" not in out
    assert "Headers" not in out
    assert "Scope" not in out
    # Order: RowSpan precedes Summary:
    assert out.index("RowSpan") < out.index("Summary")


def test_str_inherits_layout_attributes_from_super() -> None:
    """Since upstream extends ``PDLayoutAttributeObject``, the layout-level
    fields (e.g. ``Placement``) appear in ``__str__`` output before the
    six ExportFormat-specific fields."""
    from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
        PDLayoutAttributeObject,
    )

    obj = PDExportFormatAttributeObject(owner="HTML-4.01")
    obj._set_name(PDLayoutAttributeObject.PLACEMENT, "Block")
    obj.set_row_span(4)
    out = str(obj)
    assert "Placement=Block" in out
    assert "RowSpan=4" in out
    # Layout-level fields appear before ExportFormat-specific fields.
    assert out.index("Placement") < out.index("RowSpan")
