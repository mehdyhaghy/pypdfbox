"""Tests for :class:`FontFormat`.

Mirrors the surface of upstream
``org.apache.pdfbox.pdmodel.font.FontFormat`` — three enum members,
identity comparable, ``str`` formatting that matches Java's enum
``toString()`` output.
"""

from __future__ import annotations

from pypdfbox.fontbox.font_format import FontFormat


def test_three_members_exist() -> None:
    assert {FontFormat.TTF, FontFormat.OTF, FontFormat.PFB} == set(FontFormat)


def test_str_returns_member_name_for_each() -> None:
    # Matches upstream Java ``Enum.toString()`` output ("TTF", "OTF",
    # "PFB"). FontInfo.__str__ depends on this exact spelling.
    assert str(FontFormat.TTF) == "TTF"
    assert str(FontFormat.OTF) == "OTF"
    assert str(FontFormat.PFB) == "PFB"


def test_identity_comparison_works() -> None:
    assert FontFormat.TTF is FontFormat.TTF  # noqa: PLR0124 - identity check
    assert FontFormat.OTF is not FontFormat.TTF


def test_repr_is_informative() -> None:
    # Standard Enum repr — covered to lock the spelling so any future
    # reformatting that breaks tooling output is caught.
    assert "TTF" in repr(FontFormat.TTF)


def test_value_is_uppercase_format_name() -> None:
    assert FontFormat.TTF.value == "TTF"
    assert FontFormat.OTF.value == "OTF"
    assert FontFormat.PFB.value == "PFB"
