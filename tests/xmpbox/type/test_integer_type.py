from __future__ import annotations

import pytest

from pypdfbox.xmpbox import (
    BooleanType,
    DateType,
    IntegerType,
    RealType,
    XMPMetadata,
)


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_integer_from_int(metadata: XMPMetadata) -> None:
    i = IntegerType(metadata, "ns", "p", "n", 42)
    assert i.get_value() == 42
    assert i.get_string_value() == "42"


def test_integer_from_string(metadata: XMPMetadata) -> None:
    i = IntegerType(metadata, "ns", "p", "n", "10")
    assert i.get_value() == 10


def test_integer_rejects_garbage(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        IntegerType(metadata, "ns", "p", "n", "Not an int")
    with pytest.raises(ValueError):
        IntegerType(metadata, "ns", "p", "n", 1.5)
    with pytest.raises(ValueError):
        IntegerType(metadata, "ns", "p", "n", True)


def test_real_from_float_and_string(metadata: XMPMetadata) -> None:
    r1 = RealType(metadata, "ns", "p", "n", 1.5)
    r2 = RealType(metadata, "ns", "p", "n", "1.5")
    assert r1.get_value() == 1.5
    assert r2.get_value() == 1.5
    assert "1.5" in r1.get_string_value()


def test_real_rejects_garbage(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        RealType(metadata, "ns", "p", "n", "Not a real")


def test_boolean_from_bool(metadata: XMPMetadata) -> None:
    t = BooleanType(metadata, "ns", "p", "n", True)
    f = BooleanType(metadata, "ns", "p", "n", False)
    assert t.get_value() is True
    assert f.get_value() is False
    assert t.get_string_value() == "True"
    assert f.get_string_value() == "False"


@pytest.mark.parametrize(
    "text,expected",
    [("True", True), ("FALSE", False), ("true", True), ("false", False)],
)
def test_boolean_from_string(metadata: XMPMetadata, text: str, expected: bool) -> None:
    b = BooleanType(metadata, "ns", "p", "n", text)
    assert b.get_value() is expected


def test_boolean_rejects_garbage(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        BooleanType(metadata, "ns", "p", "n", "Not a Boolean")
    with pytest.raises(ValueError):
        BooleanType(metadata, "ns", "p", "n", 1)


def test_date_from_iso_string(metadata: XMPMetadata) -> None:
    d = DateType(metadata, "ns", "p", "n", "2010-03-22T14:33:11+01:00")
    assert d.get_string_value().startswith("2010-03-22T14:33:11")


def test_date_rejects_garbage(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        DateType(metadata, "ns", "p", "n", "Bad Date")
    with pytest.raises(ValueError):
        DateType(metadata, "ns", "p", "n", None)
