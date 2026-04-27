from __future__ import annotations

from fractions import Fraction

import pytest

from pypdfbox.xmpbox import XMPMetadata
from pypdfbox.xmpbox.type import RationalType, TextType


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_is_text_subclass(metadata: XMPMetadata) -> None:
    rat = RationalType(metadata, "ns", "p", "ratio", "1/2")
    assert isinstance(rat, TextType)
    assert rat.get_string_value() == "1/2"


def test_as_fraction_simple(metadata: XMPMetadata) -> None:
    rat = RationalType(metadata, "ns", "p", "ratio", "3/4")
    assert rat.as_fraction() == Fraction(3, 4)


def test_as_fraction_whole_number(metadata: XMPMetadata) -> None:
    rat = RationalType(metadata, "ns", "p", "ratio", "5")
    assert rat.as_fraction() == Fraction(5, 1)


def test_as_fraction_with_whitespace(metadata: XMPMetadata) -> None:
    rat = RationalType(metadata, "ns", "p", "ratio", " 7 / 8 ")
    assert rat.as_fraction() == Fraction(7, 8)


def test_as_fraction_invalid_returns_none(metadata: XMPMetadata) -> None:
    rat = RationalType(metadata, "ns", "p", "ratio", "abc")
    assert rat.as_fraction() is None


def test_as_fraction_zero_denominator_returns_none(metadata: XMPMetadata) -> None:
    rat = RationalType(metadata, "ns", "p", "ratio", "1/0")
    assert rat.as_fraction() is None


def test_round_trip_value(metadata: XMPMetadata) -> None:
    rat = RationalType(metadata, "ns", "p", "ratio", "1/2")
    assert rat.get_value() == "1/2"
