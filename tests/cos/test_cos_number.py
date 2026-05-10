from __future__ import annotations

import pytest

from pypdfbox.cos import COSFloat, COSInteger, COSNumber


def test_get_returns_integer_for_integral_input() -> None:
    # Integers go through the small-int cache, so identity holds for
    # values in ``-100..256``.
    assert COSNumber.get("0") is COSInteger.ZERO
    assert COSNumber.get("42") is COSInteger.get(42)
    # Outside the cache range we still get a ``COSInteger`` but a fresh one.
    n = COSNumber.get("99999")
    assert isinstance(n, COSInteger)
    assert n.value == 99999


def test_get_treats_dot_dash_empty_as_zero() -> None:
    # PDFBox quirk (PDFBOX-592): trivial sub-token shapes parse to zero
    # instead of raising.
    assert COSNumber.get("") is COSInteger.ZERO
    assert COSNumber.get("-") is COSInteger.ZERO
    assert COSNumber.get(".") is COSInteger.ZERO


def test_get_returns_float_for_decimal_or_exponent() -> None:
    f1 = COSNumber.get("1.5")
    assert isinstance(f1, COSFloat)
    assert f1.value == 1.5

    f2 = COSNumber.get("1e3")
    assert isinstance(f2, COSFloat)
    assert f2.value == 1000.0


def test_get_strips_leading_plus() -> None:
    # ``int('+42')`` works in Python, but Java's ``Long.parseLong("+42")``
    # only accepts the plus sign in newer JDKs; PDFBox strips it. Either way
    # the parse is successful and yields the cached singleton.
    assert COSNumber.get("+42") is COSInteger.get(42)


def test_get_out_of_range_returns_sentinels() -> None:
    too_big = str(2**63)
    too_small = str(-(2**63) - 1)
    assert COSNumber.get(too_big) is COSInteger.OUT_OF_RANGE_MAX
    assert COSNumber.get(too_small) is COSInteger.OUT_OF_RANGE_MIN
    assert COSNumber.get(too_big).is_valid() is False
    assert COSNumber.get(too_small).is_valid() is False


def test_get_rejects_non_numeric() -> None:
    with pytest.raises(OSError):
        COSNumber.get("abc")
    with pytest.raises(OSError):
        COSNumber.get("1.2.3")


def test_get_rejects_none() -> None:
    with pytest.raises((TypeError, AttributeError)):
        COSNumber.get(None)  # type: ignore[arg-type]


def test_abstract_value_methods_raise() -> None:
    """``COSNumber`` itself defines abstract ``*_value`` methods. A subclass
    that forgets to override them must surface ``NotImplementedError``."""

    class _Number(COSNumber):
        def accept(self, visitor: object) -> object:
            return visitor

    n = _Number()
    with pytest.raises(NotImplementedError):
        n.float_value()
    with pytest.raises(NotImplementedError):
        n.int_value()
    with pytest.raises(NotImplementedError):
        n.long_value()
