from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common import LabelGenerator
from pypdfbox.pdmodel.pd_page_label_range import PDPageLabelRange


def _range(style: str | None = None, prefix: str | None = None, start: int = 1) -> PDPageLabelRange:
    r = PDPageLabelRange()
    if style is not None:
        r.set_style(style)
    if prefix is not None:
        r.set_prefix(prefix)
    r.set_start(start)
    return r


def test_decimal_iterator() -> None:
    gen = LabelGenerator(_range(PDPageLabelRange.STYLE_DECIMAL, start=10), 3)
    assert list(gen) == ["10", "11", "12"]


def test_roman_lower_iterator() -> None:
    gen = LabelGenerator(_range(PDPageLabelRange.STYLE_ROMAN_LOWER), 4)
    assert list(gen) == ["i", "ii", "iii", "iv"]


def test_roman_upper() -> None:
    gen = LabelGenerator(_range(PDPageLabelRange.STYLE_ROMAN_UPPER), 3)
    assert list(gen) == ["I", "II", "III"]


def test_letter_iterator() -> None:
    gen = LabelGenerator(_range(PDPageLabelRange.STYLE_LETTERS_LOWER), 28)
    out = list(gen)
    assert out[0] == "a"
    assert out[25] == "z"
    assert out[26] == "aa"
    assert out[27] == "bb"


def test_letter_upper_iterator() -> None:
    gen = LabelGenerator(_range(PDPageLabelRange.STYLE_LETTERS_UPPER), 2)
    assert list(gen) == ["A", "B"]


def test_prefix_prepends() -> None:
    gen = LabelGenerator(_range(PDPageLabelRange.STYLE_DECIMAL, prefix="X-"), 2)
    assert list(gen) == ["X-1", "X-2"]


def test_prefix_trims_at_nul() -> None:
    gen = LabelGenerator(_range(prefix="A\x00bad"), 1)
    assert list(gen) == ["A"]


def test_has_next_and_next_methods() -> None:
    gen = LabelGenerator(_range(PDPageLabelRange.STYLE_DECIMAL), 1)
    assert gen.has_next()
    assert gen.next() == "1"
    assert not gen.has_next()
    with pytest.raises(StopIteration):
        gen.next()


def test_make_roman_label_4000() -> None:
    assert LabelGenerator.make_roman_label(4000) == "mmmm"


def test_make_letter_label_negative() -> None:
    assert LabelGenerator.make_letter_label(0) == ""


def test_get_number_unknown_style_falls_back_to_decimal() -> None:
    assert LabelGenerator.get_number(5, "bogus") == "5"


def test_get_number_none_style() -> None:
    assert LabelGenerator.get_number(7, None) == "7"
