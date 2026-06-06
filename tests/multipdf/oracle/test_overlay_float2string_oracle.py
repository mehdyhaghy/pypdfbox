"""Live PDFBox differential parity for ``Overlay.float2String``.

Drives ``Float2StringProbe`` (a verbatim inline copy of PDFBox 3.0.7's
package-private ``Overlay.float2String(float)`` BigDecimal pipeline) over
a spread of values and asserts pypdfbox's ``Overlay._float_to_string``
produces the byte-identical string. The probe also emits the float32 raw
int bits so the Python side reconstructs the exact same float32 the Java
side formatted — eliminating any double-parsing skew between the two
runtimes.

Covers the two upstream properties the old ``f"{v:.10f}"`` shortcut
missed: float32 shortest-round-trip digits, and ``toPlainString``'s
exponent expansion (which drops the trailing ``.0`` for whole numbers
that came from ``E``-notation).
"""
from __future__ import annotations

import struct

from pypdfbox.multipdf import Overlay
from tests.oracle.harness import requires_oracle, run_probe_text

# A spread spanning every Float.toString / BigDecimal.toPlainString branch:
# clean half-integers, irrational binary fractions, the >= 1e7 and < 1e-3
# E-notation thresholds, large and tiny magnitudes, and a negative value.
_VALUES: tuple[float, ...] = (
    0.0,
    1.0,
    1.5,
    0.1,
    150.0,
    200.5,
    12.34,
    283.46,
    0.000001,
    99.95,
    197.625,
    123456.789,
    0.0000001,
    1234567.0,
    0.333333333333,
    66.66666666,
    1e8,
    0.00012345678,
    -36.5,
    1e-4,
    0.0009999,
    1e7,
    9999999.0,
    5e-4,
    595.276,  # A4 width in points (typical overlay shift operand)
    841.89,
)


@requires_oracle
def test_float2string_matches_pdfbox_oracle() -> None:
    args = [repr(v) for v in _VALUES]
    text = run_probe_text("Float2StringProbe", *args)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == len(_VALUES)
    mismatches: list[str] = []
    for line in lines:
        bits_s, expected = line.split(" ", 1)
        bits = int(bits_s) & 0xFFFFFFFF
        # Reconstruct the exact float32 the Java side formatted.
        f32 = struct.unpack("f", struct.pack("I", bits))[0]
        got = Overlay._float_to_string(f32)  # noqa: SLF001
        if got != expected:
            mismatches.append(f"{f32!r}: pypdfbox={got!r} java={expected!r}")
    assert not mismatches, "float2String divergence:\n" + "\n".join(mismatches)
