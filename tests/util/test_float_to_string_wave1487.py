"""Java ``Float.toString`` parity for the scientific-notation regime.

``org.apache.pdfbox.util.Matrix.toString`` / ``Vector.toString`` concatenate the
*raw* ``Float.toString`` of each (float32) cell — which switches to scientific
``d.dddEexp`` notation when the magnitude is ``>= 1e7`` or ``< 1e-3``. Before
wave 1487 pypdfbox routed those through ``format_float32`` (the PDF
real-number serializer), which always strips the ``E`` form to plain decimal,
so a ``1e8`` Matrix cell rendered ``"100000000.0"`` where Java renders
``"1.0E8"``.

``float_to_string`` is the byte-for-byte ``Float.toString`` port that
``Matrix``/``Vector`` now use; ``format_float32`` builds on it and applies the
``BigDecimal.toPlainString`` step (so ``COSFloat.writePDF`` output stays plain
decimal). All expected values below were pinned from the live
``FloatToStringProbe`` oracle (Apache PDFBox 3.0.7 / OpenJDK 21).
"""

from __future__ import annotations

import struct

import pytest

from pypdfbox.cos.cos_float import float_to_string, format_float32


def _f32(value: float) -> float:
    """Narrow ``value`` to IEEE-754 single precision (what Matrix/Vector store)."""
    return struct.unpack("f", struct.pack("f", value))[0]


# (input-double, Float.toString) pinned from the live oracle.
_SCIENTIFIC_CASES = [
    # 1e7 upper boundary: >= 1e7 switches to E-notation.
    (9999999.0, "9999999.0"),
    (1.0e7, "1.0E7"),
    (1.0000001e7, "1.0000001E7"),
    (10000001.0, "1.0000001E7"),
    # 1e-3 lower boundary: < 1e-3 switches to E-notation.
    (0.001, "0.001"),
    (9.999999e-4, "9.999999E-4"),
    (0.0010001, "0.0010001"),
    # exact powers of ten across the window edges.
    (1.0e6, "1000000.0"),
    (1.0e8, "1.0E8"),
    (1.0e-2, "0.01"),
    (1.0e-4, "1.0E-4"),
    (1.0e10, "1.0E10"),
    (1.0e-10, "1.0E-10"),
    (1.0e20, "1.0E20"),
    (1.0e-20, "1.0E-20"),
    # negatives.
    (-4.2e10, "-4.2E10"),
    (-1.0e8, "-1.0E8"),
    (-1.23e-4, "-1.23E-4"),
    (-7.5e-5, "-7.5E-5"),
    # full-mantissa values.
    (1.2345678e9, "1.2345678E9"),
    (1.2345678e-5, "1.2345678E-5"),
    (1.23e-4, "1.23E-4"),
    # subnormals — two-significant-digit floor (the legacy FloatingDecimal
    # rendering), NOT the globally-shortest 1-digit form.
    (1.4e-45, "1.4E-45"),  # Float.MIN_VALUE
    (2.8e-45, "2.8E-45"),
    (3.0e-44, "2.9E-44"),
    (1.17549435e-38, "1.1754944E-38"),  # Float.MIN_NORMAL
    # Float.MAX_VALUE.
    (3.4028235e38, "3.4028235E38"),
    (-3.4028235e38, "-3.4028235E38"),
]


@pytest.mark.parametrize(
    ("value", "expected"),
    _SCIENTIFIC_CASES,
    ids=[expected for _, expected in _SCIENTIFIC_CASES],
)
def test_float_to_string_matches_java(value: float, expected: str) -> None:
    assert float_to_string(_f32(value)) == expected


# In-window plain-decimal values must keep their verbatim Float.toString form.
_DECIMAL_CASES = [
    (1.0, "1.0"),
    (100.0, "100.0"),
    (1000000.0, "1000000.0"),
    (0.5, "0.5"),
    (0.9950042, "0.9950042"),
    (0.099833414, "0.099833414"),
    (-0.099833414, "-0.099833414"),
    (0.8660254, "0.8660254"),
]


@pytest.mark.parametrize(
    ("value", "expected"),
    _DECIMAL_CASES,
    ids=[expected for _, expected in _DECIMAL_CASES],
)
def test_float_to_string_decimal_window_verbatim(value: float, expected: str) -> None:
    assert float_to_string(_f32(value)) == expected


def test_float_to_string_signed_zero() -> None:
    assert float_to_string(0.0) == "0.0"
    assert float_to_string(-0.0) == "-0.0"


def test_float_to_string_non_finite() -> None:
    assert float_to_string(float("nan")) == "NaN"
    assert float_to_string(float("inf")) == "Infinity"
    assert float_to_string(float("-inf")) == "-Infinity"


# --- format_float32 (PDF serializer) strips E-notation to plain decimal -----
# Pinned from the live oracle via COSFloat.writePDF.
_FORMAT_FLOAT32_CASES = [
    (1.0e8, "100000000"),
    (1.0e7, "10000000"),
    (1.0e-4, "0.0001"),
    (9.999999e-4, "0.0009999999"),
    (3.4028235e38, "340282350000000000000000000000000000000"),
    # The two-sig-digit subnormal floor now flows through to the plain form too:
    # COSFloat.writePDF emits the BigDecimal expansion of "1.4E-45".
    (1.4e-45, "0.0000000000000000000000000000000000000000000014"),
]


@pytest.mark.parametrize(
    ("value", "expected"),
    _FORMAT_FLOAT32_CASES,
    ids=[str(v) for v, _ in _FORMAT_FLOAT32_CASES],
)
def test_format_float32_strips_e_notation(value: float, expected: str) -> None:
    assert format_float32(_f32(value)) == expected


def test_format_float32_decimal_window_unchanged() -> None:
    # The wave-1485 in-window pins must not regress.
    for value, expected in _DECIMAL_CASES:
        assert format_float32(_f32(value)) == expected
    assert format_float32(0.0) == "0.0"
    assert format_float32(-0.0) == "-0.0"


# --- Matrix / Vector toString carry the scientific form ---------------------


def test_matrix_tostring_keeps_scientific_cells() -> None:
    from pypdfbox.util.matrix import Matrix

    m = Matrix(1.0e8, 0.0, 0.0, 1.0e-4, 0.0, 0.0)
    assert repr(m) == "[1.0E8,0.0,0.0,1.0E-4,0.0,0.0]"


def test_vector_tostring_keeps_scientific_components() -> None:
    from pypdfbox.util.vector import Vector

    v = Vector(1.0e8, 1.4e-45)
    assert v.to_string() == "(1.0E8, 1.4E-45)"


@pytest.mark.parametrize(
    ("value", "expected"),
    _SCIENTIFIC_CASES + _DECIMAL_CASES,
    ids=[e for _, e in _SCIENTIFIC_CASES + _DECIMAL_CASES],
)
def test_float_to_string_round_trips_to_same_float32(
    value: float, expected: str
) -> None:
    # Whatever Java renders, parsing it back must reproduce the float32.
    target = _f32(value)
    assert _f32(float(expected)) == target
