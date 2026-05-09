from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.measurement import PDNumberFormatDictionary

_C = COSName.get_pdf_name("C")
_D = COSName.get_pdf_name("D")
_FD = COSName.get_pdf_name("FD")
_RT = COSName.get_pdf_name("RT")
_RD = COSName.get_pdf_name("RD")
_SS = COSName.get_pdf_name("SS")


def test_number_format_remaining_numeric_and_boolean_presence_clearers() -> None:
    number_format = PDNumberFormatDictionary()

    number_format.set_conversion_factor(2.5)
    number_format.set_denominator(16)
    number_format.set_fd(True)

    assert number_format.has_conversion_factor() is True
    assert number_format.has_denominator() is True
    assert number_format.has_fd() is True

    number_format.clear_conversion_factor()
    number_format.clear_denominator()
    number_format.clear_fd()

    cos = number_format.get_cos_object()
    assert not cos.contains_key(_C)
    assert not cos.contains_key(_D)
    assert not cos.contains_key(_FD)
    assert number_format.get_conversion_factor() == -1.0
    assert number_format.get_denominator() == -1
    assert number_format.is_fd() is False


def test_number_format_remaining_separator_and_suffix_presence_clearers() -> None:
    number_format = PDNumberFormatDictionary()

    number_format.set_thousands_separator("'")
    number_format.set_decimal_separator(",")
    number_format.set_label_suffix_string(")")

    assert number_format.has_thousands_separator() is True
    assert number_format.has_decimal_separator() is True
    assert number_format.has_label_suffix_string() is True

    number_format.clear_thousands_separator()
    number_format.clear_decimal_separator()
    number_format.clear_label_suffix_string()

    cos = number_format.get_cos_object()
    assert not cos.contains_key(_RT)
    assert not cos.contains_key(_RD)
    assert not cos.contains_key(_SS)
    assert number_format.get_thousands_separator() == ","
    assert number_format.get_decimal_separator() == "."
    assert number_format.get_label_suffix_string() == " "
