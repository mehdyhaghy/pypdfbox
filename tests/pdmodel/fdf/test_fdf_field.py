from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.fdf import FDFField


def test_default_constructor_is_empty() -> None:
    f = FDFField()
    assert isinstance(f.get_cos_object(), COSDictionary)
    assert f.get_partial_field_name() is None
    assert f.get_value() is None
    assert f.get_kids() is None


def test_partial_field_name_round_trip() -> None:
    f = FDFField()
    f.set_partial_field_name("first_name")
    assert f.get_partial_field_name() == "first_name"


def test_string_value_round_trip() -> None:
    f = FDFField()
    f.set_value("Alice")
    assert f.get_value() == "Alice"
    # Underlying COS storage uses COSString.
    raw = f.get_cos_object().get_dictionary_object(COSName.get_pdf_name("V"))
    assert isinstance(raw, COSString)


def test_value_none_removes_entry() -> None:
    f = FDFField()
    f.set_value("x")
    f.set_value(None)
    assert f.get_value() is None
    assert not f.get_cos_object().contains_key(COSName.get_pdf_name("V"))


def test_value_list_round_trip_for_multiselect() -> None:
    f = FDFField()
    f.set_value(["a", "b", "c"])
    assert f.get_value() == ["a", "b", "c"]


def test_value_cos_name_passthrough() -> None:
    """Buttons store the on-state as a /Name (e.g. /Yes, /Off)."""
    f = FDFField()
    f.set_value(COSName.get_pdf_name("Yes"))
    assert f.get_value() == "Yes"


def test_value_invalid_type_raises() -> None:
    f = FDFField()
    with pytest.raises(TypeError):
        f.set_value(object())


def test_default_value_round_trip() -> None:
    f = FDFField()
    f.set_default_value("default")
    assert f.get_default_value() == "default"
    f.set_default_value(None)
    assert f.get_default_value() is None


def test_kids_round_trip_returns_wrappers() -> None:
    parent = FDFField()
    parent.set_partial_field_name("address")
    child_a = FDFField()
    child_a.set_partial_field_name("street")
    child_b = FDFField()
    child_b.set_partial_field_name("city")
    parent.set_kids([child_a, child_b])
    kids = parent.get_kids()
    assert kids is not None and len(kids) == 2
    assert kids[0].get_partial_field_name() == "street"
    assert kids[1].get_partial_field_name() == "city"


def test_kids_none_removes_entry() -> None:
    f = FDFField()
    f.set_kids([FDFField()])
    f.set_kids(None)
    assert f.get_kids() is None


def test_mapping_name_round_trip() -> None:
    f = FDFField()
    f.set_mapping_name("Mapped")
    assert f.get_mapping_name() == "Mapped"


def test_field_flags_default_zero() -> None:
    f = FDFField()
    assert f.get_field_flags() == 0
    f.set_field_flags(0b1010)
    assert f.get_field_flags() == 0b1010


def test_set_clear_field_flags_round_trip() -> None:
    f = FDFField()
    f.set_set_field_flags(1)
    f.set_clear_field_flags(2)
    assert f.get_set_field_flags() == 1
    assert f.get_clear_field_flags() == 2


def test_widget_field_flags_round_trip() -> None:
    f = FDFField()
    f.set_widget_field_flags(4)
    f.set_set_widget_field_flags(8)
    f.set_clear_widget_field_flags(16)
    assert f.get_widget_field_flags() == 4
    assert f.get_set_widget_field_flags() == 8
    assert f.get_clear_widget_field_flags() == 16


def test_options_returns_none_when_absent() -> None:
    f = FDFField()
    assert f.get_options() is None


def test_options_string_round_trip() -> None:
    f = FDFField()
    f.set_options(["one", "two"])

    assert f.has_options()
    assert f.get_options() == ["one", "two"]
    raw = f.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Opt"))
    assert isinstance(raw, COSArray)
    assert isinstance(raw.get_object(0), COSString)


def test_options_pair_round_trip() -> None:
    f = FDFField()
    f.set_options([("export", "display")])

    assert f.get_options() == [["export", "display"]]
    raw = f.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Opt"))
    assert isinstance(raw, COSArray)
    pair = raw.get_object(0)
    assert isinstance(pair, COSArray)
    assert pair.get_string(0) == "export"
    assert pair.get_string(1) == "display"


def test_options_none_removes_entry() -> None:
    f = FDFField()
    f.set_options(["one"])

    f.set_options(None)

    assert f.get_options() is None
    assert not f.has_options()
    assert not f.get_cos_object().contains_key(COSName.get_pdf_name("Opt"))


def test_options_rejects_invalid_entry() -> None:
    f = FDFField()

    with pytest.raises(TypeError, match="options must be"):
        f.set_options([object()])

    with pytest.raises(TypeError, match="option pairs"):
        f.set_options([["only-one"]])
