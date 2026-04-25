"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSInteger.java

Upstream extends TestCOSNumber (which itself extends TestCOSBase). We pull
the relevant parent-class tests inline here so the suite is self-contained.

The ``testAccept`` and ``testWritePDF`` upstream tests rely on
``COSWriter`` to serialize the integer to bytes; pypdfbox does not yet
ship a writer (pdfwriter cluster) so those serialization checks are
replaced with a recording-visitor / direct-string check.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSFloat, COSInteger, COSNumber


def test_get() -> None:
    # Static numbers map back to their cached singletons.
    assert COSNumber.get("0") is COSInteger.ZERO  # type: ignore[attr-defined]
    assert COSNumber.get("-") is COSInteger.ZERO  # type: ignore[attr-defined]
    assert COSNumber.get(".") is COSInteger.ZERO  # type: ignore[attr-defined]
    assert COSNumber.get("1") is COSInteger.ONE  # type: ignore[attr-defined]
    assert COSNumber.get("2") is COSInteger.TWO  # type: ignore[attr-defined]
    assert COSNumber.get("3") is COSInteger.THREE  # type: ignore[attr-defined]
    # Arbitrary ints.
    assert COSNumber.get("100") == COSInteger.get(100)
    assert COSNumber.get("256") == COSInteger.get(256)
    assert COSNumber.get("-1000") == COSInteger.get(-1000)
    assert COSNumber.get("+2000") == COSInteger.get(2000)
    # Floats.
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
    # Java Long.MAX_VALUE / MIN_VALUE.
    cos_number = COSNumber.get(str(2**63 - 1))
    assert isinstance(cos_number, COSInteger)
    assert cos_number.is_valid()

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


def test_equals() -> None:
    # Consistency over a range of arbitrary values.
    for i in range(-1000, 3000, 200):
        test1 = COSInteger.get(i)
        test2 = COSInteger.get(i)
        test3 = COSInteger.get(i)
        # Reflexive
        assert test1 == test1
        # Symmetric
        assert test2 == test1
        assert test1 == test2
        # Transitive
        assert test1 == test2
        assert test2 == test3
        assert test1 == test3

        test4 = COSInteger.get(i + 1)
        assert test4 != test1


def test_hash_code() -> None:
    for i in range(-1000, 3000, 200):
        test1 = COSInteger.get(i)
        test2 = COSInteger.get(i)
        assert hash(test1) == hash(test2)
        test3 = COSInteger.get(i + 1)
        assert hash(test3) is not hash(test1)


def test_float_value() -> None:
    for i in range(-1000, 3000, 200):
        assert COSInteger.get(i).float_value() == float(i)


def test_int_value() -> None:
    for i in range(-1000, 3000, 200):
        assert COSInteger.get(i).int_value() == i


def test_long_value() -> None:
    for i in range(-1000, 3000, 200):
        assert COSInteger.get(i).long_value() == i


def test_accept() -> None:
    # Upstream uses COSWriter; pypdfbox has no writer yet. We assert that
    # the integer accepts a visitor and dispatches to ``visit_from_integer``.
    from tests.cos.helpers import RecordingVisitor

    visitor = RecordingVisitor()
    for i in range(-1000, 3000, 200):
        COSInteger.get(i).accept(visitor)
    assert all(call[0] == "integer" for call in visitor.calls)
    assert len(visitor.calls) == len(range(-1000, 3000, 200))


@pytest.mark.skip(reason="writePDF requires pdfwriter / COSWriter (not yet ported)")
def test_write_pdf() -> None:
    pass


# ---------- inherited from TestCOSBase ----------


def test_is_set_direct() -> None:
    test_cos_base = COSInteger.get(0)
    test_cos_base.set_direct(True)
    assert test_cos_base.is_direct()
    test_cos_base.set_direct(False)
    assert not test_cos_base.is_direct()
