"""Upstream-mirrored tests for PDNumberFormatDictionary.

Apache PDFBox 3.0.x has no JUnit test for
``org.apache.pdfbox.pdmodel.interactive.measurement.PDNumberFormatDictionary``
(no ``PDNumberFormatDictionaryTest.java`` exists in
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/measurement/``).

We therefore translate behaviour expressed by the upstream class' own Javadoc
contract — defaults, validation, and round-tripping through the wrapped
``COSDictionary`` — into pytest-style tests. Should upstream add a real test
file in the future, this module should be replaced with a direct port.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.measurement import PDNumberFormatDictionary


def test_default_constructor_assigns_type():
    nf = PDNumberFormatDictionary()
    assert nf.get_cos_object().get_name(COSName.TYPE) == PDNumberFormatDictionary.TYPE


def test_wrap_existing_dictionary_preserves_identity():
    src = COSDictionary()
    nf = PDNumberFormatDictionary(src)
    assert nf.get_cos_object() is src


def test_fractional_display_default_d():
    # Javadoc: "F" defaults to FRACTIONAL_DISPLAY_DECIMAL ("D")
    nf = PDNumberFormatDictionary()
    assert nf.get_fractional_display() == "D"


def test_fractional_display_invalid_raises():
    # Javadoc: setFractionalDisplay throws IllegalArgumentException for invalid values.
    nf = PDNumberFormatDictionary()
    with pytest.raises(ValueError):
        nf.set_fractional_display("Z")


def test_fractional_display_null_allowed():
    nf = PDNumberFormatDictionary()
    nf.set_fractional_display(None)  # explicitly allowed
    # After clearing, the getter falls back to default "D".
    assert nf.get_fractional_display() == "D"


def test_label_position_default_suffix():
    # Javadoc: "O" defaults to LABEL_SUFFIX_TO_VALUE ("S")
    nf = PDNumberFormatDictionary()
    assert nf.get_label_position_to_value() == "S"


def test_label_position_invalid_raises():
    nf = PDNumberFormatDictionary()
    with pytest.raises(ValueError):
        nf.set_label_position_to_value("Q")


def test_label_position_null_allowed():
    nf = PDNumberFormatDictionary()
    nf.set_label_position_to_value(None)
    assert nf.get_label_position_to_value() == "S"


def test_thousands_separator_default_comma():
    nf = PDNumberFormatDictionary()
    assert nf.get_thousands_separator() == ","


def test_decimal_separator_default_dot():
    nf = PDNumberFormatDictionary()
    assert nf.get_decimal_separator() == "."


def test_label_prefix_suffix_default_space():
    nf = PDNumberFormatDictionary()
    assert nf.get_label_prefix_string() == " "
    assert nf.get_label_suffix_string() == " "


def test_fd_default_false():
    nf = PDNumberFormatDictionary()
    assert nf.is_fd() is False


def test_setters_round_trip_through_cos():
    nf = PDNumberFormatDictionary()
    nf.set_units("ft")
    nf.set_conversion_factor(0.3048)
    nf.set_fractional_display("R")
    nf.set_denominator(4)
    nf.set_fd(True)
    nf.set_thousands_separator(" ")
    nf.set_decimal_separator(",")
    nf.set_label_prefix_string("(")
    nf.set_label_suffix_string(")")
    nf.set_label_position_to_value("P")

    rebuilt = PDNumberFormatDictionary(nf.get_cos_object())
    assert rebuilt.get_units() == "ft"
    assert rebuilt.get_conversion_factor() == pytest.approx(0.3048)
    assert rebuilt.get_fractional_display() == "R"
    assert rebuilt.get_denominator() == 4
    assert rebuilt.is_fd() is True
    assert rebuilt.get_thousands_separator() == " "
    assert rebuilt.get_decimal_separator() == ","
    assert rebuilt.get_label_prefix_string() == "("
    assert rebuilt.get_label_suffix_string() == ")"
    assert rebuilt.get_label_position_to_value() == "P"
