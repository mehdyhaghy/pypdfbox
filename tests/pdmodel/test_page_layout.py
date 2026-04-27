from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.page_layout import PageLayout


def test_string_value_round_trip() -> None:
    for member in PageLayout:
        assert PageLayout.from_string(member.string_value()) is member


def test_known_pdf_name_strings() -> None:
    expected = {
        "SinglePage",
        "OneColumn",
        "TwoColumnLeft",
        "TwoColumnRight",
        "TwoPageLeft",
        "TwoPageRight",
    }
    assert {m.string_value() for m in PageLayout} == expected


def test_str_enum_compares_equal_to_string() -> None:
    # ``StrEnum`` keeps back-compat with callers that expect plain strings.
    assert PageLayout.ONE_COLUMN == "OneColumn"
    assert PageLayout.SINGLE_PAGE == "SinglePage"


def test_to_cos_name_returns_canonical_name() -> None:
    name = PageLayout.TWO_COLUMN_LEFT.to_cos_name()
    assert isinstance(name, COSName)
    assert name.get_name() == "TwoColumnLeft"


def test_from_string_unknown_raises() -> None:
    with pytest.raises(ValueError):
        PageLayout.from_string("NotARealLayout")


def test_from_string_empty_raises() -> None:
    with pytest.raises(ValueError):
        PageLayout.from_string("")
