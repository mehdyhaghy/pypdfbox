"""Wave 1273: parity coverage for ``ASCIIHexFilter.is_whitespace`` and
``ASCIIHexFilter.is_eod`` static helpers (promoted from the upstream
private statics ``isWhitespace`` / ``isEOD``)."""

from __future__ import annotations

import pytest

from pypdfbox.filter.ascii_hex_filter import ASCIIHexFilter


@pytest.mark.parametrize("byte_value", [0, 9, 10, 12, 13, 32])
def test_is_whitespace_recognises_pdf_whitespace_bytes(byte_value: int) -> None:
    assert ASCIIHexFilter.is_whitespace(byte_value) is True


@pytest.mark.parametrize(
    "byte_value",
    [
        1,
        8,
        11,
        14,
        31,
        33,
        ord("0"),
        ord("9"),
        ord("A"),
        ord("F"),
        ord("a"),
        ord("f"),
        ord(">"),
        255,
    ],
)
def test_is_whitespace_rejects_non_whitespace_bytes(byte_value: int) -> None:
    assert ASCIIHexFilter.is_whitespace(byte_value) is False


def test_is_whitespace_handles_java_eof_sentinel() -> None:
    # Upstream ``isWhitespace`` is called on a Java ``int`` that may be
    # ``-1`` after ``InputStream.read()`` returns EOF; the switch falls
    # through to ``default: return false``. Mirror that contract.
    assert ASCIIHexFilter.is_whitespace(-1) is False


def test_is_eod_marker_is_greater_than() -> None:
    assert ASCIIHexFilter.is_eod(ord(">")) is True


@pytest.mark.parametrize(
    "byte_value",
    [0, ord("<"), ord("="), ord("?"), ord("0"), ord("F"), ord("a"), 255, -1],
)
def test_is_eod_rejects_non_marker_bytes(byte_value: int) -> None:
    assert ASCIIHexFilter.is_eod(byte_value) is False


def test_is_whitespace_is_static() -> None:
    # Callable both on the class and an instance — matches Java's
    # ``private static`` semantics once promoted.
    assert ASCIIHexFilter.is_whitespace(32) is True
    assert ASCIIHexFilter().is_whitespace(32) is True


def test_is_eod_is_static() -> None:
    assert ASCIIHexFilter.is_eod(0x3E) is True
    assert ASCIIHexFilter().is_eod(0x3E) is True
