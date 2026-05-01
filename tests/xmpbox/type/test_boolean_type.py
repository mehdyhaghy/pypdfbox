from __future__ import annotations

import pytest

from pypdfbox.xmpbox import BooleanType, XMPMetadata


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


def test_boolean_class_constants() -> None:
    assert BooleanType.TRUE == "True"
    assert BooleanType.FALSE == "False"


def test_boolean_from_python_true(metadata: XMPMetadata) -> None:
    b = BooleanType(metadata, "ns", "p", "flag", True)
    assert b.get_value() is True
    assert b.get_string_value() == "True"


def test_boolean_from_python_false(metadata: XMPMetadata) -> None:
    b = BooleanType(metadata, "ns", "p", "flag", False)
    assert b.get_value() is False
    assert b.get_string_value() == "False"


@pytest.mark.parametrize("text", ["True", "TRUE", "true", "  TrUe  "])
def test_boolean_from_string_true(metadata: XMPMetadata, text: str) -> None:
    b = BooleanType(metadata, "ns", "p", "flag", text)
    assert b.get_value() is True
    assert b.get_string_value() == "True"


@pytest.mark.parametrize("text", ["False", "FALSE", "false", "  fAlSe  "])
def test_boolean_from_string_false(metadata: XMPMetadata, text: str) -> None:
    b = BooleanType(metadata, "ns", "p", "flag", text)
    assert b.get_value() is False
    assert b.get_string_value() == "False"


def test_boolean_invalid_string_raises(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        BooleanType(metadata, "ns", "p", "flag", "Not a Boolean")


def test_boolean_invalid_type_raises(metadata: XMPMetadata) -> None:
    with pytest.raises(ValueError):
        BooleanType(metadata, "ns", "p", "flag", 12)


def test_boolean_set_value_replaces(metadata: XMPMetadata) -> None:
    b = BooleanType(metadata, "ns", "p", "flag", True)
    b.set_value("False")
    assert b.get_value() is False
    assert b.get_string_value() == "False"
