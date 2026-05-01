from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_field import PDField
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_T = COSName.get_pdf_name("T")
_TU = COSName.get_pdf_name("TU")
_TM = COSName.get_pdf_name("TM")
_FF = COSName.get_pdf_name("Ff")
_KIDS = COSName.get_pdf_name("Kids")
_V = COSName.get_pdf_name("V")


def _make_field() -> PDTextField:
    """PDField is abstract; PDTextField is the simplest concrete subclass."""
    return PDTextField(PDAcroForm())


# ---------- /Ff bit accessors ----------


def test_is_read_only_default_false() -> None:
    f = _make_field()
    assert f.is_read_only() is False
    assert f.get_field_flags() == 0


def test_set_read_only_round_trip() -> None:
    f = _make_field()
    f.set_read_only(True)
    assert f.is_read_only() is True
    assert f.get_field_flags() & PDField.FLAG_READ_ONLY
    assert f.get_cos_object().get_int(_FF) & 1

    f.set_read_only(False)
    assert f.is_read_only() is False
    assert (f.get_field_flags() & PDField.FLAG_READ_ONLY) == 0


def test_is_required_default_false() -> None:
    f = _make_field()
    assert f.is_required() is False


def test_set_required_round_trip() -> None:
    f = _make_field()
    f.set_required(True)
    assert f.is_required() is True
    assert f.get_field_flags() & PDField.FLAG_REQUIRED
    assert f.get_cos_object().get_int(_FF) & 2

    f.set_required(False)
    assert f.is_required() is False
    assert (f.get_field_flags() & PDField.FLAG_REQUIRED) == 0


def test_is_no_export_default_false() -> None:
    f = _make_field()
    assert f.is_no_export() is False


def test_set_no_export_round_trip() -> None:
    f = _make_field()
    f.set_no_export(True)
    assert f.is_no_export() is True
    assert f.get_field_flags() & PDField.FLAG_NO_EXPORT
    assert f.get_cos_object().get_int(_FF) & 4

    f.set_no_export(False)
    assert f.is_no_export() is False
    assert (f.get_field_flags() & PDField.FLAG_NO_EXPORT) == 0


def test_flag_bits_independent() -> None:
    """Setting one bit must not clobber the others."""
    f = _make_field()
    f.set_read_only(True)
    f.set_required(True)
    f.set_no_export(True)
    assert f.is_read_only() is True
    assert f.is_required() is True
    assert f.is_no_export() is True
    assert f.get_field_flags() == (1 | 2 | 4)

    f.set_required(False)
    assert f.is_read_only() is True
    assert f.is_required() is False
    assert f.is_no_export() is True
    assert f.get_field_flags() == (1 | 4)


def test_set_field_flags_overwrite() -> None:
    f = _make_field()
    f.set_field_flags(1 | 4)
    assert f.is_read_only() is True
    assert f.is_required() is False
    assert f.is_no_export() is True


# ---------- /TU alternate field name ----------


def test_alternate_field_name_default_none() -> None:
    f = _make_field()
    assert f.get_alternate_field_name() is None


def test_alternate_field_name_round_trip() -> None:
    f = _make_field()
    f.set_alternate_field_name("First Name")
    assert f.get_alternate_field_name() == "First Name"
    assert f.get_cos_object().get_string(_TU) == "First Name"


# ---------- /TM mapping name ----------


def test_mapping_name_default_none() -> None:
    f = _make_field()
    assert f.get_mapping_name() is None


def test_mapping_name_round_trip() -> None:
    f = _make_field()
    f.set_mapping_name("user.firstName")
    assert f.get_mapping_name() == "user.firstName"
    assert f.get_cos_object().get_string(_TM) == "user.firstName"


# ---------- /T partial name ----------


def test_partial_name_default_none() -> None:
    f = _make_field()
    assert f.get_partial_name() is None


def test_partial_name_round_trip() -> None:
    f = _make_field()
    f.set_partial_name("firstName")
    assert f.get_partial_name() == "firstName"
    assert f.get_cos_object().get_string(_T) == "firstName"


# ---------- /T period rejection (upstream IllegalArgumentException parity) ----------


def test_set_partial_name_with_period_raises() -> None:
    f = _make_field()
    with pytest.raises(ValueError, match="period character"):
        f.set_partial_name("first.last")


def test_set_partial_name_none_does_not_raise() -> None:
    f = _make_field()
    # Upstream PDFieldTest.testSetPartialNameNull asserts no throw on null.
    f.set_partial_name(None)
    assert f.get_partial_name() is None


# ---------- equality / hash (mirror upstream equals/hashCode) ----------


def test_eq_self() -> None:
    f = _make_field()
    assert f == f


def test_eq_same_dictionary() -> None:
    form = PDAcroForm()
    a = PDTextField(form)
    a.set_partial_name("shared")
    # Wrap the same COSDictionary in a fresh PDTextField; upstream equals is
    # defined as backing-dictionary equality.
    b = PDTextField(form, a.get_cos_object(), None)
    assert a == b
    assert hash(a) == hash(b)


def test_eq_different_dictionaries() -> None:
    form = PDAcroForm()
    a = PDTextField(form)
    b = PDTextField(form)
    a.set_partial_name("a")
    b.set_partial_name("b")
    assert a != b


def test_eq_against_non_field_returns_false() -> None:
    f = _make_field()
    assert f != "not a field"
    assert f != 42
    assert f != None  # noqa: E711  — explicit comparison to None


# ---------- __str__ / toString parity ----------


def test_str_includes_class_and_partial_name() -> None:
    f = _make_field()
    f.set_partial_name("myField")
    s = str(f)
    assert "PDTextField" in s
    assert "myField" in s
    assert "type:" in s
    assert "value:" in s


def test_str_includes_inheritable_value() -> None:
    f = _make_field()
    f.set_partial_name("withValue")
    f.get_cos_object().set_item(_V, COSString("hello"))
    s = str(f)
    assert "hello" in s


# ---------- find_kid (upstream package-private parity) ----------


def test_find_kid_returns_none_when_no_kids() -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.set_partial_name("root")
    assert parent.find_kid(["leaf"], 0) is None


def test_find_kid_single_level() -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.set_partial_name("root")

    child_dict = COSDictionary()
    child_dict.set_string(_T, "leaf")
    child_dict.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Tx"))
    parent.get_cos_object().set_item(_KIDS, COSArray([child_dict]))

    found = parent.find_kid(["leaf"], 0)
    assert found is not None
    assert found.get_partial_name() == "leaf"


def test_find_kid_no_match_returns_none() -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.set_partial_name("root")

    child_dict = COSDictionary()
    child_dict.set_string(_T, "leaf")
    child_dict.set_item(COSName.get_pdf_name("FT"), COSName.get_pdf_name("Tx"))
    parent.get_cos_object().set_item(_KIDS, COSArray([child_dict]))

    assert parent.find_kid(["missing"], 0) is None
