"""Tests for :class:`FieldFlag`."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName
from pypdfbox.debugger.flagbitspane.field_flag import FieldFlag

_FF = COSName.get_pdf_name("Ff")
_FT = COSName.get_pdf_name("FT")
_TX = COSName.get_pdf_name("Tx")
_BTN = COSName.get_pdf_name("Btn")
_CH = COSName.get_pdf_name("Ch")


def _field_dict(field_type: COSName | None, flag_value: int) -> COSDictionary:
    d = COSDictionary()
    if field_type is not None:
        d.set_item(_FT, field_type)
    d.set_item(_FF, COSInteger.get(flag_value))
    return d


@pytest.mark.parametrize(
    "field_type,expected",
    [
        (_TX, "Text field flag"),
        (_BTN, "Button field flag"),
        (_CH, "Choice field flag"),
        (None, "Field flag"),
    ],
)
def test_flag_type_dispatch(field_type, expected):
    assert FieldFlag(_field_dict(field_type, 0)).get_flag_type() == expected


def test_flag_value_string():
    assert FieldFlag(_field_dict(_TX, 13)).get_flag_value() == "Flag value: 13"


def test_text_field_table_shape():
    rows = FieldFlag(_field_dict(_TX, 0)).get_flag_bits()
    positions = [r[0] for r in rows]
    assert positions == [1, 2, 3, 13, 14, 21, 23, 24, 25, 26]
    assert [r[1] for r in rows] == [
        "ReadOnly",
        "Required",
        "NoExport",
        "Multiline",
        "Password",
        "FileSelect",
        "DoNotSpellCheck",
        "DoNotScroll",
        "Comb",
        "RichText",
    ]


def test_button_field_table_shape():
    rows = FieldFlag(_field_dict(_BTN, 0)).get_flag_bits()
    assert [r[0] for r in rows] == [1, 2, 3, 15, 16, 17, 26]


def test_choice_field_table_shape():
    rows = FieldFlag(_field_dict(_CH, 0)).get_flag_bits()
    assert [r[0] for r in rows] == [1, 2, 3, 18, 19, 20, 22, 23, 27]


def test_generic_field_table_shape():
    rows = FieldFlag(_field_dict(None, 0)).get_flag_bits()
    assert [r[0] for r in rows] == [1, 2, 3]


def test_text_field_specific_bit_only():
    # /Ff bit 14 == Password
    rows = FieldFlag(_field_dict(_TX, 1 << 13)).get_flag_bits()
    flags = {r[1]: r[2] for r in rows}
    assert flags["Password"] is True
    assert flags["Multiline"] is False
    assert flags["ReadOnly"] is False


def test_button_radio_bit():
    # bit 16 == Radio
    rows = FieldFlag(_field_dict(_BTN, 1 << 15)).get_flag_bits()
    flags = {r[1]: r[2] for r in rows}
    assert flags["Radio"] is True
    assert flags["Pushbutton"] is False
