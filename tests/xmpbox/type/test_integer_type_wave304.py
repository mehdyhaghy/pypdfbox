from __future__ import annotations

import pytest

from pypdfbox.xmpbox import IntegerType, XMPMetadata


@pytest.fixture
def metadata() -> XMPMetadata:
    return XMPMetadata.create_xmp_metadata()


@pytest.mark.parametrize("text,expected", [("+7", 7), ("-7", -7), ("0", 0)])
def test_integer_string_accepts_java_decimal_syntax(
    metadata: XMPMetadata, text: str, expected: int
) -> None:
    field = IntegerType(metadata, "ns", "p", "count", text)

    assert field.get_value() == expected
    assert field.get_string_value() == str(expected)


@pytest.mark.parametrize("text", [" 7", "7 ", "1_000", "", "+", "-", "１２"])
def test_integer_string_rejects_non_java_decimal_syntax(
    metadata: XMPMetadata, text: str
) -> None:
    with pytest.raises(ValueError):
        IntegerType(metadata, "ns", "p", "count", text)
