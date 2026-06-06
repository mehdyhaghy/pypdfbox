"""Wave 1505 — Overlay.float2String byte-faithful port (agent C).

``Overlay.float2String`` (and its internal alias ``_float_to_string``)
emit the decimal numbers that go into the overlay placement content
stream (``a b c d e f cm``). Upstream's helper is::

    private String float2String(float floatValue) {
        BigDecimal value = new BigDecimal(String.valueOf(floatValue));
        String s = value.toPlainString();
        if (s.indexOf('.') > -1 && !s.endsWith(".0"))
            while (s.endsWith("0") && !s.endsWith(".0"))
                s = s.substring(0, s.length() - 1);
        return s;
    }

Two upstream properties the previous ``f"{value:.10f}"`` shortcut did
NOT honour, both fixed here and pinned against Java PDFBox 3.0.7
reference output (see ``oracle/probes`` /F2S reference run captured in
the wave 1505 report):

1. The value is cast to a **32-bit float** before formatting, then
   rendered with ``Float.toString``'s *shortest round-trip* digits —
   not a fixed 10-fractional-digit double rendering. e.g. ``123456.789``
   → ``123456.79`` (float32 rounds), ``66.66666``f → ``66.666664``.
2. ``BigDecimal.toPlainString()`` expands ``Float.toString``'s
   ``E``-notation. When the exponent pushes the decimal point past all
   significant digits the plain string has **no** decimal point and
   therefore keeps no trailing ``.0`` — e.g. ``1e8`` → ``100000000``
   (the old code produced ``100000000.0``).
"""
from __future__ import annotations

import struct

import pytest

from pypdfbox.multipdf import Overlay

# Golden table: input double -> expected string, captured from Java
# PDFBox 3.0.7 ``float2String((float) input)`` (BigDecimal pipeline).
_GOLDEN: dict[float, str] = {
    0.0: "0.0",
    1.0: "1.0",
    1.5: "1.5",
    0.1: "0.1",
    150.0: "150.0",
    200.5: "200.5",
    12.34: "12.34",
    283.46: "283.46",
    0.000001: "0.000001",
    99.95: "99.95",
    197.625: "197.625",
    123456.789: "123456.79",  # float32 rounds the double down
    0.0000001: "0.0000001",
    1234567.0: "1234567.0",
    0.333333333333: "0.33333334",  # float32 shortest repr
    66.66666666: "66.666664",  # float32 shortest repr
    1e8: "100000000",  # toPlainString drops the point -> no .0
    0.00012345678: "0.00012345678",
    -36.5: "-36.5",
    -0.0: "0.0",  # BigDecimal normalises the sign away
    1e-4: "0.0001",
    0.0009999: "0.0009999",
    1e7: "10000000",  # >= 1e7 uses E-notation upstream; plain -> no .0
    9999999.0: "9999999.0",
    5e-4: "0.0005",
}


@pytest.mark.parametrize(
    ("value", "expected"),
    list(_GOLDEN.items()),
    ids=[f"{k!r}" for k in _GOLDEN],
)
def test_float_to_string_matches_java_float2string(
    value: float, expected: str
) -> None:
    assert Overlay._float_to_string(value) == expected  # noqa: SLF001


@pytest.mark.parametrize(
    ("value", "expected"),
    list(_GOLDEN.items()),
    ids=[f"{k!r}" for k in _GOLDEN],
)
def test_public_float2_string_matches_java(value: float, expected: str) -> None:
    # The public parity mirror must agree byte-for-byte.
    assert Overlay.float2_string(value) == expected


def test_no_trailing_zero_except_dot_zero() -> None:
    """Upstream strips trailing ``0`` digits but always keeps a final
    ``.0`` on integer-valued plain decimals."""
    f = Overlay._float_to_string  # noqa: SLF001
    assert f(12.500) == "12.5"
    assert f(12.0) == "12.0"
    assert not f(12.34).endswith("0")


def test_float32_cast_is_applied() -> None:
    """A double that is not representable as float32 must render the
    nearest float32's shortest decimal, not the double's digits."""
    f = Overlay._float_to_string  # noqa: SLF001
    # 0.1 + 0.2 == 0.30000000000000004 as a double; float32-nearest is 0.3.
    val = 0.1 + 0.2
    f32 = struct.unpack("f", struct.pack("f", val))[0]
    assert f(val) == f(f32)
    assert f(val) == "0.3"


def test_negative_zero_normalised() -> None:
    assert Overlay._float_to_string(-0.0) == "0.0"  # noqa: SLF001
