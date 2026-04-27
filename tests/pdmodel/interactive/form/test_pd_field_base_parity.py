from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_field import PDField
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_T = COSName.get_pdf_name("T")
_TU = COSName.get_pdf_name("TU")
_TM = COSName.get_pdf_name("TM")
_FF = COSName.get_pdf_name("Ff")


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
