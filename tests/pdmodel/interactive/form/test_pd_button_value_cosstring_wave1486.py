"""Wave 1486 — PDButton value-reader parity for non-COSName /V and /DV tokens.

Pins the oracle-confirmed behaviour that ``PDButton.get_value`` and
``PDButton.get_default_value`` only read an ``instanceof COSName`` token.
A COSString (or any non-name) ``/V`` reads back as the default ``"Off"``;
a COSString ``/DV`` reads back as ``""``. This mirrors upstream
``PDButton.getValue`` (PDButton.java line 105) and
``PDButton.getDefaultValue`` (PDButton.java line 205).

PDFBox 3.0.7 oracle output (ButtonValProbe)::

    getValue(COSString V)=[Off]
    getDefaultValue(COSString DV)=[]
    getValue(no V)=[Off]
    getValue(COSName Yes)=[Yes]
"""
from __future__ import annotations

from pypdfbox.cos import COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox

_V = COSName.get_pdf_name("V")
_DV = COSName.get_pdf_name("DV")


def test_get_value_cosstring_reads_off() -> None:
    button = PDButton(PDAcroForm())
    button.get_cos_object().set_item(_V, COSString("string-value"))
    # has_value still detects the COSString token...
    assert button.has_value()
    # ...but the value reader mirrors upstream: only COSName is read.
    assert button.get_value() == "Off"


def test_get_default_value_cosstring_reads_empty() -> None:
    button = PDButton(PDAcroForm())
    button.get_cos_object().set_item(_DV, COSString("default-value"))
    assert button.has_default_value()
    assert button.get_default_value() == ""


def test_get_value_missing_reads_off() -> None:
    button = PDButton(PDAcroForm())
    assert button.get_value() == "Off"


def test_get_value_cosname_is_read() -> None:
    button = PDButton(PDAcroForm())
    button.get_cos_object().set_name(_V, "Yes")
    assert button.get_value() == "Yes"


def test_check_box_cosstring_value_reads_off() -> None:
    check_box = PDCheckBox(PDAcroForm())
    check_box.get_cos_object().set_item(_V, COSString("Yes"))
    assert check_box.get_value() == "Off"
    assert check_box.get_value_as_string() == "Off"
