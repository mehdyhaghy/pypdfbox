"""
Ported from Apache PDFBox 3.0:
  pdfbox/src/test/java/org/apache/pdfbox/cos/TestCOSFloat.java

Upstream extends TestCOSNumber/TestCOSBase. The looped pseudorandom
``BaseTester`` machinery is collapsed to a single deterministic loop here.
``testAccept`` is translated to a recording-visitor dispatch check.
"""

from __future__ import annotations

import io
import math
import struct

import pytest

from pypdfbox.cos import COSFloat
from tests.cos.helpers import RecordingVisitor


def _values() -> list[float]:
    """Mirrors upstream's ``BaseTester`` range/step (low=-100k, high=300k,
    step=20k) using the deterministic seed 123456."""
    import random

    rnd = random.Random(123456)
    return [i * rnd.random() for i in range(-100_000, 300_000, 20_000)]


def _next_float(num: float) -> float:
    """Java's ``Float.intBitsToFloat(Float.floatToIntBits(num) + 1)``."""
    bits = struct.unpack(">i", struct.pack(">f", num))[0]
    return struct.unpack(">f", struct.pack(">i", bits + 1))[0]


def test_equals() -> None:
    for num in _values():
        test1 = COSFloat(num)
        test2 = COSFloat(num)
        test3 = COSFloat(num)
        # Reflexive
        assert test1 == test1
        # Symmetric
        assert test2 == test3
        assert test3 == test2
        # Transitive
        assert test1 == test2
        assert test2 == test3
        assert test1 == test3

        nf = _next_float(num)
        if not math.isnan(nf) and not math.isinf(nf):
            test4 = COSFloat(nf)
            # The next representable float must compare unequal.
            assert test4 != test1


def test_hash_code() -> None:
    for num in _values():
        test1 = COSFloat(num)
        test2 = COSFloat(num)
        assert hash(test1) == hash(test2)
        nf = _next_float(num)
        if not math.isnan(nf) and not math.isinf(nf):
            test3 = COSFloat(nf)
            assert hash(test3) is not hash(test1)


def test_float_value() -> None:
    for num in _values():
        # COSFloat clamps to float32, so compare against the round-tripped value.
        rounded = struct.unpack(">f", struct.pack(">f", num))[0]
        assert COSFloat(num).float_value() == rounded


def test_int_value() -> None:
    for num in _values():
        rounded = struct.unpack(">f", struct.pack(">f", num))[0]
        assert COSFloat(num).int_value() == int(rounded)


def test_long_value() -> None:
    for num in _values():
        rounded = struct.unpack(">f", struct.pack(">f", num))[0]
        assert COSFloat(num).long_value() == int(rounded)


def test_accept() -> None:
    visitor = RecordingVisitor()
    for num in _values()[:5]:
        COSFloat(num).accept(visitor)
    assert all(call[0] == "float" for call in visitor.calls)
    assert len(visitor.calls) == 5


def test_write_pdf() -> None:
    for literal in ("1.23", "-4.5", "0.000001", "2.500"):
        out = io.BytesIO()
        COSFloat(literal).write_pdf(out)
        assert out.getvalue() == literal.encode("iso-8859-1")


def test_double_negative() -> None:
    # PDFBOX-4289
    cos_float = COSFloat("--16.33")
    assert cos_float.float_value() == pytest.approx(-16.33, rel=1e-5)


def test_very_small_values() -> None:
    # Float.MIN_VALUE / 10
    small_value = (2**-149) / 10.0
    # Test must use a value smaller than Float.MIN_VALUE.
    assert small_value < 2**-149

    as_string = str(small_value)
    cos_float = COSFloat(as_string)
    assert cos_float.float_value() == 0.0

    small_value = -small_value
    as_string = str(small_value)
    cos_float = COSFloat(as_string)
    assert cos_float.float_value() == 0.0


def test_very_large_values() -> None:
    # Float.MAX_VALUE * 10
    float_max = 3.4028234663852886e38
    large_value = float_max * 10.0
    assert large_value > float_max

    as_string = str(large_value)
    cos_float = COSFloat(as_string)
    assert cos_float.float_value() == float_max

    large_value = -large_value
    as_string = str(large_value)
    cos_float = COSFloat(as_string)
    assert cos_float.float_value() == -float_max


def test_misplaced_negative() -> None:
    # PDFBOX-2990, PDFBOX-3369: ``0.00000-33917698``
    cos_float = COSFloat("0.00000-33917698")
    assert cos_float == COSFloat("-0.0000033917698")

    cos_float = COSFloat("0.-262")
    assert cos_float == COSFloat("-0.262")

    cos_float = COSFloat("-0.-262")
    assert cos_float == COSFloat("-0.262")

    cos_float = COSFloat("-12.-1")
    assert cos_float == COSFloat("-12.1")


def test_duplicate_misplaced_negative() -> None:
    with pytest.raises(OSError):
        COSFloat("0.-26-2")
    with pytest.raises(OSError):
        COSFloat("---0.262")
    with pytest.raises(OSError):
        COSFloat("--0.2-62")


def test_stub_operator_min_max_values() -> None:
    large_value = 32768.0
    large_negative_value = -32768.0
    assert COSFloat(large_value).float_value() == large_value
    assert COSFloat(large_negative_value).float_value() == large_negative_value


def test_is_set_direct() -> None:
    f = COSFloat(1.5)
    f.set_direct(True)
    assert f.is_direct()
    f.set_direct(False)
    assert not f.is_direct()
