"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSNumber.java

Upstream is an abstract base test class (``TestCOSNumber`` extends
``TestCOSBase``); the concrete loops live in ``TestCOSFloat`` /
``TestCOSInteger``. Here we keep the parts that are independent of the
concrete subclass — ``testGet``, ``testLargeNumber``, ``testInvalidNumber``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSFloat, COSInteger, COSNumber


def test_get() -> None:
    # Ensure the basic static numbers are recognized.
    assert COSNumber.get("0") == COSInteger.ZERO  # type: ignore[attr-defined]
    assert COSNumber.get("-") == COSInteger.ZERO  # type: ignore[attr-defined]
    assert COSNumber.get(".") == COSInteger.ZERO  # type: ignore[attr-defined]
    assert COSNumber.get("1") == COSInteger.ONE  # type: ignore[attr-defined]
    assert COSNumber.get("2") == COSInteger.TWO  # type: ignore[attr-defined]
    assert COSNumber.get("3") == COSInteger.THREE  # type: ignore[attr-defined]
    # Test some arbitrary ints.
    assert COSNumber.get("100") == COSInteger.get(100)
    assert COSNumber.get("256") == COSInteger.get(256)
    assert COSNumber.get("-1000") == COSInteger.get(-1000)
    assert COSNumber.get("+2000") == COSInteger.get(2000)
    # Some arbitrary floats.
    assert COSNumber.get("1.1") == COSFloat(1.1)
    assert COSNumber.get("100.0") == COSFloat(100.0)
    assert COSNumber.get("-100.001") == COSFloat(-100.001)
    # Per the spec exponentials shouldn't be used in PDF, but they exist.
    assert COSNumber.get("-2e-006") is not None
    assert COSNumber.get("-8e+05") is not None

    with pytest.raises((TypeError, AttributeError)):
        COSNumber.get(None)  # type: ignore[arg-type]
    with pytest.raises(OSError):
        COSNumber.get("a")


def test_large_number() -> None:
    """PDFBOX-5176: large number, too big for a long, leads to a COSInteger
    value which is marked as invalid."""
    # Java Long.MAX_VALUE.
    cos_number = COSNumber.get(str(2**63 - 1))
    assert isinstance(cos_number, COSInteger)
    assert cos_number.is_valid()
    # Java Long.MIN_VALUE.
    cos_number = COSNumber.get(str(-(2**63)))
    assert isinstance(cos_number, COSInteger)
    assert cos_number.is_valid()

    # Out of range, max value.
    cos_number = COSNumber.get("18446744073307448448")
    assert isinstance(cos_number, COSInteger)
    assert not cos_number.is_valid()
    # Out of range, min value.
    cos_number = COSNumber.get("-18446744073307448448")
    assert isinstance(cos_number, COSInteger)
    assert not cos_number.is_valid()


def test_invalid_number() -> None:
    with pytest.raises(OSError):
        COSNumber.get("18446744073307F448448")
