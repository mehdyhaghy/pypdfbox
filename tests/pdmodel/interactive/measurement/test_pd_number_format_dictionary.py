from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.measurement import PDNumberFormatDictionary


def test_default_constructor_sets_type():
    nf = PDNumberFormatDictionary()
    cos = nf.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name(COSName.TYPE) == "NumberFormat"
    assert nf.get_type() == "NumberFormat"


def test_constructor_with_existing_dictionary():
    src = COSDictionary()
    src.set_string("U", "ft")
    nf = PDNumberFormatDictionary(src)
    assert nf.get_cos_object() is src
    assert nf.get_units() == "ft"


def test_units_round_trip():
    nf = PDNumberFormatDictionary()
    assert nf.get_units() is None
    nf.set_units("meters")
    assert nf.get_units() == "meters"
    nf.set_units(None)
    assert nf.get_units() is None


def test_conversion_factor_round_trip():
    nf = PDNumberFormatDictionary()
    # default for absent key in pypdfbox COSDictionary.get_float is -1.0
    assert nf.get_conversion_factor() == -1.0
    nf.set_conversion_factor(2.54)
    assert nf.get_conversion_factor() == pytest.approx(2.54)


def test_fractional_display_default_is_decimal():
    nf = PDNumberFormatDictionary()
    assert nf.get_fractional_display() == PDNumberFormatDictionary.FRACTIONAL_DISPLAY_DECIMAL


@pytest.mark.parametrize(
    "value",
    [
        PDNumberFormatDictionary.FRACTIONAL_DISPLAY_DECIMAL,
        PDNumberFormatDictionary.FRACTIONAL_DISPLAY_FRACTION,
        PDNumberFormatDictionary.FRACTIONAL_DISPLAY_ROUND,
        PDNumberFormatDictionary.FRACTIONAL_DISPLAY_TRUNCATE,
    ],
)
def test_fractional_display_accepts_valid_values(value):
    nf = PDNumberFormatDictionary()
    nf.set_fractional_display(value)
    assert nf.get_fractional_display() == value


def test_fractional_display_accepts_none():
    nf = PDNumberFormatDictionary()
    nf.set_fractional_display("F")
    assert nf.get_fractional_display() == "F"
    nf.set_fractional_display(None)
    # falls back to default after entry removed
    assert nf.get_fractional_display() == PDNumberFormatDictionary.FRACTIONAL_DISPLAY_DECIMAL


def test_fractional_display_rejects_invalid_values():
    nf = PDNumberFormatDictionary()
    with pytest.raises(ValueError):
        nf.set_fractional_display("X")
    with pytest.raises(ValueError):
        nf.set_fractional_display("")


def test_denominator_round_trip():
    nf = PDNumberFormatDictionary()
    # default for absent key in pypdfbox COSDictionary.get_int is -1
    assert nf.get_denominator() == -1
    nf.set_denominator(8)
    assert nf.get_denominator() == 8


def test_fd_round_trip():
    nf = PDNumberFormatDictionary()
    assert nf.is_fd() is False
    nf.set_fd(True)
    assert nf.is_fd() is True
    nf.set_fd(False)
    assert nf.is_fd() is False


def test_thousands_separator_default_and_override():
    nf = PDNumberFormatDictionary()
    assert nf.get_thousands_separator() == ","
    nf.set_thousands_separator(".")
    assert nf.get_thousands_separator() == "."


def test_decimal_separator_default_and_override():
    nf = PDNumberFormatDictionary()
    assert nf.get_decimal_separator() == "."
    nf.set_decimal_separator(",")
    assert nf.get_decimal_separator() == ","


def test_label_prefix_default_and_override():
    nf = PDNumberFormatDictionary()
    assert nf.get_label_prefix_string() == " "
    nf.set_label_prefix_string(">")
    assert nf.get_label_prefix_string() == ">"


def test_label_suffix_default_and_override():
    nf = PDNumberFormatDictionary()
    assert nf.get_label_suffix_string() == " "
    nf.set_label_suffix_string("<")
    assert nf.get_label_suffix_string() == "<"


def test_label_position_default_is_suffix():
    nf = PDNumberFormatDictionary()
    assert nf.get_label_position_to_value() == PDNumberFormatDictionary.LABEL_SUFFIX_TO_VALUE


@pytest.mark.parametrize(
    "value",
    [
        PDNumberFormatDictionary.LABEL_SUFFIX_TO_VALUE,
        PDNumberFormatDictionary.LABEL_PREFIX_TO_VALUE,
    ],
)
def test_label_position_accepts_valid_values(value):
    nf = PDNumberFormatDictionary()
    nf.set_label_position_to_value(value)
    assert nf.get_label_position_to_value() == value


def test_label_position_accepts_none():
    nf = PDNumberFormatDictionary()
    nf.set_label_position_to_value("P")
    assert nf.get_label_position_to_value() == "P"
    nf.set_label_position_to_value(None)
    # falls back to default after entry removed
    assert nf.get_label_position_to_value() == PDNumberFormatDictionary.LABEL_SUFFIX_TO_VALUE


def test_label_position_rejects_invalid_values():
    nf = PDNumberFormatDictionary()
    with pytest.raises(ValueError):
        nf.set_label_position_to_value("X")
    with pytest.raises(ValueError):
        nf.set_label_position_to_value("")


def test_round_trip_via_cos_dictionary():
    nf = PDNumberFormatDictionary()
    nf.set_units("in")
    nf.set_conversion_factor(0.0254)
    nf.set_fractional_display("F")
    nf.set_denominator(16)
    nf.set_fd(True)
    nf.set_thousands_separator(".")
    nf.set_decimal_separator(",")
    nf.set_label_prefix_string("[")
    nf.set_label_suffix_string("]")
    nf.set_label_position_to_value("P")

    raw = nf.get_cos_object()
    rebuilt = PDNumberFormatDictionary(raw)

    assert rebuilt.get_units() == "in"
    assert rebuilt.get_conversion_factor() == pytest.approx(0.0254)
    assert rebuilt.get_fractional_display() == "F"
    assert rebuilt.get_denominator() == 16
    assert rebuilt.is_fd() is True
    assert rebuilt.get_thousands_separator() == "."
    assert rebuilt.get_decimal_separator() == ","
    assert rebuilt.get_label_prefix_string() == "["
    assert rebuilt.get_label_suffix_string() == "]"
    assert rebuilt.get_label_position_to_value() == "P"
    assert rebuilt.get_type() == "NumberFormat"


def test_constructor_does_not_overwrite_type():
    src = COSDictionary()
    src.set_name(COSName.TYPE, "Other")
    nf = PDNumberFormatDictionary(src)
    # The wrapping ctor should not overwrite an existing /Type when passed a dict.
    assert nf.get_cos_object().get_name(COSName.TYPE) == "Other"


def test_fractional_display_invalid_does_not_mutate_dict():
    # Mirrors upstream: invalid argument throws before any setString call.
    nf = PDNumberFormatDictionary()
    nf.set_fractional_display("F")
    with pytest.raises(ValueError):
        nf.set_fractional_display("X")
    # /F entry survives the rejected call unchanged.
    assert nf.get_fractional_display() == "F"


def test_label_position_invalid_does_not_mutate_dict():
    nf = PDNumberFormatDictionary()
    nf.set_label_position_to_value("P")
    with pytest.raises(ValueError):
        nf.set_label_position_to_value("X")
    # /O entry survives the rejected call unchanged.
    assert nf.get_label_position_to_value() == "P"


def test_units_set_none_clears_entry():
    # Mirrors upstream setString(key, null) which removes the entry.
    nf = PDNumberFormatDictionary()
    nf.set_units("ft")
    assert nf.get_cos_object().contains_key("U")
    nf.set_units(None)
    assert not nf.get_cos_object().contains_key("U")
    assert nf.get_units() is None


def test_thousands_separator_set_none_falls_back_to_default():
    # Setting None clears the entry, so the next read returns the upstream default.
    nf = PDNumberFormatDictionary()
    nf.set_thousands_separator(".")
    nf.set_thousands_separator(None)
    assert not nf.get_cos_object().contains_key("RT")
    assert nf.get_thousands_separator() == ","


def test_decimal_separator_set_none_falls_back_to_default():
    nf = PDNumberFormatDictionary()
    nf.set_decimal_separator(",")
    nf.set_decimal_separator(None)
    assert not nf.get_cos_object().contains_key("RD")
    assert nf.get_decimal_separator() == "."
