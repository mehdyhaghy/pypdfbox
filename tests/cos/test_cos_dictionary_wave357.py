from __future__ import annotations

import pytest

from pypdfbox.cos import COSBoolean, COSDictionary, COSFloat, COSInteger, COSName, COSNull


def test_wave357_numeric_and_boolean_getters_accept_second_key() -> None:
    dictionary = COSDictionary(
        [
            ("Width", COSInteger.get(640)),
            ("Height", COSFloat(12.5)),
            ("Revision", COSInteger.get(2**40)),
            ("Enabled", COSBoolean.TRUE),
        ]
    )

    assert dictionary.get_int("W", "Width") == 640
    assert dictionary.get_float("H", "Height") == pytest.approx(12.5)
    assert dictionary.get_long("R", COSName.get_pdf_name("Revision")) == 2**40
    assert dictionary.get_boolean("Flag", "Enabled") is True

    assert dictionary.getInt("W", "Width") == 640
    assert dictionary.getFloat("H", "Height") == pytest.approx(12.5)
    assert dictionary.getLong("R", "Revision") == 2**40
    assert dictionary.getBoolean("Flag", "Enabled") is True


def test_wave357_second_key_getters_use_explicit_default_when_both_missing() -> None:
    dictionary = COSDictionary()

    assert dictionary.get_int("Missing", "AlsoMissing") == -1
    assert dictionary.get_int("Missing", "AlsoMissing", 7) == 7
    assert dictionary.get_long("Missing", "AlsoMissing", 8) == 8
    assert dictionary.get_float("Missing", "AlsoMissing", 1.25) == pytest.approx(1.25)
    assert dictionary.get_boolean("Missing", "AlsoMissing", True) is True


def test_wave357_second_key_getters_preserve_first_key_precedence() -> None:
    dictionary = COSDictionary(
        [
            ("FirstInt", COSFloat(2.9)),
            ("FirstWrongShape", COSName.get_pdf_name("NotANumber")),
            ("FirstNull", COSNull.NULL),
            ("Fallback", COSInteger.get(5)),
        ]
    )

    assert dictionary.get_int("FirstInt", "Fallback") == 2
    assert dictionary.get_int("FirstWrongShape", "Fallback", 9) == 9
    assert dictionary.get_int("FirstNull", "Fallback") == 5
