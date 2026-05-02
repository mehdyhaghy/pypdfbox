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


def test_values_returns_all_members_in_declaration_order() -> None:
    """``PageLayout.values()`` mirrors Java's enum ``values()``: a list of all
    members in declaration order, equivalent to ``list(PageLayout)``."""
    members = PageLayout.values()
    assert isinstance(members, list)
    assert members == list(PageLayout)
    assert members[0] is PageLayout.SINGLE_PAGE
    assert members[-1] is PageLayout.TWO_PAGE_RIGHT
    # Every call returns a fresh list — mutation must not leak.
    members.append(PageLayout.SINGLE_PAGE)  # type: ignore[arg-type]
    assert len(PageLayout.values()) == 6


def test_str_returns_pdf_string_value() -> None:
    """StrEnum's ``__str__`` is the underlying PDF name string, not the
    Pythonic identifier — so ``str(PageLayout.TWO_COLUMN_LEFT) ==
    'TwoColumnLeft'``."""
    assert str(PageLayout.TWO_COLUMN_LEFT) == "TwoColumnLeft"
    assert str(PageLayout.SINGLE_PAGE) == "SinglePage"
