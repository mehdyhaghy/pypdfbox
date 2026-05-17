"""Wave 1337 coverage-boost tests for :mod:`pypdfbox.pdmodel.interactive.form.pd_field`.

Targets the abstract-method raise paths (``get_value_as_string``,
``set_value``, ``get_widgets``, ``export_fdf``) and the FDF import path
branches (``/Ff`` mutation, ``/SetFf`` mutation, ``/ClrFf`` mutation).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.fdf.fdf_field import FDFField
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_field import PDField


class _BarePDField(PDField):
    """Concrete subclass that does NOT override the abstract methods."""

    def is_terminal(self) -> bool:
        return True


# ---------- abstract-method raises (lines 247, 258, 269, 278) ----------


def test_pd_field_base_get_value_as_string_raises_not_implemented() -> None:
    form = PDAcroForm()
    f = _BarePDField(form)
    with pytest.raises(NotImplementedError):
        f.get_value_as_string()


def test_pd_field_base_set_value_raises_not_implemented() -> None:
    form = PDAcroForm()
    f = _BarePDField(form)
    with pytest.raises(NotImplementedError):
        f.set_value("anything")


def test_pd_field_base_get_widgets_raises_not_implemented() -> None:
    form = PDAcroForm()
    f = _BarePDField(form)
    with pytest.raises(NotImplementedError):
        f.get_widgets()


def test_pd_field_base_export_fdf_raises_not_implemented() -> None:
    form = PDAcroForm()
    f = _BarePDField(form)
    with pytest.raises(NotImplementedError):
        f.export_fdf()


# ---------- get_field_type covers lines 141-144 ----------


def test_pd_field_get_field_type_returns_ft_name() -> None:
    """When ``/FT`` is a COSName, the field type is its string."""
    form = PDAcroForm()
    f = _BarePDField(form)
    f.get_cos_object().set_name(COSName.get_pdf_name("FT"), "Tx")
    assert f.get_field_type() == "Tx"


def test_pd_field_get_field_type_returns_none_when_ft_is_not_name() -> None:
    """When ``/FT`` is missing or not a COSName the type is None."""
    form = PDAcroForm()
    f = _BarePDField(form)
    # Set /FT to an integer (non-name) — falls through to None.
    f.get_cos_object().set_item(
        COSName.get_pdf_name("FT"), COSInteger.get(42)
    )
    assert f.get_field_type() is None


def test_pd_field_get_field_type_returns_none_when_ft_absent() -> None:
    form = PDAcroForm()
    f = _BarePDField(form)
    assert f.get_field_type() is None


# ---------- get_field_flags covers lines 147-152 ----------


def test_pd_field_get_field_flags_returns_zero_when_absent() -> None:
    form = PDAcroForm()
    f = _BarePDField(form)
    assert f.get_field_flags() == 0


def test_pd_field_get_field_flags_returns_int_value() -> None:
    form = PDAcroForm()
    f = _BarePDField(form)
    f.get_cos_object().set_item(
        COSName.get_pdf_name("Ff"), COSInteger.get(0x42)
    )
    assert f.get_field_flags() == 0x42


def test_pd_field_get_field_flags_ignores_non_integer() -> None:
    """``/Ff`` set to a non-integer falls through to 0."""
    form = PDAcroForm()
    f = _BarePDField(form)
    f.get_cos_object().set_name(COSName.get_pdf_name("Ff"), "garbage")
    assert f.get_field_flags() == 0


# ---------- import_fdf /Ff / /SetFf / /ClrFf branches ----------
# Lines 303-304: /Ff path (early return).
# Lines 310-311: /SetFf bit-or.
# Lines 315-317: /ClrFf bit-clear via XOR complement.


def test_pd_field_import_fdf_writes_field_flags_when_ff_present() -> None:
    """An FDF field carrying ``/Ff`` overwrites the PDField's flags."""
    form = PDAcroForm()
    f = _BarePDField(form)
    f.get_cos_object().set_item(
        COSName.get_pdf_name("Ff"), COSInteger.get(0x01)
    )

    fdf_dict = COSDictionary()
    fdf_dict.set_item(COSName.get_pdf_name("Ff"), COSInteger.get(0x80))
    fdf_field = FDFField(fdf_dict)

    f.import_fdf(fdf_field)
    assert f.get_field_flags() == 0x80


def test_pd_field_import_fdf_applies_set_ff_or() -> None:
    """``/SetFf`` ORs additional bits into the existing flag set."""
    form = PDAcroForm()
    f = _BarePDField(form)
    f.set_field_flags(0x01)

    fdf_dict = COSDictionary()
    fdf_dict.set_item(COSName.get_pdf_name("SetFf"), COSInteger.get(0x02))
    fdf_field = FDFField(fdf_dict)

    f.import_fdf(fdf_field)
    assert f.get_field_flags() == (0x01 | 0x02)


def test_pd_field_import_fdf_applies_clr_ff_xor_mask() -> None:
    """``/ClrFf`` clears the bits set in its value (complement-and-AND)."""
    form = PDAcroForm()
    f = _BarePDField(form)
    f.set_field_flags(0x07)  # bits 0, 1, 2 set

    fdf_dict = COSDictionary()
    fdf_dict.set_item(COSName.get_pdf_name("ClrFf"), COSInteger.get(0x02))
    fdf_field = FDFField(fdf_dict)

    f.import_fdf(fdf_field)
    # Bit 1 cleared.
    assert f.get_field_flags() == (0x07 & ~0x02)


def test_pd_field_import_fdf_applies_set_ff_and_clr_ff_together() -> None:
    """Both ``/SetFf`` and ``/ClrFf`` apply in sequence."""
    form = PDAcroForm()
    f = _BarePDField(form)
    f.set_field_flags(0x01)

    fdf_dict = COSDictionary()
    fdf_dict.set_item(COSName.get_pdf_name("SetFf"), COSInteger.get(0x04))
    fdf_dict.set_item(COSName.get_pdf_name("ClrFf"), COSInteger.get(0x01))
    fdf_field = FDFField(fdf_dict)

    f.import_fdf(fdf_field)
    # 0x01 | 0x04 = 0x05, then clear bit 0 → 0x04.
    assert f.get_field_flags() == 0x04


def test_pd_field_import_fdf_with_value_writes_v_entry() -> None:
    """Non-terminal branch: any non-None ``/V`` from the FDF lands as a
    raw COS entry on the PD field."""
    form = PDAcroForm()
    f = _BarePDField(form)

    fdf_dict = COSDictionary()
    fdf_dict.set_string(COSName.get_pdf_name("V"), "hello")
    fdf_field = FDFField(fdf_dict)

    f.import_fdf(fdf_field)
    v = f.get_cos_object().get_dictionary_object(COSName.get_pdf_name("V"))
    assert v is not None
