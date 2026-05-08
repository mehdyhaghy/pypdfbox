from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.measurement import PDNumberFormatDictionary

_C = COSName.get_pdf_name("C")
_F = COSName.get_pdf_name("F")
_FD = COSName.get_pdf_name("FD")
_O = COSName.get_pdf_name("O")
_PS = COSName.get_pdf_name("PS")
_U = COSName.get_pdf_name("U")


def test_typed_presence_helpers_ignore_malformed_number_format_entries() -> None:
    raw = COSDictionary()
    raw.set_item(_C, COSString("not-a-number"))
    raw.set_item(_F, COSArray())
    raw.set_item(_FD, COSString("true"))
    raw.set_item(_O, COSArray())

    number_format = PDNumberFormatDictionary(raw)

    assert number_format.get_conversion_factor() == -1.0
    assert number_format.get_fractional_display() == "D"
    assert number_format.is_fd() is False
    assert number_format.get_label_position_to_value() == "S"

    assert number_format.has_conversion_factor() is False
    assert number_format.has_fractional_display() is False
    assert number_format.has_fd() is False
    assert number_format.has_label_position_to_value() is False


def test_presence_helpers_count_falsy_typed_values_as_present() -> None:
    number_format = PDNumberFormatDictionary()
    number_format.set_units("")
    number_format.set_conversion_factor(0.0)
    number_format.set_fd(False)
    number_format.set_label_prefix_string("")

    assert number_format.has_units() is True
    assert number_format.has_conversion_factor() is True
    assert number_format.has_fd() is True
    assert number_format.has_label_prefix_string() is True


def test_clear_helpers_remove_number_format_entries() -> None:
    number_format = PDNumberFormatDictionary()
    number_format.set_units("m")
    number_format.set_fractional_display("F")
    number_format.set_label_position_to_value("P")
    number_format.set_label_prefix_string("[")

    number_format.clear_units()
    number_format.clear_fractional_display()
    number_format.clear_label_position_to_value()
    number_format.clear_label_prefix_string()

    cos = number_format.get_cos_object()
    assert not cos.contains_key(_U)
    assert not cos.contains_key(_F)
    assert not cos.contains_key(_O)
    assert not cos.contains_key(_PS)
    assert number_format.get_fractional_display() == "D"
    assert number_format.get_label_position_to_value() == "S"
