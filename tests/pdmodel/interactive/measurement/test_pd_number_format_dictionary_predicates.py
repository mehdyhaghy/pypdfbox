"""Predicate helpers and constant tuples on ``PDNumberFormatDictionary``.

These extend the surface beyond the literal upstream port: PDFBox callers
constantly write ``"D".equals(nf.getFractionalDisplay())``, so we expose
typed predicates plus iterable tuples of the valid constants.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.measurement import PDNumberFormatDictionary

# ---------- Constants tuples ----------


def test_fractional_displays_tuple_contents():
    assert PDNumberFormatDictionary.FRACTIONAL_DISPLAYS == ("D", "F", "R", "T")
    # Tuple is immutable so the constant cannot be accidentally mutated.
    assert isinstance(PDNumberFormatDictionary.FRACTIONAL_DISPLAYS, tuple)


def test_label_positions_tuple_contents():
    # Spec order from upstream: suffix is the default, prefix is the alternate.
    assert PDNumberFormatDictionary.LABEL_POSITIONS == ("S", "P")
    assert isinstance(PDNumberFormatDictionary.LABEL_POSITIONS, tuple)


def test_constants_tuples_match_individual_constants():
    cls = PDNumberFormatDictionary
    assert set(cls.FRACTIONAL_DISPLAYS) == {
        cls.FRACTIONAL_DISPLAY_DECIMAL,
        cls.FRACTIONAL_DISPLAY_FRACTION,
        cls.FRACTIONAL_DISPLAY_ROUND,
        cls.FRACTIONAL_DISPLAY_TRUNCATE,
    }
    assert set(cls.LABEL_POSITIONS) == {
        cls.LABEL_PREFIX_TO_VALUE,
        cls.LABEL_SUFFIX_TO_VALUE,
    }


def test_constants_tuples_drive_set_validation():
    # Setter accepts every value in the tuple, no exceptions.
    nf = PDNumberFormatDictionary()
    for value in PDNumberFormatDictionary.FRACTIONAL_DISPLAYS:
        nf.set_fractional_display(value)
        assert nf.get_fractional_display() == value
    for value in PDNumberFormatDictionary.LABEL_POSITIONS:
        nf.set_label_position_to_value(value)
        assert nf.get_label_position_to_value() == value


# ---------- Fractional-display predicates ----------


def test_fractional_display_predicates_default_state():
    # Default (entry absent) falls back to "D" → only the decimal predicate is True.
    nf = PDNumberFormatDictionary()
    assert nf.is_fractional_display_decimal() is True
    assert nf.is_fractional_display_fraction() is False
    assert nf.is_fractional_display_round() is False
    assert nf.is_fractional_display_truncate() is False


@pytest.mark.parametrize(
    ("value", "predicate"),
    [
        ("D", "is_fractional_display_decimal"),
        ("F", "is_fractional_display_fraction"),
        ("R", "is_fractional_display_round"),
        ("T", "is_fractional_display_truncate"),
    ],
)
def test_fractional_display_predicate_only_one_true(value, predicate):
    nf = PDNumberFormatDictionary()
    nf.set_fractional_display(value)

    all_predicates = (
        "is_fractional_display_decimal",
        "is_fractional_display_fraction",
        "is_fractional_display_round",
        "is_fractional_display_truncate",
    )
    for name in all_predicates:
        actual = getattr(nf, name)()
        assert actual is (name == predicate), (
            f"{name}() should be {name == predicate} when /F={value!r}, got {actual}"
        )


def test_fractional_display_predicate_after_clear_falls_back_to_decimal():
    nf = PDNumberFormatDictionary()
    nf.set_fractional_display("F")
    assert nf.is_fractional_display_fraction() is True
    # Clear via None; getter falls back to "D" so decimal predicate becomes True.
    nf.set_fractional_display(None)
    assert nf.is_fractional_display_decimal() is True
    assert nf.is_fractional_display_fraction() is False


# ---------- Label-position predicates ----------


def test_label_position_predicates_default_state():
    # Default (entry absent) falls back to "S" → only the suffix predicate is True.
    nf = PDNumberFormatDictionary()
    assert nf.is_label_suffix_to_value() is True
    assert nf.is_label_prefix_to_value() is False


def test_label_position_predicate_when_prefix():
    nf = PDNumberFormatDictionary()
    nf.set_label_position_to_value("P")
    assert nf.is_label_prefix_to_value() is True
    assert nf.is_label_suffix_to_value() is False


def test_label_position_predicate_when_suffix_explicit():
    nf = PDNumberFormatDictionary()
    nf.set_label_position_to_value("S")
    assert nf.is_label_suffix_to_value() is True
    assert nf.is_label_prefix_to_value() is False


def test_label_position_predicates_mutually_exclusive():
    nf = PDNumberFormatDictionary()
    for value in PDNumberFormatDictionary.LABEL_POSITIONS:
        nf.set_label_position_to_value(value)
        # Exactly one predicate is true at any time.
        assert (
            nf.is_label_prefix_to_value() ^ nf.is_label_suffix_to_value()
        ), f"predicates collided for /O={value!r}"


def test_label_position_predicate_after_clear_falls_back_to_suffix():
    nf = PDNumberFormatDictionary()
    nf.set_label_position_to_value("P")
    assert nf.is_label_prefix_to_value() is True
    nf.set_label_position_to_value(None)
    assert nf.is_label_suffix_to_value() is True
    assert nf.is_label_prefix_to_value() is False
