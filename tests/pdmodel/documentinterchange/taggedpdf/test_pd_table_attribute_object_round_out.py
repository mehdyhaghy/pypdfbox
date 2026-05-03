"""Wave 226 round-out for ``PDTableAttributeObject``.

Covers the gaps relative to upstream ``PDTableAttributeObject``:

* ``__str__`` (toString parity) — appends ``", <FieldName>=<value>"`` for
  each entry the dictionary explicitly writes.
* ``add_header(value)`` — incremental ``/Headers`` append helper.
* ``is_<field>_specified()`` per-key predicate helpers.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSString
from pypdfbox.pdmodel.documentinterchange.taggedpdf import (
    PDTableAttributeObject,
)


# ---------- __str__ / toString parity ----------


def test_str_owner_only() -> None:
    obj = PDTableAttributeObject()
    # No fields written beyond /O — base class provides "O=Table".
    assert str(obj) == "O=Table"


def test_str_appends_row_span_when_specified() -> None:
    obj = PDTableAttributeObject()
    obj.set_row_span(3)
    assert str(obj) == "O=Table, RowSpan=3"


def test_str_appends_col_span_when_specified() -> None:
    obj = PDTableAttributeObject()
    obj.set_col_span(5)
    assert str(obj) == "O=Table, ColSpan=5"


def test_str_appends_scope_when_specified() -> None:
    obj = PDTableAttributeObject()
    obj.set_scope(PDTableAttributeObject.SCOPE_BOTH)
    assert str(obj) == "O=Table, Scope=Both"


def test_str_appends_summary_when_specified() -> None:
    obj = PDTableAttributeObject()
    obj.set_summary("financials Q4")
    assert str(obj) == "O=Table, Summary=financials Q4"


def test_str_appends_headers_via_array_to_string() -> None:
    obj = PDTableAttributeObject()
    obj.set_headers(["h1", "h2", "h3"])
    # Upstream ``arrayToString(String[])`` joins with ", " inside [...].
    assert str(obj) == "O=Table, Headers=[h1, h2, h3]"


def test_str_appends_all_fields_in_upstream_order() -> None:
    obj = PDTableAttributeObject()
    obj.set_summary("summary")  # written first to confirm order is by class, not write
    obj.set_scope("Row")
    obj.set_headers(["h1"])
    obj.set_col_span(2)
    obj.set_row_span(7)
    # Upstream order: O, RowSpan, ColSpan, Headers, Scope, Summary.
    assert str(obj) == (
        "O=Table, RowSpan=7, ColSpan=2, Headers=[h1], Scope=Row, Summary=summary"
    )


def test_str_skips_default_values_that_were_never_written() -> None:
    obj = PDTableAttributeObject()
    # get_row_span / get_col_span return 1 by default but ``__str__`` only
    # appends when ``is_specified`` reports the entry is explicitly written
    # — matching upstream which gates each append behind ``isSpecified``.
    assert obj.get_row_span() == 1
    assert obj.get_col_span() == 1
    assert "RowSpan" not in str(obj)
    assert "ColSpan" not in str(obj)


def test_str_after_explicit_default_write_still_appended() -> None:
    obj = PDTableAttributeObject()
    obj.set_row_span(1)  # explicit write of the default value
    # Upstream ``isSpecified`` only checks dictionary presence, not
    # equality with the default — so an explicit write does append.
    assert "RowSpan=1" in str(obj)


# ---------- add_header ----------


def test_add_header_creates_array_when_absent() -> None:
    obj = PDTableAttributeObject()
    obj.add_header("h1")
    assert obj.get_headers() == ["h1"]
    raw = obj.get_cos_object().get_dictionary_object("Headers")
    assert isinstance(raw, COSArray)


def test_add_header_appends_to_existing_array() -> None:
    obj = PDTableAttributeObject()
    obj.set_headers(["h1", "h2"])
    obj.add_header("h3")
    assert obj.get_headers() == ["h1", "h2", "h3"]


def test_add_header_encodes_utf8() -> None:
    obj = PDTableAttributeObject()
    obj.add_header("café")
    raw = obj.get_cos_object().get_dictionary_object("Headers")
    assert isinstance(raw, COSArray)
    item = raw.get_object(0)
    assert isinstance(item, COSString)
    assert item.get_bytes() == "café".encode("utf-8")
    assert obj.get_headers() == ["café"]


def test_add_header_then_str_uses_array_to_string() -> None:
    obj = PDTableAttributeObject()
    obj.add_header("a")
    obj.add_header("b")
    assert str(obj) == "O=Table, Headers=[a, b]"


# ---------- per-key presence predicates ----------


def test_is_row_span_specified_default_false() -> None:
    obj = PDTableAttributeObject()
    assert obj.is_row_span_specified() is False


def test_is_row_span_specified_true_after_write() -> None:
    obj = PDTableAttributeObject()
    obj.set_row_span(2)
    assert obj.is_row_span_specified() is True


def test_is_col_span_specified_round_trip() -> None:
    obj = PDTableAttributeObject()
    assert obj.is_col_span_specified() is False
    obj.set_col_span(4)
    assert obj.is_col_span_specified() is True


def test_is_headers_specified_round_trip() -> None:
    obj = PDTableAttributeObject()
    assert obj.is_headers_specified() is False
    obj.set_headers(["h1"])
    assert obj.is_headers_specified() is True
    obj.set_headers([])  # empty list removes the entry
    assert obj.is_headers_specified() is False


def test_is_headers_specified_true_after_add_header() -> None:
    obj = PDTableAttributeObject()
    assert obj.is_headers_specified() is False
    obj.add_header("h1")
    assert obj.is_headers_specified() is True


def test_is_scope_specified_round_trip() -> None:
    obj = PDTableAttributeObject()
    assert obj.is_scope_specified() is False
    obj.set_scope("Row")
    assert obj.is_scope_specified() is True
    obj.set_scope(None)  # None removes
    assert obj.is_scope_specified() is False


def test_is_summary_specified_round_trip() -> None:
    obj = PDTableAttributeObject()
    assert obj.is_summary_specified() is False
    obj.set_summary("hello")
    assert obj.is_summary_specified() is True
    obj.set_summary(None)
    assert obj.is_summary_specified() is False


# ---------- defensive: __str__ tolerates wrap of an existing dictionary ----------


def test_str_when_wrapping_pre_built_dictionary() -> None:
    # Build the dictionary first, then wrap. The constructor uses the
    # zero-arg branch when ``dictionary is None``; passing a dictionary
    # leaves the owner untouched, so we set /O explicitly here.
    cos = COSDictionary()
    cos.set_name("O", "Table")
    cos.set_int("RowSpan", 9)
    obj = PDTableAttributeObject(cos)
    assert obj.get_row_span() == 9
    assert "RowSpan=9" in str(obj)
